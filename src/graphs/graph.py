"""
小红书内容生成系统 - 飞书自动化工作流
包含5个飞书自动化工作流，实现从飞书读取→LLM生成→写入飞书的完整流程
"""

import os
import re
import json
import time
import logging
import requests
from datetime import datetime
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field
from jinja2 import Template
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from coze_workload_identity import Client

from graphs.state import (
    GlobalState,
    FeishuReadInput,
    FeishuWriteInput,
    FeishuTopicPostInput,
    FeishuImageSuggestionInput,
    FeishuWeeklyReviewInput,
)
from graphs.nodes.feishu_read_node import feishu_read_node
from graphs.nodes.feishu_write_node import feishu_write_node, FeishuBitableWriter


# ============================================
# 品牌规范 & 禁用词
# ============================================
FORBIDDEN_WORDS = [
    "招财", "转运", "辟邪", "改命", "风水", "保佑", "开运",
    "旺财", "聚财", "镇宅", "化煞", "消灾", "祈福", "灵验",
]

# 内容类型到薯账号映射
CONTENT_TYPE_SHU_MAP = {
    "家居/空间": ["@家居薯", "@生活薯"],
    "文化/知识": ["@知识薯", "@人文薯"],
    "穿搭/饰品": ["@时尚薯", "@穿搭薯"],
    "普通内容": ["@薯条小助手"],
    "节日热点": ["@生活薯", "@人文薯"],
    "家具工艺": ["@家居薯", "@知识薯"],
}

# 默认薯账号（如果无法判断内容类型）
DEFAULT_SHU_ACCOUNTS = ["@薯条小助手"]

# 双账号配置
ACCOUNT_CONFIG = {
    "灵楠阁品牌号": {
        "name": "灵楠阁品牌号",
        "focus": "金丝楠木中式生活美学——饰品、文房、香器、茶器",
        "tone": "生活美学、情感陪伴、仪式感、精致日常",
        "audience": "25-35岁女性，喜欢传统文化和精致生活方式，注重审美和情感价值",
        "product_categories": ["饰品", "文房", "香器", "茶器"],
        "content_angles": [
            "产品与日常生活的融合（喝茶、读书、焚香、写字）",
            "送礼场景（闺蜜礼、生日、节日、乔迁）",
            "自用好物分享（包浆变化、搭配心得）",
            "文化入门（金丝楠是什么、怎么选、怎么养）",
        ],
    },
    "古典家具号": {
        "name": "古典家具号",
        "focus": "金丝楠木古典家具与空间美学——家具、摆件、定制",
        "tone": "专业深度、文化底蕴、收藏价值、空间美学",
        "audience": "中式家居爱好者、收藏者、设计师、茶空间主理人",
        "product_categories": ["家具", "摆件", "定制"],
        "content_angles": [
            "家具形制与历史文化（圈椅、翘头案、博古架的来历与讲究）",
            "空间搭配方案（不同户型如何选配中式家具）",
            "金丝楠家具的收藏与养护",
            "一件家具的诞生（选料→开料→榫卯→打磨的全过程记录）",
        ],
    },
}

# 薯账号映射：根据内容类型自动添加对应的薯账号
SHU_ACCOUNT_MAP = {
    "家居/空间": ["@家居薯", "@生活薯"],
    "文化/知识": ["@知识薯", "@人文薯"],
    "穿搭/饰品": ["@时尚薯", "@穿搭薯"],
    "普通内容": ["@薯条小助手"],
    "节日热点": ["@生活薯", "@人文薯"],
    "家具工艺": ["@家居薯", "@知识薯"],
}

# 简化版：根据内容栏目/SOP类型映射
POTATO_ACCOUNTS = {
    "节日热点": ["@生活薯", "@人文薯"],
    "家具工艺": ["@家居薯", "@知识薯"],
    "家居/空间": ["@家居薯", "@生活薯"],
    "文化/知识": ["@知识薯", "@人文薯"],
    "普通内容": ["@薯条小助手"],
}




# ============================================
# 工具函数
# ============================================

def extract_feishu_field(fields: dict, field_name: str) -> str:
    """
    从飞书字段值中提取文本内容。
    支持文本、多选、关联记录、数字、日期等多种字段类型。
    """
    field_value = fields.get(field_name) if fields else None
    if field_value is None:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, (int, float)):
        return str(field_value)
    if isinstance(field_value, list):
        if not field_value:
            return ""
        texts = []
        for item in field_value:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    texts.append(text)
            elif isinstance(item, str):
                texts.append(item)
        return ", ".join(texts)
    return str(field_value)


def parse_llm_json(content: str) -> dict:
    """从LLM输出中解析JSON，带多种回退策略。"""
    # 策略1: 直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 策略2: 提取 ```json ... ``` 代码块
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略3: 提取最外层大括号
    brace_start = content.find('{')
    brace_end = content.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(content[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从LLM输出中解析JSON，原始内容前200字符: {content[:200]}")


def validate_content(title: str, body: str) -> list[str]:
    """校验生成内容，返回问题列表（空列表=通过）。"""
    issues = []
    for word in FORBIDDEN_WORDS:
        if word in title:
            issues.append(f"标题包含禁用词: {word}")
        if word in body:
            issues.append(f"正文包含禁用词: {word}")
    if len(title) > 30:
        issues.append(f"标题过长({len(title)}字), 建议不超过20字")
    body_clean = body.replace('\n', '').replace(' ', '')
    if len(body_clean) < 200:
        issues.append(f"正文字数偏少({len(body_clean)}字), 建议300-700字")
    return issues


def llm_invoke(
    messages: list,
    model: str = "doubao-seed-2-0-pro-260215",
    temperature: float | None = None,
    max_retries: int = 3,
    ctx = None,
) -> str:
    """调用LLM，带重试机制。"""
    last_error: Exception = Exception("LLM调用失败，未知错误")
    for attempt in range(max_retries):
        try:
            kwargs = {"messages": messages, "model": model}
            if temperature is not None:
                kwargs["temperature"] = temperature
            client = LLMClient(ctx=ctx) if ctx else LLMClient()
            response = client.invoke(**kwargs)
            result = response.content if isinstance(response.content, str) else str(response.content)
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
    raise last_error


def llm_generate_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float | None = None,
    ctx = None,
    max_retries: int = 3,
) -> dict:
    """调用LLM并返回解析后的JSON，JSON解析失败时重试。"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    last_content = ""
    for attempt in range(max_retries):
        try:
            content = llm_invoke(messages, temperature=temperature, ctx=ctx)
            last_content = content
            return parse_llm_json(content)
        except ValueError as e:
            if attempt < max_retries - 1:
                # 重试时追加格式提醒
                messages.append(HumanMessage(content=f"上次输出JSON解析失败: {e}\n请严格按照JSON格式重新输出，不要输出任何JSON之外的内容。"))
    raise ValueError(f"JSON解析重试{max_retries}次后仍然失败。最后输出: {last_content[:500]}")


def llm_generate_text(
    system_prompt: str,
    user_prompt: str,
    temperature: float | None = None,
    ctx = None,
) -> str:
    """调用LLM并返回纯文本响应，不解析JSON。"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    return llm_invoke(messages, temperature=temperature, ctx=ctx)


def filter_products_by_account(products: list[dict], account: str) -> list[dict]:
    """按账号定位筛选相关产品。匹配的产品排前面，不匹配的排后面作为备选。"""
    config = ACCOUNT_CONFIG.get(account)
    if not config:
        return products
    categories = config["product_categories"]
    matched = [p for p in products if p.get("分类", "") in categories]
    others = [p for p in products if p.get("分类", "") not in categories]
    return matched + others


def get_account_context(account: str) -> str:
    """获取账号定位摘要，注入LLM提示词。"""
    config = ACCOUNT_CONFIG.get(account)
    if not config:
        return ""
    return f"""目标账号：{account}
账号定位：{config['focus']}
内容调性：{config['tone']}
目标受众：{config['audience']}
推荐切入角度：{', '.join(config['content_angles'])}"""


# ============================================
# 统一入参定义
# ============================================
class WorkflowInput(BaseModel):
    """工作流统一输入参数 - 所有参数已预填默认值，直接运行即可"""
    workflow_type: Literal["一键生成", "热点选题", "选题文案", "客户故事", "图片建议", "数据复盘", "内容整理"] = Field(
        default="一键生成",
        description="工作流类型（默认：一键生成，直接运行即可）"
    )

    # 飞书通用参数
    feishu_app_token: str = Field(default="FoWqb7NLuah1gdssEHbc7Wk9nQh", description="飞书多维表格app_token")
    feishu_product_table_id: str = Field(default="tbllExTlKURFJP2j", description="产品素材表table_id")
    feishu_topic_table_id: str = Field(default="tblJNjx74uZ3s1vs", description="选题库table_id")
    feishu_content_table_id: str = Field(default="tblg7zZuWKcUvqQX", description="内容成品库table_id")
    feishu_review_table_id: str = Field(default="tblfSaXuLDh6OKEq", description="数据复盘表table_id")
    feishu_hot_calendar_table_id: str = Field(default="tblT1KM0397UcGeM", description="热点日历表table_id")

    # 热点选题参数
    target_audience: str = Field(default="25-35岁女性，喜欢传统文化和审美生活方式", description="目标人群")
    content_style: str = Field(default="新中式、克制、种草但不硬广", description="内容风格")
    publish_account: str = Field(default="灵楠阁品牌号", description="发布账号")

    # 客户故事参数
    customer_background: str = Field(default="", description="客户背景")
    purchased_product: str = Field(default="", description="购买产品")
    purchase_reason: str = Field(default="", description="购买原因")
    usage_scenario: str = Field(default="", description="使用场景")
    customer_feedback: str = Field(default="", description="客户反馈")

    # 内容整理参数
    filter_status: str = Field(default="待审核", description="筛选状态（如：待审核、已通过）")
    page_size: int = Field(default=10, description="读取记录数量")
    
    # 自选生成参数（从Streamlit界面传入）
    selected_products: list = Field(default=[], description="选中的产品列表")
    selected_hots: list = Field(default=[], description="选中的热点列表")


class WorkflowOutput(BaseModel):
    """工作流统一输出"""
    workflow_type: str = Field(..., description="执行的工作流类型")
    result: str = Field(..., description="生成结果")
    processed_count: int = Field(default=0, description="处理记录数")
    success_count: int = Field(default=0, description="成功写入数")


class FeishuWorkflowOutput(BaseModel):
    """飞书工作流输出"""
    workflow_type: str = Field(..., description="工作流类型")
    result: str = Field(..., description="处理结果")
    processed_count: int = Field(default=0, description="处理记录数")
    success_count: int = Field(default=0, description="成功写入数")


# ============================================
# 工作流①：热点选题
# 热点日历库 + 产品素材库 → LLM生成 → 写入选题库
# ============================================
def feishu_hot_topic_workflow_node(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 热点选题
    desc: 从热点日历库+产品库读取数据，生成选题，写入选题库
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context

    # 加载热点选题配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_hot_topic_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        hot_topic_cfg = json.load(f)

    # 步骤1: 读取热点日历库
    hot_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_hot_calendar_table_id,
        filter_field="状态",
        filter_value="待准备",
        page_size=5
    )
    hot_output = feishu_read_node(hot_input, config, runtime)

    if hot_output.record_count == 0:
        return FeishuWorkflowOutput(
            workflow_type="feishu_hot_topic",
            result="没有找到待处理的热点",
            processed_count=0,
            success_count=0
        )

    # 步骤2: 读取产品素材库（读取所有关键字段）
    product_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_product_table_id,
        filter_field="产品状态",
        filter_value="可发布",
        page_size=20
    )
    product_output = feishu_read_node(product_input, config, runtime)

    # 构建产品信息列表（含所有可用于文案生成的字段）
    products_info = []
    for record in product_output.records:
        fields = record.get("fields", {})
        name = extract_feishu_field(fields, "产品名称")
        if not name:
            continue
        products_info.append({
            "名称": name,
            "分类": extract_feishu_field(fields, "产品分类"),
            "材质": extract_feishu_field(fields, "材质说明"),
            "卖点": extract_feishu_field(fields, "核心卖点"),
            "价格": extract_feishu_field(fields, "价格区间"),
            "人群": extract_feishu_field(fields, "适合人群"),
            "场景": extract_feishu_field(fields, "使用场景"),
            "record_id": record.get("record_id", ""),
        })

    # 步骤3: 逐条处理热点
    success_count = 0
    results = []

    for record in hot_output.records[:3]:  # 最多处理3条热点
        fields = record.get("fields", {})
        hot_record_id = record.get("record_id", "")

        hot_topic_name = extract_feishu_field(fields, "热点名称")
        hot_topic_date = extract_feishu_field(fields, "热点日期")
        hot_topic_type = extract_feishu_field(fields, "热点类型")
        hot_angles = extract_feishu_field(fields, "备选角度")  # 人工编辑已想好的角度
        account = extract_feishu_field(fields, "适合账号") or state.publish_account

        if not hot_topic_name:
            continue

        # 确定目标账号（优先用热点日历中的"适合账号"，否则用传入的默认值）
        account = extract_feishu_field(fields, "适合账号") or state.publish_account
        # 适合账号可能是多选（如"灵楠阁品牌号,古典家具号"），取第一个作为主账号
        account = account.split(",")[0].strip() if account else "灵楠阁品牌号"

        # 按账号筛选产品（匹配的排前面）
        ordered_products = filter_products_by_account(products_info, account)

        # 构建产品摘要
        product_summary_lines = []
        for p in ordered_products:
            product_summary_lines.append(
                f"- {p['名称']}（{p['分类']}）材质：{p['材质']} | 卖点：{p['卖点']} | 场景：{p['场景']} | 人群：{p['人群']}"
            )
        product_summary = "\n".join(product_summary_lines) if product_summary_lines else "暂无产品数据"

        # 构建账号上下文
        account_context = get_account_context(account)

        # 构建用户提示词
        user_prompt = f"""请根据以下信息为指定账号生成5-8个选题方案：

{account_context}

热点名称：{hot_topic_name}
热点日期：{hot_topic_date}
热点类型：{hot_topic_type}
编辑建议角度：{hot_angles if hot_angles else '无，请自行发挥'}

可用产品列表（按账号关联度排序）：
{product_summary}

请输出选题JSON，直接输出JSON不要任何其他文字。"""

        try:
            data = llm_generate_json(hot_topic_cfg.get("sp", ""), user_prompt, temperature=0.7, ctx=ctx)
        except (ValueError, Exception) as e:
            results.append(f"✗ {hot_topic_name} LLM调用失败: {str(e)[:100]}")
            continue

        # 处理返回数据格式：可能是list（直接是选题数组）或dict（包含选题列表字段）
        if isinstance(data, list):
            topic_list = data
        elif isinstance(data, dict):
            topic_list = data.get("选题列表", [])
        else:
            topic_list = []
        
        if not topic_list:
            results.append(f"✗ {hot_topic_name} LLM返回了空的选题列表")
            continue

        # 逐条写入选题库
        for topic in topic_list[:10]:
            topic_title = topic.get("选题标题", "")[:20]
            topic_column = topic.get("内容栏目", "SOP1热点")
            topic_angle = topic.get("切入角度", "")
            cover_text = topic.get("封面文案建议", "")
            cover_direction = topic.get("封面图方向", "")
            tags = topic.get("预期标签", "")
            at_accounts = topic.get("预期@薯", "")

            # 校验
            validation_issues = validate_content(topic_title, topic_angle + cover_text)
            if validation_issues:
                results.append(f"⚠ {topic_title} 校验问题: {'; '.join(validation_issues)}")

            try:
                write_input = FeishuWriteInput(
                    app_token=state.feishu_app_token,
                    table_id=state.feishu_topic_table_id,
                    record_id="",
                    fields={
                        "选题标题": topic_title,
                        "内容栏目": topic_column,
                        "目标账号": account,
                        "关联热点": [hot_record_id] if hot_record_id else [],
                        "切入角度": topic_angle,
                        "封面文案建议": cover_text,
                        "封面图方向": cover_direction,
                        "预期标签": tags,
                        "预期@薯": at_accounts.split(",") if at_accounts else [],
                        "选题状态": "待审核",
                    }
                )
                write_output = feishu_write_node(write_input, config, runtime)
                logging.info(f"写入结果: success={write_output.success}, message={write_output.message}")
                if write_output.success:
                    success_count += 1
                    results.append(f"✓ {topic_title}")
                else:
                    results.append(f"✗ {topic_title} 写入失败: {write_output.message}")
            except Exception as e:
                results.append(f"✗ {topic_title} 写入异常: {str(e)[:100]}")

    return FeishuWorkflowOutput(
        workflow_type="feishu_hot_topic",
        result="\n".join(results) if results else "未生成任何选题",
        processed_count=len(results),
        success_count=success_count
    )


# ============================================
# 工作流②：选题文案
# 选题库 + 产品素材库 → LLM生成文案 → 写入内容成品库
# ============================================
def feishu_topic_post_workflow_node(
    state: FeishuTopicPostInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 选题文案
    desc: 从选题库读取通过的选题→读取产品素材→生成文案→写入内容成品库
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context

    # 加载选题文案配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_topic_post_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        topic_post_cfg = json.load(f)

    app_token = state.feishu_app_token
    topic_table_id = state.feishu_topic_table_id
    product_table_id = state.feishu_product_table_id
    content_table_id = state.feishu_content_table_id
    filter_status = getattr(state, 'filter_status', '通过') or '通过'

    # 步骤1: 读取选题库（含关联记录信息）
    topic_input = FeishuReadInput(
        app_token=app_token,
        table_id=topic_table_id,
        filter_field="选题状态",
        filter_value=filter_status,
        page_size=5
    )
    topic_output = feishu_read_node(topic_input, config, runtime)

    if not topic_output.records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_topic_post",
            result="没有找到待处理的选题记录",
            processed_count=0,
            success_count=0
        )

    # 步骤2: 读取产品素材库（完整字段）
    product_input = FeishuReadInput(
        app_token=app_token,
        table_id=product_table_id,
        filter_field="产品状态",
        filter_value="可发布",
        page_size=30
    )
    product_output = feishu_read_node(product_input, config, runtime)

    # 构建产品信息映射
    product_map = {}
    for p in product_output.records:
        fields = p.get("fields", {})
        name = extract_feishu_field(fields, "产品名称")
        if name:
            product_map[name] = {
                "分类": extract_feishu_field(fields, "产品分类"),
                "材质": extract_feishu_field(fields, "材质说明"),
                "卖点": extract_feishu_field(fields, "核心卖点"),
                "场景": extract_feishu_field(fields, "使用场景"),
                "人群": extract_feishu_field(fields, "适合人群"),
                "价格": extract_feishu_field(fields, "价格区间"),
            }

    # 步骤3: 逐条处理选题
    success_count = 0
    results = []

    for topic_record in topic_output.records[:5]:
        topic_fields = topic_record.get("fields", {})
        topic_record_id = topic_record.get("record_id", "")
        topic_title = extract_feishu_field(topic_fields, "选题标题")
        topic_angle = extract_feishu_field(topic_fields, "切入角度")
        topic_column = extract_feishu_field(topic_fields, "内容栏目") or "SOP2产品"
        account = extract_feishu_field(topic_fields, "目标账号") or "灵楠阁品牌号"

        # 按账号筛选产品
        ordered_products = filter_products_by_account(
            [{"名称": name, "分类": info["分类"], "材质": info["材质"],
              "卖点": info["卖点"], "场景": info["场景"],
              "人群": info["人群"], "价格": info["价格"]}
             for name, info in product_map.items()],
            account
        )

        # 获取关联产品
        linked_products = topic_fields.get("关联产品", [])
        product_info = ""
        matched_product_name = ""
        if linked_products and isinstance(linked_products, list):
            for lp in linked_products:
                prod_name = lp.get("text", "") if isinstance(lp, dict) else str(lp)
                if prod_name in product_map:
                    p = product_map[prod_name]
                    product_info = f"""产品名称：{prod_name}
产品分类：{p['分类']}
材质说明：{p['材质']}
核心卖点：{p['卖点']}
适合人群：{p['人群']}
使用场景：{p['场景']}
价格区间：{p['价格']}"""
                    matched_product_name = prod_name
                    break

        if not product_info:
            # 回退：优先从匹配账号的产品中找
            for prod in ordered_products:
                prod_name = prod.get("名称", "")
                if prod_name in product_map:
                    p = product_map[prod_name]
                    if prod_name in topic_title or prod_name in topic_angle:
                        product_info = f"产品名称：{prod_name}\n材质说明：{p['材质']}\n核心卖点：{p['卖点']}\n使用场景：{p['场景']}"
                        matched_product_name = prod_name
                        break
            # 再回退：用第一个匹配账号的产品
            if not product_info and ordered_products:
                first = ordered_products[0]
                first_name = first.get("名称", "")
                if first_name in product_map:
                    p = product_map[first_name]
                    product_info = f"产品名称：{first_name}\n材质说明：{p['材质']}\n核心卖点：{p['卖点']}"
                    matched_product_name = first_name
            # 最后回退
            if not product_info and product_map:
                first = list(product_map.values())[0]
                first_name = list(product_map.keys())[0]
                product_info = f"产品名称：{first_name}\n材质说明：{first['材质']}\n核心卖点：{first['卖点']}"

        # 构建账号上下文
        account_context = get_account_context(account)

        # 构建用户提示词
        user_prompt = f"""请根据以下选题和产品信息生成一篇小红书笔记：

{account_context}

选题标题：{topic_title}
切入角度：{topic_angle}
内容栏目：{topic_column}

{product_info}

请输出完整文案JSON，直接输出JSON不要任何其他文字。"""

        try:
            data = llm_generate_json(topic_post_cfg.get("sp", ""), user_prompt, temperature=0.7, ctx=ctx)
        except (ValueError, Exception) as e:
            results.append(f"✗ {topic_title} LLM调用失败: {str(e)[:100]}")
            continue

        post_title = data.get("发布标题", topic_title)[:20]
        post_body = data.get("正文", "")
        post_cover = data.get("封面文案", "")
        post_tags = data.get("发布标签", "")
        at_accounts = data.get("@薯账号", "")
        comment_guide = data.get("评论区引导语", "")

        # 校验
        validation_issues = validate_content(post_title, post_body)
        if validation_issues:
            results.append(f"⚠ {post_title} 校验问题: {'; '.join(validation_issues)}")

        try:
            write_input = FeishuWriteInput(
                app_token=app_token,
                table_id=content_table_id,
                record_id="",
                fields={
                    "发布标题": post_title,
                    "正文": post_body,
                    "封面文案": post_cover,
                    "内容栏目": topic_column,
                    "发布账号": account,
                    "关联选题": [topic_record_id] if topic_record_id else [],
                    "发布标签": post_tags,
                    "@薯账号": at_accounts,
                    "评论区引导语": comment_guide,
                    "发布状态": "待审核",
                    "内容版本": "v1.0",
                }
            )
            write_output = feishu_write_node(write_input, config, runtime)
            if write_output.success:
                success_count += 1
                results.append(f"✓ {post_title} 文案已生成")
            else:
                results.append(f"✗ {post_title} 写入失败: {write_output.message}")
        except Exception as e:
            results.append(f"✗ {post_title} 写入异常: {str(e)[:100]}")

    return FeishuWorkflowOutput(
        workflow_type="feishu_topic_post",
        result="\n".join(results) if results else "没有处理任何选题",
        processed_count=len(results),
        success_count=success_count
    )


# ============================================
# 工作流③：客户故事
# 手动输入客户信息 → LLM生成故事 → 写入内容成品库
# ============================================
def feishu_customer_story_workflow_node(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 客户故事
    desc: 根据手动输入的客户信息生成故事文案，写入内容成品库
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context

    # 加载客户故事配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_customer_story_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        customer_story_cfg = json.load(f)

    if not state.customer_background or not state.purchased_product:
        return FeishuWorkflowOutput(
            workflow_type="feishu_customer_story",
            result="客户背景和购买产品为必填项",
            processed_count=0,
            success_count=0
        )

    account_context = get_account_context(state.publish_account)

    user_prompt = f"""请根据以下客户信息写一篇客户故事型小红书笔记：

{account_context}

客户背景：{state.customer_background}
购买产品：{state.purchased_product}
购买原因：{state.purchase_reason or '未提供'}
使用场景：{state.usage_scenario or '未提供'}
客户反馈：{state.customer_feedback or '未提供'}

请输出完整故事JSON，直接输出JSON不要任何其他文字。"""

    try:
        data = llm_generate_json(customer_story_cfg.get("sp", ""), user_prompt, temperature=0.7, ctx=ctx)
    except (ValueError, Exception) as e:
        return FeishuWorkflowOutput(
            workflow_type="feishu_customer_story",
            result=f"LLM调用失败: {str(e)[:200]}",
            processed_count=0,
            success_count=0
        )

    post_title = data.get("发布标题", f"{state.customer_background}的{state.purchased_product}故事")[:20]
    post_body = data.get("正文", "")
    post_cover = data.get("封面文案", "")
    post_tags = data.get("发布标签", "")
    at_accounts = data.get("@薯账号", "")
    comment_guide = data.get("评论区引导语", "")

    # 校验
    validation_issues = validate_content(post_title, post_body)
    result_prefix = ""
    if validation_issues:
        result_prefix = f"⚠ 校验问题: {'; '.join(validation_issues)}\n"

    try:
        write_input = FeishuWriteInput(
            app_token=state.feishu_app_token,
            table_id=state.feishu_content_table_id,
            record_id="",
            fields={
                "发布标题": post_title,
                "正文": post_body,
                "封面文案": post_cover,
                "内容栏目": "SOP5故事",
                "发布账号": state.publish_account,
                "发布标签": post_tags,
                "@薯账号": at_accounts,
                "评论区引导语": comment_guide,
                "发布状态": "待审核",
                "内容版本": "v1.0",
            }
        )
        write_output = feishu_write_node(write_input, config, runtime)

        if write_output.success:
            return FeishuWorkflowOutput(
                workflow_type="feishu_customer_story",
                result=f"{result_prefix}✓ {post_title} 客户故事已生成并写入",
                processed_count=1,
                success_count=1
            )
        else:
            return FeishuWorkflowOutput(
                workflow_type="feishu_customer_story",
                result=f"✗ 写入失败: {write_output.message}",
                processed_count=1,
                success_count=0
            )
    except Exception as e:
        return FeishuWorkflowOutput(
            workflow_type="feishu_customer_story",
            result=f"✗ 写入异常: {str(e)[:200]}",
            processed_count=1,
            success_count=0
        )


# ============================================
# 工作流④：图片建议
# 内容成品库 → LLM生成配图方案 → 更新内容库
# ============================================
def feishu_image_suggestion_workflow_node(
    state: FeishuImageSuggestionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 图片建议
    desc: 从内容成品库读取待配图内容，生成图片建议，更新内容库
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context

    # 加载图片建议配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_image_suggestion_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        image_suggestion_cfg = json.load(f)

    # 步骤1: 读取内容成品库中待审核的内容
    content_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_content_table_id,
        filter_field="发布状态",
        filter_value="待审核",
        page_size=5
    )
    content_output = feishu_read_node(content_input, config, runtime)

    if not content_output.records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_image_suggestion",
            result="没有找到待配图的内容记录",
            processed_count=0,
            success_count=0
        )

    success_count = 0
    results = []

    for content_record in content_output.records[:3]:
        content_fields = content_record.get("fields", {})
        content_record_id = content_record.get("record_id", "")
        post_title = extract_feishu_field(content_fields, "发布标题")
        post_body = extract_feishu_field(content_fields, "正文")

        if not post_title:
            continue

        # 从记录中提取发布账号，用于确定视觉风格
        content_account = extract_feishu_field(content_fields, "发布账号") or "灵楠阁品牌号"
        account_context = get_account_context(content_account)

        user_prompt = f"""请为以下内容设计图片发布方案：

{account_context}

内容标题：{post_title}
正文摘要：{post_body[:200]}...

请按格式输出配图方案（纯文本格式，不要输出JSON）。"""

        try:
            # 使用纯文本生成，不解析JSON
            suggestion_text = llm_generate_text(image_suggestion_cfg.get("sp", ""), user_prompt, temperature=0.7, ctx=ctx)
        except Exception as e:
            results.append(f"✗ {post_title} LLM调用失败: {str(e)[:100]}")
            continue

        # 更新内容成品库
        try:
            write_input = FeishuWriteInput(
                app_token=state.feishu_app_token,
                table_id=state.feishu_content_table_id,
                record_id=content_record_id,
                fields={
                    "正文": post_body + f"\n\n---\n{suggestion_text}",
                }
            )
            write_output = feishu_write_node(write_input, config, runtime)
            if write_output.success:
                success_count += 1
                results.append(f"✓ {post_title} 图片建议已更新")
            else:
                results.append(f"✗ {post_title} 更新失败: {write_output.message}")
        except Exception as e:
            results.append(f"✗ {post_title} 更新异常: {str(e)[:100]}")

    return FeishuWorkflowOutput(
        workflow_type="feishu_image_suggestion",
        result="\n".join(results) if results else "未处理任何内容",
        processed_count=len(results),
        success_count=success_count
    )


# ============================================
# 工作流⑤：数据复盘
# 数据复盘表 → LLM分析 → 回写复盘表 + 写入选题建议
# ============================================
def feishu_weekly_review_workflow_node(
    state: FeishuWeeklyReviewInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 数据复盘
    desc: 从数据复盘表读取本周数据，生成分析报告，回写复盘备注和选题建议
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context

    # 加载数据复盘配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_weekly_review_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        weekly_review_cfg = json.load(f)

    # 步骤1: 读取数据复盘表
    review_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_review_table_id,
        filter_field="",
        filter_value="",
        page_size=30
    )
    review_output = feishu_read_node(review_input, config, runtime)

    if not review_output.records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_weekly_review",
            result="没有找到数据复盘记录",
            processed_count=0,
            success_count=0
        )

    # 构建数据摘要
    data_lines = []
    for record in review_output.records:
        fields = record.get("fields", {})
        title = extract_feishu_field(fields, "发布标题")
        account = extract_feishu_field(fields, "发布账号")
        likes = extract_feishu_field(fields, "点赞数")
        collects = extract_feishu_field(fields, "收藏数")
        comments = extract_feishu_field(fields, "评论数")
        shares = extract_feishu_field(fields, "分享数")
        dms = extract_feishu_field(fields, "私信数")
        deal = extract_feishu_field(fields, "是否成交")
        amount = extract_feishu_field(fields, "成交金额（估）")

        data_lines.append(
            f"- {title} | {account} | 赞{likes} 藏{collects} 评{comments} 享{shares} 私{dms} | 成交:{deal} {amount}元"
        )

    data_str = "\n".join(data_lines)

    user_prompt = f"""请分析以下本周发布数据并给出优化建议：

本周数据（{len(review_output.records)}条）：
{data_str}

请输出分析JSON，直接输出JSON不要任何其他文字。"""

    try:
        data = llm_generate_json(weekly_review_cfg.get("sp", ""), user_prompt, temperature=0.3, ctx=ctx)
    except (ValueError, Exception) as e:
        return FeishuWorkflowOutput(
            workflow_type="feishu_weekly_review",
            result=f"LLM调用失败: {str(e)[:200]}",
            processed_count=len(review_output.records),
            success_count=0
        )

    # 格式化分析结果（双账号结构）
    brand_analysis = data.get("品牌号分析", {})
    furniture_analysis = data.get("家具号分析", {})
    next_week_topics = data.get("下周选题建议", [])

    result_text = f"📊 数据复盘报告（共分析{len(review_output.records)}条记录）\n\n"

    # 品牌号分析
    brand_best = brand_analysis.get("本周最佳", []) if isinstance(brand_analysis, dict) else []
    brand_common = brand_analysis.get("共性发现", "") if isinstance(brand_analysis, dict) else ""
    if brand_best or brand_common:
        result_text += "▎灵楠阁品牌号：\n"
        for item in brand_best:
            result_text += f"  ★ {item.get('发布标题', '')}\n"
            result_text += f"    {item.get('表现亮点', '')}\n"
            result_text += f"    可复制：{item.get('可复制点', '')}\n\n"
        if brand_common:
            result_text += f"  共性发现：{brand_common}\n\n"

    # 家具号分析
    furniture_best = furniture_analysis.get("本周最佳", []) if isinstance(furniture_analysis, dict) else []
    furniture_common = furniture_analysis.get("共性发现", "") if isinstance(furniture_analysis, dict) else ""
    if furniture_best or furniture_common:
        result_text += "▎古典家具号：\n"
        for item in furniture_best:
            result_text += f"  ★ {item.get('发布标题', '')}\n"
            result_text += f"    {item.get('表现亮点', '')}\n"
            result_text += f"    可复制：{item.get('可复制点', '')}\n\n"
        if furniture_common:
            result_text += f"  共性发现：{furniture_common}\n\n"

    # 下周选题建议
    if next_week_topics:
        result_text += "▎下周选题建议：\n"
        for i, topic in enumerate(next_week_topics, 1):
            target = topic.get("目标账号", "")
            result_text += f"  {i}. [{target}] {topic.get('内容栏目', '')}｜{topic.get('选题方向', '')}\n"
            result_text += f"     推荐理由：{topic.get('推荐理由', '')}\n"

    # 回写复盘备注到第一条记录
    write_success = False
    if review_output.records:
        first_record = review_output.records[0]
        first_record_id = first_record.get("record_id", "")
        try:
            write_input = FeishuWriteInput(
                app_token=state.feishu_app_token,
                table_id=state.feishu_review_table_id,
                record_id=first_record_id,
                fields={
                    "复盘备注": result_text,
                }
            )
            write_output = feishu_write_node(write_input, config, runtime)
            write_success = write_output.success
        except Exception:
            pass

    # 将下周选题建议写入选题库
    topic_success = 0
    for topic in next_week_topics[:5]:
        try:
            write_input = FeishuWriteInput(
                app_token=state.feishu_app_token,
                table_id=state.feishu_topic_table_id,
                record_id="",
                fields={
                    "选题标题": topic.get("选题方向", "")[:20],
                    "内容栏目": topic.get("内容栏目", "SOP1热点"),
                    "切入角度": topic.get("推荐理由", ""),
                    "目标账号": "灵楠阁品牌号",
                    "选题状态": "待审核",
                    "创建时间": int(datetime.now().timestamp() * 1000),
                }
            )
            w_out = feishu_write_node(write_input, config, runtime)
            if w_out.success:
                topic_success += 1
        except Exception:
            pass

    return FeishuWorkflowOutput(
        workflow_type="feishu_weekly_review",
        result=result_text + f"\n回写结果：复盘备注{'已' if write_success else '未'}写入，{topic_success}/{len(next_week_topics[:5])}条选题建议已写入选题库",
        processed_count=len(review_output.records),
        success_count=1 if write_success else 0
    )


def _generate_from_selection(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context],
    ctx
) -> FeishuWorkflowOutput:
    """根据选中的产品和热点直接生成内容"""
    
    # 加载文案生成配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_topic_post_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        post_cfg = json.load(f)
    
    sp = post_cfg.get("sp", "")
    
    generated_contents = []  # 存储生成的内容
    error_messages = []  # 存储错误信息
    status_messages = []  # 存储状态消息
    success_count = 0
    content_count = 0  # 实际生成的内容篇数
    
    # 构建产品信息文本
    products_text = ""
    for p in state.selected_products:
        products_text += f"- 产品名称: {p.get('name', '')}, 分类: {p.get('category', '')}\n"
    
    # 构建热点信息文本
    hots_text = ""
    for h in state.selected_hots:
        hots_text += f"- 热点: {h.get('title', '')}, 时间: {h.get('date', '')}\n"
    
    # 为每个产品生成内容
    for idx, product in enumerate(state.selected_products):
        product_name = product.get('name', '未知产品')
        product_category = product.get('category', '')
        logging.info(f"  [{idx+1}/{len(state.selected_products)}] 开始处理: {product_name}")
        
        # 构建选题角度
        topic_angle = f"产品推荐: {product_name}"
        if state.selected_hots:
            hot_titles = [h.get('title', '') for h in state.selected_hots]
            topic_angle = f"结合热点 {', '.join(hot_titles)} 推荐产品 {product_name}"
        
        # 构建用户提示词
        up_template = post_cfg.get("up", "")
        up_content = up_template.replace("{{topic_angle}}", topic_angle)
        up_content = up_content.replace("{{product_info}}", f"产品: {product_name}, 分类: {product_category}")
        up_content = up_content.replace("{{account}}", state.publish_account)
        
        # 重试机制：最多重试3次
        max_retries = 3
        retry_count = 0
        last_error = ""
        
        while retry_count < max_retries:
            retry_count += 1
            logging.info(f"尝试生成 ({retry_count}/{max_retries}): product={product_name}")
            
            try:
                # 调用LLM生成文案
                result = llm_generate_json(sp, up_content, temperature=0.7, ctx=ctx)
                logging.info(f"LLM返回结果类型: {type(result)}, 内容: {str(result)[:200] if result else 'None'}")
                
                if not result:
                    last_error = "LLM返回空结果"
                    logging.error(f"尝试 {retry_count} 失败: {last_error}")
                    if retry_count < max_retries:
                        continue
                    else:
                        generated_contents.append(f"❌ {product_name} 生成失败(重试{max_retries}次): {last_error}")
                        break
                    
                # 解析结果
                title = result.get("发布标题", "")
                body = result.get("正文", "")
                cover_text = result.get("封面文案", "")
                tags = result.get("发布标签", "")
                shu_account = result.get("@薯账号", "")
                comment_guide = result.get("评论区引导语", "")
                
                if not title or not body:
                    last_error = f"标题或正文为空: title={title[:20] if title else '空'}, body={body[:20] if body else '空'}"
                    logging.error(f"尝试 {retry_count} 失败: {last_error}")
                    if retry_count < max_retries:
                        continue
                    else:
                        generated_contents.append(f"❌ {product_name} 生成失败(重试{max_retries}次): {last_error}")
                        break
                
                # 生成图片建议
                image_suggestion = ""
                try:
                    image_cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_image_suggestion_cfg.json")
                    with open(image_cfg_path, 'r', encoding='utf-8') as f:
                        image_cfg = json.load(f)
                    
                    image_prompt = f"""请为以下小红书内容生成图片拍摄建议：

标题：{title}
正文：{body[:200]}...

请按格式输出纯文本配图方案（不要输出JSON）。"""
                    
                    image_suggestion = llm_generate_text(image_cfg.get("sp", ""), image_prompt, temperature=0.7, ctx=ctx)
                except Exception as e:
                    logging.warning(f"图片建议生成失败: {e}")
                
                # 整理内容
                body_with_image = f"{body}\n\n【图片建议】\n{image_suggestion}"
                
                content_organized = f"""【标题】{title}

【正文】
{body}

【封面文案】{cover_text}

【图片建议】
{image_suggestion}

【标签】{tags}

【@薯账号】{shu_account}

【评论区引导语】{comment_guide}

【发布账号】{state.publish_account}"""
                
                # 写入飞书表格（带重试）
                write_success = False
                write_error = ""
                for write_retry in range(max_retries):
                    try:
                        writer = FeishuBitableWriter()
                        
                        # 检查 access_token 是否有效
                        if not writer.access_token:
                            write_error = "飞书access_token为空，请检查飞书集成配置"
                            logging.error(f"写入失败(尝试{write_retry+1}): {write_error}")
                            continue
                        
                        new_content_fields = {
                            "发布标题": title,
                            "正文": body_with_image,
                            "发布标签": tags,
                            "发布账号": state.publish_account,
                            "@薯账号": shu_account,
                            "风险审核结果": "待审核",
                            "内容整理": content_organized
                        }
                        
                        logging.info(f"写入飞书(尝试{write_retry+1}): app_token={state.feishu_app_token[:10]}..., table_id={state.feishu_content_table_id}")
                        add_result = writer.add_record(state.feishu_app_token, state.feishu_content_table_id, new_content_fields)
                        
                        # 如果执行到这里，说明写入成功（_request在失败时会抛出异常）
                        write_success = True
                        logging.info(f"✓ 写入成功: {title}")
                        break
                    except Exception as e:
                        import traceback
                        write_error = f"{str(e)}"
                        logging.error(f"写入异常(尝试{write_retry+1}): {write_error}\n{traceback.format_exc()}")
                
                # 记录结果
                content_count += 1
                generated_contents.append(content_organized)
                logging.info(f"记录结果: write_success={write_success}, write_error={write_error}")
                if write_success:
                    success_count += 1
                    status_messages.append(f"✅ {title} 已写入飞书")
                else:
                    error_msg = write_error if write_error else "未知错误"
                    error_msg_full = f"❌ {title} 写入失败(重试{max_retries}次): {error_msg[:200]}"
                    logging.info(f"添加错误信息: {error_msg_full}")
                    error_messages.append(error_msg_full)
                
                # 生成成功，跳出重试循环
                break
                    
            except Exception as e:
                import traceback
                last_error = f"{str(e)}\n{traceback.format_exc()}"
                logging.error(f"生成异常(尝试{retry_count}): {last_error}")
                if retry_count >= max_retries:
                    error_messages.append(f"❌ {product_name} 生成失败(重试{max_retries}次): {str(e)[:100]}")
    
    # 构建结果文本
    result_text = f"✨ 自选生成完成！\n\n选中产品: {len(state.selected_products)} 个\n选中热点: {len(state.selected_hots)} 个\n生成内容: {content_count} 篇\n成功写入: {success_count} 篇\n\n"
    
    # 添加错误信息
    if error_messages:
        result_text += "⚠️ 错误信息:\n" + "\n".join(error_messages) + "\n\n"
    
    # 添加成功消息
    if status_messages:
        result_text += "\n".join(status_messages) + "\n\n"
    
    # 添加生成的内容
    result_text += "\n" + "="*50 + "\n".join(generated_contents)
    
    return FeishuWorkflowOutput(
        workflow_type="内容整理",
        result=result_text,
        processed_count=len(state.selected_products),
        success_count=success_count
    )


# ============================================
# 工作流⑥：内容整理
# 从内容成品库读取数据，整理输出标题、正文、封面文案、图片建议、标签、@官方号
# 或根据选中的产品和热点直接生成内容
# ============================================
def feishu_content_organize_workflow_node(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 内容整理
    desc: 从内容成品库读取数据整理输出，或根据选中的产品和热点直接生成内容
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context

    # 如果传入了选中的产品或热点，走直接生成流程
    if state.selected_products or state.selected_hots:
        return _generate_from_selection(state, config, runtime, ctx)

    # 否则走原有的从内容成品库读取流程
    # 步骤1: 从内容成品库读取数据
    content_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_content_table_id,
        filter_field="发布状态",
        filter_value=state.filter_status,
        page_size=state.page_size
    )
    content_output = feishu_read_node(content_input, config, runtime)

    if not content_output.records:
        return FeishuWorkflowOutput(
            workflow_type="内容整理",
            result="没有找到符合条件的记录",
            processed_count=0,
            success_count=0
        )

    # 步骤2: 整理每条记录的字段，并写入飞书表格
    organized_contents = []
    success_count = 0
    
    for record in content_output.records:
        fields = record.get("fields", {})
        record_id = record.get("record_id", "")

        # 提取各个字段
        title = extract_feishu_field(fields, "发布标题")
        body = extract_feishu_field(fields, "正文")
        cover_text = extract_feishu_field(fields, "封面文案")
        image_suggestion = extract_feishu_field(fields, "图片建议")
        tags = extract_feishu_field(fields, "发布标签")
        official_account = extract_feishu_field(fields, "发布账号")

        # 整理成格式化内容
        content_item = f"""【标题】{title}

【正文】
{body}

【封面文案】{cover_text}

【图片建议】
{image_suggestion}

【标签】{tags}

【发布账号】{official_account}"""
        organized_contents.append(content_item)

        # 写入飞书表格的"内容整理"字段
        try:
            from graphs.nodes.feishu_write_node import FeishuBitableWriter
            writer = FeishuBitableWriter()
            writer.update_record(
                app_token=state.feishu_app_token,
                table_id=state.feishu_content_table_id,
                record_id=record_id,
                fields={"内容整理": content_item}
            )
            success_count += 1
            print(f"✓ 已写入内容整理字段: {title}")
        except Exception as e:
            print(f"✗ 写入失败: {title}, 错误: {e}")

    # 步骤3: 合并所有内容用于显示
    result_text = f"📋 内容整理完成，共整理 {len(organized_contents)} 条记录，成功写入 {success_count} 条\n\n"
    result_text += "\n========================================\n".join(organized_contents)

    return FeishuWorkflowOutput(
        workflow_type="内容整理",
        result=result_text,
        processed_count=len(content_output.records),
        success_count=success_count
    )


def _generate_from_selected_items(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context],
    ctx,
    app_token: str,
    content_table_id: str,
    publish_account: str
) -> FeishuWorkflowOutput:
    """根据自选的产品和热点生成内容（一键生成工作流专用）"""
    
    logging.info(f"🎨 自选生成: {len(state.selected_products)} 个产品, {len(state.selected_hots)} 个热点")
    
    # 加载文案生成配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_topic_post_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        post_cfg = json.load(f)
    
    sp = post_cfg.get("sp", "")
    up_template = post_cfg.get("up", "")
    
    llm_client = LLMClient()
    generated_contents = []
    success_count = 0
    
    # 构建热点文本
    hots_text = ""
    if state.selected_hots:
        hot_titles = [h.get('title', '') for h in state.selected_hots]
        hots_text = f"结合热点：{', '.join(hot_titles)}"
    
    # 为每个产品生成内容
    for product in state.selected_products:
        product_name = product.get('name', '未知产品')
        product_category = product.get('category', '')
        
        # 构建选题角度
        if state.selected_hots:
            hot_titles = [h.get('title', '') for h in state.selected_hots]
            topic_angle = f"结合热点「{', '.join(hot_titles)}」推荐产品「{product_name}」"
        else:
            topic_angle = f"产品推荐: {product_name}"
        
        # 构建用户提示词
        up_content = up_template.replace("{{topic_angle}}", topic_angle)
        up_content = up_content.replace("{{product_info}}", f"产品: {product_name}, 分类: {product_category}")
        up_content = up_content.replace("{{account}}", publish_account)
        
        logging.info(f"  生成文案: {product_name}")
        
        try:
            # 调用LLM生成文案
            response = llm_client.invoke(
                messages=[
                    SystemMessage(content=sp),
                    HumanMessage(content=up_content)
                ],
                model=post_cfg.get("config", {}).get("model", "doubao-seed-2-0-pro-260215"),
                temperature=post_cfg.get("config", {}).get("temperature", 0.7),
                max_completion_tokens=post_cfg.get("config", {}).get("max_completion_tokens", 4096)
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            result = parse_llm_json(content)
            
            # 解析结果
            title = result.get("发布标题", "")
            body = result.get("正文", "")
            cover_text = result.get("封面文案", "")
            tags = result.get("发布标签", "")
            shu_account = result.get("@薯账号", "")
            comment_guide = result.get("评论区引导语", "")
            
            # 生成图片建议
            image_suggestion = ""
            try:
                image_cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_image_suggestion_cfg.json")
                with open(image_cfg_path, 'r', encoding='utf-8') as f:
                    image_cfg = json.load(f)
                
                image_prompt = f"""请为以下小红书内容生成图片拍摄建议：

标题：{title}
正文：{body[:200]}...

请按格式输出纯文本配图方案（不要输出JSON）。"""
                
                img_response = llm_client.invoke(
                    messages=[
                        SystemMessage(content=image_cfg.get("sp", "")),
                        HumanMessage(content=image_prompt)
                    ],
                    model=image_cfg.get("config", {}).get("model", "doubao-seed-2-0-pro-260215"),
                    temperature=0.7,
                    max_completion_tokens=4096
                )
                image_content = img_response.content if hasattr(img_response, 'content') else str(img_response)
                image_suggestion = str(image_content).strip()
            except Exception as e:
                logging.warning(f"图片建议生成失败: {e}")
            
            # 整理内容格式
            content_organized = f"""【标题】{title}

【正文】
{body}

【封面文案】{cover_text}

【图片建议】
{image_suggestion}

【标签】{tags}

【@薯账号】{shu_account}

【评论区引导语】{comment_guide}"""
            
            generated_contents.append({
                "title": title,
                "body": body,
                "cover_text": cover_text,
                "image_suggestion": image_suggestion,
                "tags": tags,
                "shu_account": shu_account,
                "comment_guide": comment_guide,
                "content_organized": content_organized
            })
            
            # 写入飞书表格
            try:
                write_input = FeishuWriteInput(
                    app_token=app_token,
                    table_id=content_table_id,
                    fields={
                        "发布标题": title,
                        "正文": body,
                        "封面文案": cover_text,
                        "图片建议": image_suggestion,
                        "发布标签": tags,
                        "@薯账号": shu_account,
                        "评论区引导语": comment_guide,
                        "发布账号": publish_account,
                        "发布状态": "待审核",
                        "内容整理": content_organized
                    }
                )
                write_output = feishu_write_node(write_input, config, runtime)
                if write_output.success:
                    success_count += 1
                    logging.info(f"  ✓ 已写入: {title}")
            except Exception as e:
                logging.error(f"  ✗ 写入失败: {e}")
                
        except Exception as e:
            import traceback
            logging.error(f"  ✗ 生成失败: {product_name} - {e}")
            logging.error(f"  详细堆栈: {traceback.format_exc()}")
    
    # 构建结果文本
    result_text = f"🎯 自选生成完成！\n\n"
    result_text += f"选中产品: {len(state.selected_products)} 个\n"
    result_text += f"选中热点: {len(state.selected_hots)} 个\n"
    result_text += f"生成内容: {len(generated_contents)} 篇\n"
    result_text += f"成功写入: {success_count} 篇\n\n"
    
    for i, content in enumerate(generated_contents, 1):
        result_text += f"\n{'='*50}\n"
        result_text += f"第{i}篇: {content['title']}\n"
        result_text += f"{'='*50}\n"
        result_text += content['content_organized']
    
    return FeishuWorkflowOutput(
        workflow_type="一键生成",
        result=result_text,
        processed_count=len(state.selected_products),
        success_count=success_count
    )


# ============================================
# 一键生成工作流
# ============================================
def one_click_generate_workflow_node(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 一键生成
    desc: 一键完成选题→文案→图片建议全流程，自动写入飞书表格，无需中间审核
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context
    
    # 预设参数（已默认填好）
    APP_TOKEN = state.feishu_app_token or "FoWqb7NLuah1gdssEHbc7Wk9nQh"
    HOT_CALENDAR_TABLE = state.feishu_hot_calendar_table_id or "tblT1KM0397UcGeM"
    PRODUCT_TABLE = state.feishu_product_table_id or "tbllExTlKURFJP2j"
    TOPIC_TABLE = state.feishu_topic_table_id or "tblJNjx74uZ3s1vs"
    CONTENT_TABLE = state.feishu_content_table_id or "tblg7zZuWKcUvqQX"
    publish_account = state.publish_account or "灵楠阁品牌号"
    
    # ========== 检查是否有自选产品和热点 ==========
    if state.selected_products or state.selected_hots:
        logging.info("🎯 检测到自选产品和热点，走自选生成流程...")
        return _generate_from_selected_items(state, config, runtime, ctx, APP_TOKEN, CONTENT_TABLE, publish_account)
    
    # ========== 步骤1: 生成选题 ==========
    print("📝 步骤1: 正在生成选题...")
    
    # 读取热点日历（筛选优先级为"必做"的热点，不限状态）
    hot_calendar_input = FeishuReadInput(
        app_token=APP_TOKEN,
        table_id=HOT_CALENDAR_TABLE,
        filter_field="优先级",
        filter_value="必做",
        page_size=10
    )
    hot_calendar_output = feishu_read_node(hot_calendar_input, config, runtime)
    logging.info(f"读取热点日历: {hot_calendar_output.record_count} 条记录")
    
    # 读取产品表
    product_input = FeishuReadInput(
        app_token=APP_TOKEN,
        table_id=PRODUCT_TABLE,
        filter_field="产品状态",
        filter_value="可发布",
        page_size=10
    )
    product_output = feishu_read_node(product_input, config, runtime)
    logging.info(f"读取产品表: {product_output.record_count} 条记录")
    
    # 构建产品列表
    products = []
    for record in product_output.records:
        fields = record.get("fields", {})
        products.append({
            "record_id": record.get("record_id", ""),
            "名称": extract_feishu_field(fields, "产品名称"),
            "分类": extract_feishu_field(fields, "产品分类"),
            "材质": extract_feishu_field(fields, "材质说明"),
            "卖点": extract_feishu_field(fields, "核心卖点"),
            "价格": extract_feishu_field(fields, "价格区间"),
            "人群": extract_feishu_field(fields, "适合人群"),
            "场景": extract_feishu_field(fields, "使用场景")
        })
    
    # 保存所有产品（不按账号过滤）
    all_products = products.copy()
    
    # 加载热点选题配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_hot_topic_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        hot_topic_cfg = json.load(f)
    
    llm_client = LLMClient()
    
    generated_topics = []
    topic_record_ids = []
    
    for hot_record in hot_calendar_output.records[:5]:  # 处理最多5个热点
        logging.info(f"处理热点: {hot_record.get('record_id', 'unknown')}")
        hot_fields = hot_record.get("fields", {})
        hot_topic_name = extract_feishu_field(hot_fields, "热点名称")
        hot_topic_date = extract_feishu_field(hot_fields, "热点日期")
        hot_topic_type = extract_feishu_field(hot_fields, "热点类型")
        hot_angles = extract_feishu_field(hot_fields, "编辑建议角度")
        # 读取热点日历中的账号和关联产品字段（统一使用"发布账号"字段名）
        hot_account = extract_feishu_field(hot_fields, "发布账号") or extract_feishu_field(hot_fields, "适合账号") or extract_feishu_field(hot_fields, "账号") or ""
        hot_linked_product_raw = extract_feishu_field(hot_fields, "关联产品") or extract_feishu_field(hot_fields, "关联产品关键词")
        logging.info(f"  热点名称: {hot_topic_name}, 类型: {hot_topic_type}, 账号: {hot_account}, 关联产品原始数据: {hot_linked_product_raw}")
        
        # 提取关联产品记录ID（飞书关联字段返回格式：{'link_record_ids': ['recxxx']}）
        linked_product_ids = []
        if isinstance(hot_linked_product_raw, dict) and "link_record_ids" in hot_linked_product_raw:
            linked_product_ids = hot_linked_product_raw.get("link_record_ids", [])
        elif isinstance(hot_linked_product_raw, list):
            for item in hot_linked_product_raw:
                if isinstance(item, dict) and "link_record_ids" in item:
                    linked_product_ids.extend(item.get("link_record_ids", []))
                elif isinstance(item, str):
                    # 尝试解析字符串形式的JSON
                    try:
                        parsed_item = json.loads(item.replace("'", '"'))
                        if isinstance(parsed_item, dict) and "link_record_ids" in parsed_item:
                            linked_product_ids.extend(parsed_item.get("link_record_ids", []))
                    except json.JSONDecodeError:
                        linked_product_ids.append(item)
        elif isinstance(hot_linked_product_raw, str) and hot_linked_product_raw:
            # 尝试解析字符串形式的JSON（飞书可能返回字符串格式的字典）
            try:
                parsed_raw = json.loads(hot_linked_product_raw.replace("'", '"'))
                if isinstance(parsed_raw, dict) and "link_record_ids" in parsed_raw:
                    linked_product_ids = parsed_raw.get("link_record_ids", [])
                else:
                    linked_product_ids.append(hot_linked_product_raw)
            except json.JSONDecodeError:
                linked_product_ids.append(hot_linked_product_raw)
        
        logging.info(f"  解析后的关联产品记录ID: {linked_product_ids}")
        
        # 根据关联产品记录ID匹配产品
        matched_products = products
        matched_product_name = ""
        if linked_product_ids and products:
            # 根据记录ID匹配产品
            matched_products = [p for p in products if p.get("record_id") in linked_product_ids]
            if matched_products:
                matched_product_name = matched_products[0].get("名称", "")
                logging.info(f"  根据记录ID {linked_product_ids} 匹配到产品: {matched_product_name}")
            else:
                # 如果记录ID匹配失败，尝试使用所有产品
                matched_products = products
                logging.info(f"  记录ID {linked_product_ids} 未匹配到产品，使用所有产品")
        
        if not hot_topic_name:
            logging.info("  热点名称为空，跳过")
            continue
        
        # 使用热点的账号获取账号上下文
        hot_account_context = get_account_context(hot_account)
        
        # 构建匹配产品的摘要
        matched_product_summary = ""
        for p in matched_products:
            matched_product_summary += f"- {p.get('名称', '')}（{p.get('分类', '')}类）：材质{p.get('材质', '')}，卖点{p.get('卖点', '')}，{p.get('价格', '')}价位，适合{p.get('人群', '')}人群，{p.get('场景', '')}场景\n"
        if not matched_product_summary:
            matched_product_summary = "无可用产品"
        
        user_prompt = f"""请根据以下信息为指定账号生成3个选题方案：

{hot_account_context}

热点名称：{hot_topic_name}
热点日期：{hot_topic_date}
热点类型：{hot_topic_type if hot_topic_type else '无'}
编辑建议角度：{hot_angles if hot_angles else '无，请自行发挥'}
关联产品：{matched_product_name if matched_product_name else '无特定关联，请从可用产品中选择'}

可用产品列表：
{matched_product_summary}

重要提示：生成的选题标题必须与热点名称和热点日期相关！例如，如果热点是"端午节"，标题必须包含端午相关内容，不能使用其他节日主题。

请直接输出JSON数组，每个选题包含：标题、SOP类型、账号、选题理由、封面方向、标签。"""
        
        sp_template = Template(hot_topic_cfg.get("sp", ""))
        sp_content = sp_template.render({})
        
        response = llm_client.invoke(
            messages=[
                SystemMessage(content=sp_content),
                HumanMessage(content=user_prompt)
            ],
            model=hot_topic_cfg.get("config", {}).get("model", "doubao-seed-2-0-pro-260215"),
            temperature=hot_topic_cfg.get("config", {}).get("temperature", 0.7),
            max_completion_tokens=hot_topic_cfg.get("config", {}).get("max_completion_tokens", 4096)
        )
        
        try:
            content = response.content if hasattr(response, 'content') else str(response)
            logging.info(f"LLM响应内容: {content[:500]}")
            
            # 多策略解析JSON
            topics_data: list = []
            
            # 策略1: 尝试提取完整的JSON数组
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    topics_data = json.loads(json_str)
                    logging.info(f"策略1成功: 解析到 {len(topics_data)} 个选题")
                except json.JSONDecodeError as e:
                    logging.warning(f"策略1失败: {e}")
                    # 策略2: 尝试修复JSON（添加缺失的结束符）
                    try:
                        # 尝试截取到最后一个完整的对象
                        last_brace_pos = json_str.rfind('}')
                        if last_brace_pos > 0:
                            fixed_json = json_str[:last_brace_pos + 1] + ']'
                            topics_data = json.loads(fixed_json)
                            logging.info(f"策略2成功: 解析到 {len(topics_data)} 个选题")
                    except json.JSONDecodeError as e2:
                        logging.error(f"策略2失败: {e2}")
            
            # 策略3: 如果没有找到数组，尝试提取单个JSON对象
            if not topics_data:
                obj_matches = re.findall(r'\{[^{}]*"标题"[^{}]*\}', content, re.DOTALL)
                for obj_str in obj_matches[:3]:
                    try:
                        obj_data = json.loads(obj_str)
                        topics_data.append(obj_data)
                    except:
                        pass
                if topics_data:
                    logging.info(f"策略3成功: 提取到 {len(topics_data)} 个选题对象")
            
            if not topics_data:
                logging.error("所有JSON解析策略都失败")
                continue
            
            for topic_item in topics_data[:3]:
                topic_title = topic_item.get("标题", "")
                topic_sop = topic_item.get("内容栏目", "") or topic_item.get("SOP类型", "")
                topic_reason = topic_item.get("切入角度", "") or topic_item.get("选题理由", "")
                
                # 尝试多种字段名获取封面文案建议
                topic_cover_text = topic_item.get("封面文案建议") or topic_item.get("封面文案") or topic_item.get("封面配文") or ""
                
                # 如果没有封面文案建议，尝试从封面方向字段中提取
                cover_direction_raw = topic_item.get("封面图方向") or topic_item.get("封面方向") or ""
                if not topic_cover_text and cover_direction_raw:
                    # 从封面方向描述中提取配文（如「配文：xxx」或「小字文案：xxx」）
                    cover_match = re.search(r'[「『【"\'《]([^」』】"\'》]{5,20})[」』】"\'》]', cover_direction_raw)
                    if cover_match:
                        topic_cover_text = cover_match.group(1)
                    else:
                        # 尝试匹配 "配文：xxx" 或 "文案：xxx"
                        text_match = re.search(r'(配文|文案|小字)[：:]\s*["\'「『]?([^"\'」』\n]{5,20})', cover_direction_raw)
                        if text_match:
                            topic_cover_text = text_match.group(2)
                
                topic_cover_image = cover_direction_raw
                topic_tags = topic_item.get("预期标签", "") or topic_item.get("标签", "")
                topic_official = topic_item.get("预期@薯", "") or topic_item.get("@薯账号", "") or topic_item.get("适合@的官方账号", "")
                
                # 处理标签格式：飞书多行文本字段需要字符串，而不是数组
                if isinstance(topic_tags, list):
                    topic_tags_str = " ".join(topic_tags)
                else:
                    topic_tags_str = str(topic_tags) if topic_tags else ""
                
                # 处理@薯账号格式：飞书多选字段需要字符串数组
                if isinstance(topic_official, list):
                    topic_official_list = [str(x) for x in topic_official if x]
                elif topic_official and str(topic_official).strip():
                    # 单个字符串，需要拆分
                    topic_official_str = str(topic_official)
                    if "," in topic_official_str or "、" in topic_official_str:
                        topic_official_list = [x.strip() for x in topic_official_str.replace("、", ",").split(",") if x.strip()]
                    else:
                        topic_official_list = [topic_official_str.strip()]
                else:
                    topic_official_list = []
                
                # 如果LLM没有生成@薯账号，根据内容栏目自动添加
                if not topic_official_list and topic_sop:
                    # SOP类型到内容类型的映射
                    sop_to_content_type = {
                        "SOP1热点": "节日热点",
                        "SOP2产品": "家居/空间",
                        "SOP3联动": "家居/空间",
                        "SOP4创意": "普通内容",
                        "SOP5故事": "文化/知识",
                        "SOP6古装剧": "文化/知识",
                        "SOP7工艺": "家具工艺"
                    }
                    content_type = sop_to_content_type.get(topic_sop, "普通内容")
                    topic_official_list = SHU_ACCOUNT_MAP.get(content_type, ["@薯条小助手"])
                
                # 写入选题库（使用正确的飞书字段名）
                new_topic_fields = {
                    "选题标题": topic_title,
                    "内容栏目": topic_sop,
                    "目标账号": publish_account,
                    "切入角度": topic_reason,
                    "封面文案建议": topic_cover_text,
                    "封面图方向": topic_cover_image,
                    "预期标签": topic_tags_str,
                    "选题状态": "通过",  # 自动审核通过
                }
                # 只有有值时才添加预期@薯字段
                if topic_official_list:
                    new_topic_fields["预期@薯"] = topic_official_list
                
                try:
                    logging.info(f"正在写入选题: {topic_title}")
                    writer = FeishuBitableWriter()
                    add_result = writer.add_record(APP_TOKEN, TOPIC_TABLE, new_topic_fields)
                    logging.info(f"飞书写入响应: {add_result.get('code', 'unknown')}")
                    new_record_id = add_result.get("data", {}).get("records", [{}])[0].get("record_id")
                    topic_record_ids.append(new_record_id)
                    
                    # 提取LLM生成的关联产品关键词，如果没有则使用热点的关联产品名称
                    llm_product_keyword = topic_item.get("关联产品关键词", "")
                    topic_product_keyword = llm_product_keyword if llm_product_keyword else matched_product_name
                    
                    generated_topics.append({
                        "record_id": new_record_id,
                        "title": topic_title,
                        "sop": topic_sop,
                        "cover_text": topic_cover_text,  # 封面文案建议
                        "cover_image": topic_cover_image,  # 封面图方向
                        "tags": topic_tags_str,
                        "official": topic_official,
                        # 新增：热点信息和关联产品关键词
                        "hot_topic_name": hot_topic_name,
                        "hot_topic_date": hot_topic_date,
                        "hot_topic_type": hot_topic_type,
                        "product_keyword": topic_product_keyword,
                        "account": hot_account  # 添加账号信息
                    })
                    logging.info(f"选题写入成功: {topic_title}, 关联产品关键词: {topic_product_keyword}")
                except Exception as e:
                    logging.error(f"选题写入失败: {topic_title} - {e}")
        except Exception as e:
            logging.error(f"选题生成失败: {e}")
    
    logging.info(f"📝 步骤1完成: 共生成 {len(generated_topics)} 个选题")
    
    # ========== 步骤2: 生成文案 ==========
    logging.info("✍️ 步骤2: 正在生成文案...")
    
    # 加载选题文案配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_topic_post_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        topic_post_cfg = json.load(f)
    
    generated_contents = []
    
    logging.info(f"准备处理 {len(generated_topics)} 个选题生成文案")
    
    for topic_info in generated_topics:
        topic_record_id = topic_info["record_id"]
        topic_title = topic_info["title"]
        # 获取热点信息和关联产品关键词
        hot_topic_name = topic_info.get("hot_topic_name", "")
        hot_topic_date = topic_info.get("hot_topic_date", "")
        product_keyword = topic_info.get("product_keyword", "")
        topic_account = topic_info.get("account", "")
        logging.info(f"正在为选题生成文案: {topic_title}, 热点: {hot_topic_name}, 关联产品: {product_keyword}, 账号: {topic_account}")
        
        # 根据关联产品关键词匹配产品
        matched_product = None
        if product_keyword and all_products:
            # 尝试精确匹配或部分匹配
            for p in all_products:
                prod_name = p.get("名称", "")
                if product_keyword in prod_name or prod_name in product_keyword:
                    matched_product = p
                    break
            # 如果没有匹配到，使用第一个产品
            if not matched_product:
                matched_product = all_products[0]
        elif all_products:
            matched_product = all_products[0]
        
        # 构建产品信息
        product_info = ""
        matched_product_name = ""
        if matched_product:
            matched_product_name = matched_product.get("名称", "")
            material = matched_product.get("材质", "")
            selling_point = matched_product.get("卖点", "")
            price = matched_product.get("价格", "")
            audience = matched_product.get("人群", "")
            scenario = matched_product.get("场景", "")
            product_info = f"产品名称：{matched_product_name}\n材质：{material}\n卖点：{selling_point}\n价格：{price}\n适合人群：{audience}\n使用场景：{scenario}"
            logging.info(f"使用产品: {matched_product_name}")
        
        account_context = get_account_context(topic_account)
        
        # 构建热点提示（如果有热点信息）
        hot_topic_hint = ""
        if hot_topic_name:
            hot_topic_hint = f"""
【重要】热点信息：
- 热点名称：{hot_topic_name}
- 热点日期：{hot_topic_date}
- 你的文案必须紧扣热点主题"{hot_topic_name}"，标题和正文内容都要与这个热点相关！
- 如果热点是某个节日（如端午节、情人节等），文案内容必须是该节日主题，不能使用其他节日！
"""
        
        user_prompt = f"""请为以下选题生成小红书发布文案：

选题标题：{topic_title}
发布账号：{topic_account}

账号定位参考：
{account_context}

产品信息：
{product_info}
{hot_topic_hint}
请直接输出JSON，包含：标题、正文(300-700字)、封面文案、标签。"""
        
        sp_template = Template(topic_post_cfg.get("sp", ""))
        sp_content = sp_template.render({})
        
        try:
            response = llm_client.invoke(
                messages=[
                    SystemMessage(content=sp_content),
                    HumanMessage(content=user_prompt)
                ],
                model=topic_post_cfg.get("config", {}).get("model", "doubao-seed-2-0-pro-260215"),
                temperature=topic_post_cfg.get("config", {}).get("temperature", 0.7),
                max_completion_tokens=topic_post_cfg.get("config", {}).get("max_completion_tokens", 4096)
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            logging.info(f"LLM返回内容长度: {len(content)} 字符")
            # 解析LLM响应 - 多策略解析
            post_data: dict = {}
            
            # 策略1: 尝试提取完整的JSON对象
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    parsed_json = json.loads(json_str)
                    logging.info(f"JSON解析成功，提取到字段: {list(parsed_json.keys())}")
                    # 从JSON中提取关键字段，处理列表格式
                    # 支持新旧两种字段名
                    title_value = parsed_json.get("发布标题") or parsed_json.get("标题")
                    if title_value:
                        if isinstance(title_value, list) and len(title_value) > 0:
                            post_data["标题"] = title_value[0]
                        else:
                            post_data["标题"] = str(title_value)
                    if parsed_json.get("正文"):
                        body = parsed_json["正文"]
                        # 处理各种异常格式
                        if isinstance(body, dict):
                            nested_body = body.get("正文") or body.get("发布标题", "")
                            post_data["正文"] = str(nested_body) if nested_body else str(body)
                            logging.warning(f"正文是嵌套dict，提取内容: {len(post_data['正文'])} 字符")
                        elif isinstance(body, list) and len(body) > 0:
                            post_data["正文"] = str(body[0])
                        elif isinstance(body, str):
                            # 检测是否是JSON字符串（正文内容被错误地输出为JSON）
                            if body.strip().startswith("{") or body.strip().startswith("["):
                                try:
                                    nested = json.loads(body)
                                    if isinstance(nested, dict):
                                        real_body = nested.get("正文") or nested.get("发布标题", "")
                                        if real_body:
                                            post_data["正文"] = str(real_body)
                                            logging.warning(f"正文是JSON字符串，提取真实正文: {len(post_data['正文'])} 字符")
                                        else:
                                            post_data["正文"] = body
                                    else:
                                        post_data["正文"] = body
                                except json.JSONDecodeError:
                                    post_data["正文"] = body
                            else:
                                post_data["正文"] = body
                        else:
                            post_data["正文"] = str(body)
                        logging.info(f"从JSON提取正文成功，长度: {len(post_data['正文'])} 字符")
                    if parsed_json.get("封面文案"):
                        covers = parsed_json["封面文案"]
                        if isinstance(covers, list) and len(covers) > 0:
                            post_data["封面文案"] = covers[0]
                        else:
                            post_data["封面文案"] = str(covers)
                    tags_value = parsed_json.get("发布标签") or parsed_json.get("标签")
                    if tags_value:
                        if isinstance(tags_value, list):
                            post_data["标签"] = " ".join(tags_value)
                        else:
                            post_data["标签"] = str(tags_value)
                    accounts_value = parsed_json.get("@薯账号") or parsed_json.get("适合@的官方账号")
                    if accounts_value:
                        if isinstance(accounts_value, list):
                            post_data["@官方号"] = " ".join([str(a) for a in accounts_value])
                        else:
                            post_data["@官方号"] = str(accounts_value)
                    if parsed_json.get("评论区引导语"):
                        post_data["评论区引导语"] = str(parsed_json["评论区引导语"])
                except json.JSONDecodeError as e:
                    logging.warning(f"JSON解析失败: {e}")
            
            # 策略2: 如果JSON解析失败或缺少关键字段，尝试从序号格式中提取
            if not post_data or not post_data.get("标题") or not post_data.get("正文"):
                logging.info("尝试策略2: 序号格式解析")
                # 从"一、标题"部分提取标题
                title_section = re.search(r'一、[^\n]*标题[^\n]*\n(.+?)二、', content, re.DOTALL)
                if title_section:
                    titles_text = title_section.group(1).strip()
                    # 提取第一个标题（通常是最推荐的）
                    first_title_match = re.search(r'1\.[^\n]*[:：]?\s*([^\n]+)', titles_text)
                    if first_title_match:
                        post_data["标题"] = first_title_match.group(1).strip()
                    else:
                        # 尝试提取第一行非空内容作为标题
                        title_lines = [l.strip() for l in titles_text.split('\n') if l.strip() and not l.strip().startswith(('种草型', '文化型', '场景型', '礼物型', '评论'))]
                        if title_lines:
                            post_data["标题"] = title_lines[0]
                
                # 从"二、正文"部分提取正文
                body_section = re.search(r'二、[^\n]*正文[^\n]*\n(.+?)三、', content, re.DOTALL)
                if body_section:
                    post_data["正文"] = body_section.group(1).strip()
                    logging.info(f"从序号格式提取正文成功，长度: {len(post_data['正文'])} 字符")
                
                # 从"三、封面文案"部分提取封面文案
                cover_section = re.search(r'三、[^\n]*封面文案[^\n]*\n(.+?)四、', content, re.DOTALL)
                if cover_section:
                    covers_text = cover_section.group(1).strip()
                    # 提取第一个封面文案
                    first_cover_match = re.search(r'1\.[^\n]*[:：]?\s*([^\n]+)', covers_text)
                    if first_cover_match:
                        post_data["封面文案"] = first_cover_match.group(1).strip()
                    else:
                        cover_lines = [l.strip() for l in covers_text.split('\n') if l.strip()]
                        if cover_lines:
                            post_data["封面文案"] = cover_lines[0]
                
                # 从"五、15个小红书标签"部分提取标签
                tags_section = re.search(r'五、[^\n]*标签[^\n]*\n(.+?)六、', content, re.DOTALL)
                if tags_section:
                    tags_text = tags_section.group(1).strip()
                    # 提取所有#标签
                    tags_found = re.findall(r'#\w+', tags_text)
                    if tags_found:
                        post_data["标签"] = " ".join(tags_found)
                
                # 从"六、适合@的官方账号"部分提取@账号
                account_section = re.search(r'六、[^\n]*官方账号[^\n]*\n(.+?)七、', content, re.DOTALL)
                if account_section:
                    accounts_text = account_section.group(1).strip()
                    # 提取@账号
                    accounts_found = re.findall(r'@\w+', accounts_text)
                    if accounts_found:
                        post_data["@官方号"] = " ".join(accounts_found)
            
            # 策略3: 如果正文仍然为空，尝试其他常见格式
            if not post_data.get("正文"):
                logging.info("尝试策略3: 其他格式解析")
                # 尝试匹配 "正文：" 或 "正文:" 格式
                body_direct_match = re.search(r'正文[：:]\s*\n(.+?)(?=封面文案|标签|@|$)', content, re.DOTALL)
                if body_direct_match:
                    post_data["正文"] = body_direct_match.group(1).strip()
                    logging.info(f"从正文直接格式提取成功，长度: {len(post_data['正文'])} 字符")
                
                # 尝试匹配段落格式的正文（连续多行文本）
                if not post_data.get("正文"):
                    # 找到第一个较长的段落（超过100字符）作为正文
                    paragraphs = re.split(r'\n\n+', content)
                    for para in paragraphs:
                        if len(para.strip()) > 100 and not para.strip().startswith(('标题', '封面', '标签', '@', '图片', '#', '【', '一、', '二、', '三、')):
                            post_data["正文"] = para.strip()
                            logging.info(f"从段落格式提取正文成功，长度: {len(post_data['正文'])} 字符")
                            break
            
            # 如果标题为空，尝试从内容开头提取
            if not post_data.get("标题"):
                # 尝试匹配标题格式
                title_match = re.search(r'标题[：:]\s*["\']?([^"\n]{5,50})["\']?', content)
                if title_match:
                    post_data["标题"] = title_match.group(1).strip()
                else:
                    # 使用选题标题作为备选
                    post_data["标题"] = topic_title
            
            post_title = post_data.get("标题", topic_title)
            # 如果标题是列表，取第一个作为发布标题
            if isinstance(post_title, list):
                post_title = post_title[0] if post_title else topic_title
            post_body = post_data.get("正文", "")
            # 如果正文是列表，取第一个
            if isinstance(post_body, list):
                post_body = post_body[0] if post_body else ""
            cover_text = post_data.get("封面文案", "")
            if isinstance(cover_text, list):
                cover_text = cover_text[0] if cover_text else ""
            post_tags = post_data.get("标签", "")
            # 处理标签格式：飞书多行文本字段需要字符串，而不是数组
            if isinstance(post_tags, list):
                post_tags_str = " ".join(post_tags)
            else:
                post_tags_str = str(post_tags) if post_tags else ""
            official_accounts = post_data.get("@官方号", "")
            
            # 如果LLM没有生成封面文案，使用选题的封面文案建议
            if not cover_text:
                cover_text = topic_info.get("cover_text", "")
            
            # 如果LLM没有生成标签，使用选题的预期标签
            if not post_tags_str:
                post_tags_str = topic_info.get("tags", "")
            
            # 如果LLM没有生成@官方号，使用选题的预期@薯
            if not official_accounts:
                official_accounts = topic_info.get("official", "")
            
            # 根据内容类型自动添加薯账号
            content_category = topic_info.get("category", "")  # 内容栏目/SOP类型
            content_style = topic_info.get("content_style", "")  # 内容风格
            
            # 判断内容类型并添加薯账号
            potatoes_added = []
            # 节日热点相关（包含情人节、端午、春节等节日关键词）
            holiday_keywords = ["热点", "节日", "端午", "情人节", "春节", "中秋", "七夕", "元宵", "清明", "重阳", "腊八", "元旦", "五一", "十一", "国庆", "母亲节", "父亲节", "圣诞", "新年"]
            if "热点" in content_category or "热点" in content_style or any(kw in topic_title or kw in post_body for kw in holiday_keywords):
                potatoes_added.extend(POTATO_ACCOUNTS["节日热点"])
            # 家具工艺相关
            if "工艺" in content_category or "工艺" in content_style or "榫卯" in post_body or "打磨" in post_body or "手工" in post_body:
                potatoes_added.extend(POTATO_ACCOUNTS["家具工艺"])
            # 家居空间相关
            if "空间" in topic_title or "茶空间" in topic_title or "家居" in post_body or "家具" in topic_title or "茶桌" in post_body or "书房" in post_body:
                potatoes_added.extend(POTATO_ACCOUNTS["家居/空间"])
            # 文化知识相关
            if "文化" in content_category or "知识" in content_style or "考工记" in post_body or "明式" in post_body or "古典" in post_body or "传统" in post_body:
                potatoes_added.extend(POTATO_ACCOUNTS["文化/知识"])
            # 穿搭饰品相关
            if "穿搭" in content_category or "饰品" in content_category or "手串" in topic_title or "手串" in post_body or "佩戴" in post_body or "搭配" in post_body:
                potatoes_added.extend(POTATO_ACCOUNTS.get("穿搭/饰品", ["@时尚薯", "@穿搭薯"]))
            # 默认添加薯条小助手（普通内容）
            if not potatoes_added:
                potatoes_added.extend(POTATO_ACCOUNTS["普通内容"])
            
            # 合并发布账号、LLM生成的@账号和自动添加的薯账号
            all_accounts = []
            # 添加发布账号
            if topic_account:
                all_accounts.append(f"@{topic_account}")
            # 添加LLM生成的薯账号（去除重复）
            if official_accounts:
                for acc in official_accounts.split():
                    if acc not in all_accounts:
                        all_accounts.append(acc)
            # 添加根据内容类型自动添加的薯账号（去除重复）
            for potato in potatoes_added:
                if potato not in all_accounts:
                    all_accounts.append(potato)
            
            official_accounts = " ".join(all_accounts)
            logging.info(f"薯账号列表: {official_accounts}")
            
            # 暂存文案数据，等图片建议生成后合并写入
            generated_contents.append({
                "title": post_title,
                "body": post_body,
                "cover_text": cover_text,
                "cover_image": topic_info.get("cover_image", ""),  # 封面图方向
                "tags": post_tags_str,
                "official_accounts": official_accounts,
                "publish_account": topic_account,  # 使用选题对应的账号，而不是默认账号
                "topic_record_id": topic_record_id
            })
            logging.info(f"文案生成成功（暂存）: {post_title}, 账号: {topic_account}")
            
        except Exception as e:
            logging.error(f"文案生成失败: {topic_title} - {e}")
    
    logging.info(f"✍️ 步骤2完成: 共生成 {len(generated_contents)} 篇文案")
    
    # ========== 步骤3: 生成图片建议 ==========
    logging.info("📷 步骤3: 正在生成图片建议...")
    
    # 加载图片建议配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_image_suggestion_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        image_cfg = json.load(f)
    
    for content_info in generated_contents:
        content_title = content_info["title"]
        content_body = content_info["body"]
        
        user_prompt = f"""请为以下小红书内容生成图片拍摄建议：

标题：{content_title}
正文：{content_body[:200]}...

请按格式输出纯文本配图方案（不要输出JSON）。"""
        
        sp_template = Template(image_cfg.get("sp", ""))
        sp_content = sp_template.render({})
        
        response = llm_client.invoke(
            messages=[
                SystemMessage(content=sp_content),
                HumanMessage(content=user_prompt)
            ],
            model=image_cfg.get("config", {}).get("model", "doubao-seed-2-0-pro-260215"),
            temperature=image_cfg.get("config", {}).get("temperature", 0.7),
            max_completion_tokens=image_cfg.get("config", {}).get("max_completion_tokens", 4096)
        )
        
        try:
            img_content = response.content if hasattr(response, 'content') else str(response)
            
            # 确保是字符串类型
            if isinstance(img_content, list):
                img_content = str(img_content[0]) if img_content else ""
            
            # LLM 返回的是文本格式（一、二、三...），直接作为图片建议
            suggestion_text = str(img_content).strip()
            
            # 合并正文和图片建议，然后写入飞书表格
            full_body = content_body
            if suggestion_text:
                full_body = content_body + "\n\n📷 图片建议：\n" + suggestion_text
            
            content_info["body_with_image"] = full_body
            content_info["image_suggestion"] = suggestion_text  # 单独存储图片建议，用于输出显示
            
        except Exception as e:
            logging.error(f"图片建议生成失败: {content_title} - {e}")
            content_info["body_with_image"] = content_body
    
    logging.info(f"📷 步骤3完成: 共生成 {len(generated_contents)} 条图片建议")
    
    # ========== 步骤4: 写入飞书表格 ==========
    logging.info("📝 步骤4: 正在写入飞书表格...")
    
    writer4 = FeishuBitableWriter()
    final_contents = []
    
    for content_info in generated_contents:
        try:
            # 使用纯正文（不含图片建议），避免重复
            pure_body = content_info.get("body", "")
            
            # 格式化图片建议（如果是JSON格式则美化输出）
            image_suggestion_raw = content_info.get('image_suggestion', '')
            if isinstance(image_suggestion_raw, dict):
                image_suggestion_str = json.dumps(image_suggestion_raw, ensure_ascii=False, indent=2)
            else:
                image_suggestion_str = str(image_suggestion_raw) if image_suggestion_raw else ''
            
            # 构建内容整理格式的文本（使用安全格式，避免Markdown标题解析）
            content_publish_account = content_info.get("publish_account", publish_account)
            content_organized = f"""标题: {content_info['title']}

正文:
{pure_body}

封面文案: {content_info.get('cover_text', '')}

图片建议:
{image_suggestion_str}

标签: {content_info.get('tags', '')}

官方账号: {content_info.get('official_accounts', content_publish_account)}"""

            # 写入内容成品库（正文字段使用完整内容，包含图片建议）
            body_with_image = content_info.get("body_with_image", content_info.get("body", ""))
            # 使用该文案对应的发布账号，而不是外层变量
            content_publish_account = content_info.get("publish_account", publish_account)
            new_content_fields = {
                "发布标题": content_info["title"],
                "正文": body_with_image,
                "发布标签": content_info.get("tags", ""),
                "发布账号": content_publish_account,
                "@薯账号": content_info.get("official_accounts", ""),
                "风险审核结果": "待审核",
                "关联选题": [content_info.get("topic_record_id")],
                "内容整理": content_organized  # 写入内容整理字段
            }
            
            logging.info(f"正在写入: {content_info['title']}")
            add_result = writer4.add_record(APP_TOKEN, CONTENT_TABLE, new_content_fields)
            
            if add_result.get('code') == 0:
                content_record_id = add_result.get("data", {}).get("records", [{}])[0].get("record_id")
                content_info["record_id"] = content_record_id
                final_contents.append(content_info)
                logging.info(f"✓ 写入成功: {content_info['title']}")
            else:
                logging.error(f"✗ 写入失败: {content_info['title']} - {add_result.get('msg', 'unknown')}")
                
        except Exception as e:
            logging.error(f"写入失败: {content_info['title']} - {e}")
    
    logging.info(f"📝 步骤4完成: 共写入 {len(final_contents)} 条内容")
    
    # ========== 从飞书表格读取"内容整理"字段作为最终成品 ==========
    logging.info("📖 步骤5: 从飞书表格读取内容整理字段...")
    
    # 构建最终结果文本
    result_text = f"🎉 一键生成完成！\n\n"
    result_text += f"📊 统计：\n"
    result_text += f"  • 生成选题：{len(generated_topics)} 条\n"
    result_text += f"  • 生成文案：{len(final_contents)} 篇（已写入飞书）\n\n"
    
    if final_contents:
        result_text += f"📝 最终成品（从飞书表格内容整理字段读取）：\n"
        result_text += "=" * 50 + "\n"
        
        # 收集所有记录ID，使用批量获取方法
        content_record_ids = [c.get("record_id", "") for c in final_contents if c.get("record_id")]
        
        if content_record_ids:
            try:
                # 使用已有的 writer4 的 list_records 方法批量获取记录
                records_response = writer4.list_records(
                    app_token=APP_TOKEN,
                    table_id=CONTENT_TABLE,
                    record_ids=content_record_ids
                )
                
                if records_response.get('code') == 0:
                    records = records_response.get('data', {}).get('records', [])
                    for i, record in enumerate(records, 1):
                        fields = record.get('fields', {})
                        # 读取飞书表格中的"内容整理"字段
                        content_organized_raw = fields.get('内容整理', '')
                        
                        # 解析飞书多行文本格式: [{'text': '内容', 'type': 'text'}]
                        content_organized_from_feishu = ""
                        if content_organized_raw:
                            if isinstance(content_organized_raw, list):
                                # 飞书多行文本字段返回列表格式
                                for item in content_organized_raw:
                                    if isinstance(item, dict) and 'text' in item:
                                        content_organized_from_feishu += item.get('text', '')
                            elif isinstance(content_organized_raw, str):
                                content_organized_from_feishu = content_organized_raw
                        
                        if content_organized_from_feishu:
                            result_text += f"\n【第{i}篇】\n"
                            result_text += content_organized_from_feishu
                            result_text += "\n" + "=" * 50 + "\n"
                            logging.info(f"✓ 读取成功: 第{i}篇内容整理")
                        else:
                            # 如果没有内容整理字段，使用原始数据构建
                            content_info = final_contents[i-1] if i <= len(final_contents) else {}
                            logging.warning(f"⚠ 第{i}篇内容整理字段为空，使用原始数据")
                            result_text += f"\n【第{i}篇】\n"
                            result_text += f"""【标题】{content_info.get('title', '')}

【正文】
{content_info.get('body', '')}

【封面文案】{content_info.get('cover_text', '')}

【图片建议】
{content_info.get('image_suggestion', '')}

【标签】{content_info.get('tags', '')}

【@官方号】{content_info.get('official_accounts', '')}
"""
                            result_text += "\n" + "=" * 50 + "\n"
                else:
                    logging.error(f"✗ 批量获取飞书记录失败: {records_response.get('msg', 'unknown')}")
                    # 失败时使用原始数据
                    for i, content_info in enumerate(final_contents, 1):
                        result_text += f"\n【第{i}篇】\n"
                        result_text += f"""【标题】{content_info.get('title', '')}

【正文】
{content_info.get('body', '')}

【封面文案】{content_info.get('cover_text', '')}

【图片建议】
{content_info.get('image_suggestion', '')}

【标签】{content_info.get('tags', '')}

【@官方号】{content_info.get('official_accounts', '')}
"""
                        result_text += "\n" + "=" * 50 + "\n"
            except Exception as e:
                logging.error(f"✗ 读取飞书记录异常: {e}")
                # 异常时使用原始数据
                for i, content_info in enumerate(final_contents, 1):
                    result_text += f"\n【第{i}篇】\n"
                    result_text += f"""【标题】{content_info.get('title', '')}

【正文】
{content_info.get('body', '')}

【封面文案】{content_info.get('cover_text', '')}

【图片建议】
{content_info.get('image_suggestion', '')}

【标签】{content_info.get('tags', '')}

【@官方号】{content_info.get('official_accounts', '')}
"""
                    result_text += "\n" + "=" * 50 + "\n"
    
    return WorkflowOutput(
        workflow_type="一键生成",
        result=result_text,
        processed_count=len(generated_topics),
        success_count=len(final_contents)
    )


# ============================================
# 条件路由 & 图构建
# ============================================
def route_workflow(state: WorkflowInput) -> str:
    """根据workflow_type路由到对应的工作流节点"""
    return state.workflow_type


builder = StateGraph(
    GlobalState,
    input_schema=WorkflowInput,
    output_schema=WorkflowOutput
)

builder.add_node("一键生成", one_click_generate_workflow_node)
builder.add_node("热点选题", feishu_hot_topic_workflow_node, metadata={"type":"agent", "llm_cfg":"config/feishu_hot_topic_cfg.json"})
builder.add_node("选题文案", feishu_topic_post_workflow_node, metadata={"type":"agent", "llm_cfg":"config/feishu_topic_post_cfg.json"})
builder.add_node("客户故事", feishu_customer_story_workflow_node, metadata={"type":"agent", "llm_cfg":"config/feishu_customer_story_cfg.json"})
builder.add_node("图片建议", feishu_image_suggestion_workflow_node, metadata={"type":"agent", "llm_cfg":"config/feishu_image_suggestion_cfg.json"})
builder.add_node("数据复盘", feishu_weekly_review_workflow_node, metadata={"type":"agent", "llm_cfg":"config/feishu_weekly_review_cfg.json"})
builder.add_node("内容整理", feishu_content_organize_workflow_node)

builder.add_conditional_edges(
    source="__start__",
    path=route_workflow,
    path_map={
        "一键生成": "一键生成",
        "热点选题": "热点选题",
        "选题文案": "选题文案",
        "客户故事": "客户故事",
        "图片建议": "图片建议",
        "数据复盘": "数据复盘",
        "内容整理": "内容整理"
    }
)

builder.add_edge("一键生成", END)
builder.add_edge("热点选题", END)
builder.add_edge("选题文案", END)
builder.add_edge("客户故事", END)
builder.add_edge("图片建议", END)
builder.add_edge("数据复盘", END)
builder.add_edge("内容整理", END)

main_graph = builder.compile()
