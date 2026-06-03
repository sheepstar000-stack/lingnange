"""
小红书内容生成系统 - 飞书自动化工作流
包含5个飞书自动化工作流，实现从飞书读取→LLM生成→写入飞书的完整流程
"""

import os
import re
import json
import requests
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
from graphs.nodes.feishu_write_node import feishu_write_node


# ============================================
# 配置加载辅助函数
# ============================================
def load_llm_config(config_path: str) -> Dict[str, Any]:
    """加载LLM配置文件"""
    full_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH", ""), config_path)
    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================
# 统一入参定义
# ============================================
class WorkflowInput(BaseModel):
    """工作流统一输入参数"""
    workflow_type: Literal["feishu_hot_topic", "feishu_topic_post", "feishu_customer_story", "feishu_image_suggestion", "feishu_weekly_review"] = Field(
        ...,
        description="工作流类型：feishu_hot_topic(飞书热点选题)、feishu_topic_post(飞书选题文案)、feishu_customer_story(飞书客户故事)、feishu_image_suggestion(飞书图片建议)、feishu_weekly_review(飞书数据复盘)"
    )
    
    # 飞书通用参数
    feishu_app_token: str = Field(default="FoWqb7NLuah1gdssEHbc7Wk9nQh", description="飞书多维表格的app_token")
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


class WorkflowOutput(BaseModel):
    """工作流统一输出"""
    workflow_type: str = Field(..., description="执行的工作流类型")
    result: str = Field(..., description="生成结果")
    processed_count: int = Field(default=0, description="处理记录数")
    success_count: int = Field(default=0, description="成功写入数")


# ============================================
# 飞书工作流输出定义
# ============================================
class FeishuWorkflowOutput(BaseModel):
    """飞书工作流输出"""
    workflow_type: str = Field(..., description="工作流类型")
    result: str = Field(..., description="处理结果")
    processed_count: int = Field(default=0, description="处理记录数")
    success_count: int = Field(default=0, description="成功写入数")


# ============================================
# 工具函数
# ============================================
def extract_feishu_field(fields: dict, field_name: str) -> str:
    """
    从飞书字段值中提取文本内容
    fields: 包含所有字段的字典
    field_name: 要提取的字段名
    飞书字段格式通常是: [{'text': '内容', 'type': 'text'}]
    """
    field_value = fields.get(field_name) if fields else None
    if field_value is None:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, list):
        texts = []
        for item in field_value:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            elif isinstance(item, str):
                texts.append(item)
        return "".join(texts)
    return str(field_value)


# ============================================
# 工作流①：热点选题（飞书版）
# 从热点日历库+产品库读取 → 生成选题 → 写入选题库
# ============================================
def feishu_hot_topic_workflow_node(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 飞书热点选题工作流
    desc: 从热点日历库+产品库读取数据，生成选题，写入选题库
    integrations: 飞书多维表格, 大语言模型
    """
    # 步骤1: 读取热点日历库
    hot_calendar_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_hot_calendar_table_id,
        filter_field="状态",
        filter_value="待准备",
        page_size=5
    )
    hot_calendar_output = feishu_read_node(hot_calendar_input, config, runtime)
    
    if hot_calendar_output.record_count == 0:
        return FeishuWorkflowOutput(
            workflow_type="feishu_hot_topic",
            result="没有找到待处理的热点",
            processed_count=0,
            success_count=0
        )
    
    # 步骤2: 读取产品素材库
    product_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_product_table_id,
        filter_field="产品状态",
        filter_value="可发布",
        page_size=10
    )
    product_output = feishu_read_node(product_input, config, runtime)
    
    # 提取产品信息
    products = []
    for record in product_output.records:
        fields = record.get("fields", {})
        product_name = extract_feishu_field(fields, "产品名称")
        selling_point = extract_feishu_field(fields, "核心卖点")
        if product_name:
            products.append(f"{product_name}+{selling_point}" if selling_point else product_name)
    
    available_products = "，".join(products)
    
    # 步骤3: 处理热点生成选题
    success_count = 0
    results = []
    
    if hot_calendar_output.records:
        record = hot_calendar_output.records[0]
        fields = record.get("fields", {})
        hot_record_id = record.get("record_id", "")
        
        hot_topic_name = extract_feishu_field(fields, "热点名称")
        hot_topic_date = extract_feishu_field(fields, "热点日期")
        account = extract_feishu_field(fields, "适合账号") or state.publish_account
        
        if hot_topic_name:
            # 加载配置文件
            cfg = load_llm_config("config/feishu_hot_topic_cfg.json")
            sp = cfg.get("sp", "")
            up_template = cfg.get("up", "")
            
            # 渲染用户提示词
            up = Template(up_template).render(
                hot_topic_name=hot_topic_name,
                hot_topic_date=hot_topic_date,
                available_products=available_products,
                target_audience=state.target_audience,
                content_style=state.content_style,
                account=account
            )
            
            # 调用LLM生成选题
            llm_client = LLMClient()
            llm_config = cfg.get("config", {})
            response = llm_client.invoke(
                messages=[
                    SystemMessage(content=sp),
                    HumanMessage(content=up)
                ],
                model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
                temperature=llm_config.get("temperature", 0.7),
                max_completion_tokens=llm_config.get("max_completion_tokens", 4096)
            )
            topic_content = response.content if isinstance(response.content, str) else str(response.content)
            
            # 写入选题库
            write_input = FeishuWriteInput(
                app_token=state.feishu_app_token,
                table_id=state.feishu_topic_table_id,
                record_id="",
                fields={
                    "选题标题": hot_topic_name,
                    "切入角度": topic_content,
                    "目标账号": account,
                    "关联热点": [hot_record_id] if hot_record_id else [],
                    "选题状态": "待审核"
                }
            )
            write_output = feishu_write_node(write_input, config, runtime)
            
            if write_output.success:
                success_count += 1
                results.append(f"✓ {hot_topic_name} 选题已生成并写入")
            else:
                results.append(f"✗ {hot_topic_name} 写入失败: {write_output.message}")
    
    return FeishuWorkflowOutput(
        workflow_type="feishu_hot_topic",
        result="\n".join(results),
        processed_count=hot_calendar_output.record_count,
        success_count=success_count
    )


# ============================================
# 工作流②：产品文案（飞书版）
# 从选题库读取 → 读取产品素材库 → 生成文案 → 写入内容成品库
# ============================================
def feishu_topic_post_workflow_node(
    state: FeishuTopicPostInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 飞书产品文案工作流
    desc: 从选题库读取通过的选题→读取产品素材→生成文案→写入内容库
    integrations: 飞书多维表格, 大语言模型
    """
    ctx = runtime.context
    
    app_token = state.feishu_app_token
    topic_table_id = state.feishu_topic_table_id
    product_table_id = state.feishu_product_table_id
    content_table_id = state.feishu_content_table_id
    filter_status = getattr(state, 'filter_status', '通过') or '通过'
    
    results = []
    success_count = 0
    
    # 1. 读取选题库
    topic_input = FeishuReadInput(
        app_token=app_token,
        table_id=topic_table_id,
        filter_field="选题状态",
        filter_value=filter_status,
        page_size=1
    )
    topic_output = feishu_read_node(topic_input, config, runtime)
    
    if not topic_output.records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_topic_post",
            result="没有找到待处理的选题记录"
        )
    
    # 2. 读取产品素材库
    product_input = FeishuReadInput(
        app_token=app_token,
        table_id=product_table_id,
        filter_field="",
        filter_value="",
        page_size=20
    )
    product_output = feishu_read_node(product_input, config, runtime)
    
    # 构建产品信息映射
    product_map = {}
    for p in product_output.records:
        fields = p.get("fields", {})
        product_name = extract_feishu_field(fields, "产品名称")
        if product_name:
            product_map[product_name] = {
                "材质": extract_feishu_field(fields, "材质说明"),
                "卖点": extract_feishu_field(fields, "核心卖点"),
                "场景": extract_feishu_field(fields, "使用场景"),
                "价格": extract_feishu_field(fields, "价格区间"),
                "人群": extract_feishu_field(fields, "适合人群")
            }
    
    # 3. 处理选题记录
    for topic_record in topic_output.records:
        topic_fields = topic_record.get("fields", {})
        topic_title = extract_feishu_field(topic_fields, "选题标题")
        topic_angle = extract_feishu_field(topic_fields, "切入角度")
        account = extract_feishu_field(topic_fields, "目标账号") or "灵楠阁品牌号"
        
        # 获取关联产品
        linked_products = topic_fields.get("关联产品", [])
        product_info = ""
        if linked_products and isinstance(linked_products, list):
            for lp in linked_products:
                if isinstance(lp, dict):
                    prod_name = lp.get("text", "")
                    if prod_name in product_map:
                        p = product_map[prod_name]
                        product_info = f"{prod_name}，材质：{p['材质']}，卖点：{p['卖点']}，场景：{p['场景']}"
                        break
        
        if not product_info:
            product_info = "金丝楠木手串，温润细腻，适合日常佩戴"
        
        # 4. 加载配置并调用LLM生成文案
        cfg = load_llm_config("config/feishu_topic_post_cfg.json")
        sp = cfg.get("sp", "")
        up_template = cfg.get("up", "")
        
        up = Template(up_template).render(
            topic_angle=topic_angle,
            product_info=product_info,
            account=account
        )
        
        llm_client = LLMClient(ctx=ctx)
        llm_config = cfg.get("config", {})
        response = llm_client.invoke(
            messages=[
                SystemMessage(content=sp),
                HumanMessage(content=up)
            ],
            model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
            temperature=llm_config.get("temperature", 0.7),
            max_completion_tokens=llm_config.get("max_completion_tokens", 4096)
        )
        
        content_result = response.content if isinstance(response.content, str) else str(response.content)
        
        # 解析文案内容
        title_match = re.search(r'1\.\s*种草型[：:]\s*(.+)', content_result)
        post_title = title_match.group(1).strip() if title_match else topic_title
        
        body_match = re.search(r'二、正文[^\n]*\n(.+?)(?=\n三、)', content_result, re.DOTALL)
        post_body = body_match.group(1).strip() if body_match else content_result[:500]
        
        tags_match = re.search(r'四、标签[^\n]*\n(.+?)(?=\n五、)', content_result, re.DOTALL)
        post_tags = tags_match.group(1).strip() if tags_match else ""
        
        # 5. 写入内容成品库
        write_input = FeishuWriteInput(
            app_token=app_token,
            table_id=content_table_id,
            fields={
                "发布标题": post_title,
                "正文": post_body,
                "内容栏目": "产品种草",
                "发布账号": account,
                "发布标签": post_tags,
                "发布状态": "待审核"
            }
        )
        write_output = feishu_write_node(write_input, config, runtime)
        
        if write_output.success:
            success_count += 1
            results.append(f"✓ {post_title} 文案已生成并写入")
        else:
            results.append(f"✗ {post_title} 写入失败: {write_output.message}")
    
    return FeishuWorkflowOutput(
        workflow_type="feishu_topic_post",
        result="\n".join(results) if results else "没有处理任何选题",
        processed_count=topic_output.record_count,
        success_count=success_count
    )


# ============================================
# 工作流③：客户故事（手动输入 → 写入内容库）
# ============================================
class FeishuCustomerStoryInput(BaseModel):
    """客户故事工作流输入"""
    workflow_type: str = Field(default="feishu_customer_story", description="工作流类型")
    feishu_app_token: str = Field(..., description="飞书多维表格app_token")
    feishu_content_table_id: str = Field(..., description="内容成品库table_id")
    customer_background: str = Field(..., description="客户背景")
    purchased_product: str = Field(..., description="购买产品")
    purchase_reason: str = Field(..., description="购买原因")
    usage_scenario: str = Field(..., description="使用场景")
    customer_feedback: str = Field(..., description="客户反馈")
    account: str = Field(default="灵楠阁品牌号", description="发布账号")


def feishu_customer_story_workflow_node(
    state: FeishuCustomerStoryInput, 
    config: RunnableConfig, 
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 客户故事生成器
    desc: 根据手动输入的客户信息生成故事文案，写入内容成品库
    integrations: 大语言模型, 飞书多维表格
    """
    results = []
    
    # 加载配置文件
    cfg = load_llm_config("config/feishu_customer_story_cfg.json")
    sp = cfg.get("sp", "")
    up_template = cfg.get("up", "")
    
    # 渲染用户提示词
    up = Template(up_template).render(
        customer_background=state.customer_background,
        purchased_product=state.purchased_product,
        purchase_reason=state.purchase_reason,
        usage_scenario=state.usage_scenario,
        customer_feedback=state.customer_feedback,
        account=state.account
    )
    
    # 调用LLM
    llm_client = LLMClient()
    llm_config = cfg.get("config", {})
    llm_result = llm_client.invoke(
        messages=[
            SystemMessage(content=sp),
            HumanMessage(content=up)
        ],
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.7),
        max_completion_tokens=llm_config.get("max_completion_tokens", 4096)
    )
    
    content = llm_result.content if isinstance(llm_result.content, str) else str(llm_result.content)
    
    # 解析输出
    post_title = ""
    titles = re.findall(r"1\.\s*(?:情绪型|故事型|产品亮点型|文化型|反转型)?[:：]?\s*(.+)", content)
    if titles:
        post_title = titles[0].strip()
    if not post_title:
        post_title = f"{state.customer_background}的{state.purchased_product}故事"
    
    # 提取正文
    body_match = re.search(r"二[、\.．]\s*正文[^国]*?(?=三[、\.．]|$)", content, re.DOTALL)
    post_body = body_match.group(0).replace("二、正文", "").strip() if body_match else content[:500]
    
    # 提取标签
    tags_match = re.search(r"四[、\.．]\s*[^国]*?(?=五[、\.．]|$)", content, re.DOTALL)
    post_tags = ""
    if tags_match:
        tags_text = tags_match.group(0)
        post_tags = "\n".join(re.findall(r"#\S+", tags_text))
    
    # 写入飞书内容库
    write_input = FeishuWriteInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_content_table_id,
        record_id="",
        fields={
            "发布标题": post_title,
            "正文": post_body,
            "内容栏目": "SOP5故事",
            "发布账号": state.account,
            "发布标签": post_tags,
            "发布状态": "待审核"
        }
    )
    write_output = feishu_write_node(write_input, config, runtime)
    
    if write_output.success:
        results.append(f"✓ {post_title} 客户故事已生成并写入")
    else:
        results.append(f"✗ {post_title} 写入失败: {write_output.message}")
    
    return FeishuWorkflowOutput(
        workflow_type="feishu_customer_story",
        result="\n".join(results),
        processed_count=1,
        success_count=1 if write_output.success else 0
    )


# ============================================
# 工作流④：图片建议（读内容库 → 更新内容库）
# ============================================
def feishu_image_suggestion_workflow_node(
    state: FeishuImageSuggestionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 飞书图片建议工作流
    desc: 从内容成品库读取待配图内容，生成图片建议，更新内容库
    integrations: 飞书多维表格, 大语言模型
    """
    # 获取飞书访问令牌
    client = Client()
    access_token = client.get_integration_credential("integration-feishu-base")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    base_url = "https://open.larkoffice.com/open-apis"
    
    # 1. 从内容成品库读取待审核的内容
    search_url = f"{base_url}/bitable/v1/apps/{state.feishu_app_token}/tables/{state.feishu_content_table_id}/records/search"
    search_body = {
        "filter": {
            "conditions": [{"field_name": "发布状态", "operator": "is", "value": ["待审核"]}],
            "conjunction": "and"
        },
        "page_size": 1
    }
    
    search_resp = requests.post(search_url, headers=headers, json=search_body)
    search_data = search_resp.json()
    
    if search_data.get("code") != 0:
        return FeishuWorkflowOutput(
            workflow_type="feishu_image_suggestion",
            result=f"查询失败: {search_data.get('msg', '')}",
            processed_count=0,
            success_count=0
        )
    
    content_records = search_data.get("data", {}).get("items", [])
    if not content_records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_image_suggestion",
            result="没有找到待配图的内容记录",
            processed_count=0,
            success_count=0
        )
    
    content_record = content_records[0]
    content_fields = content_record.get("fields", {})
    content_record_id = content_record.get("record_id", "")
    post_title = extract_feishu_field(content_fields, "发布标题")
    content_body = extract_feishu_field(content_fields, "正文")
    
    # 2. 加载配置并生成图片建议
    cfg = load_llm_config("config/feishu_image_suggestion_cfg.json")
    sp = cfg.get("sp", "")
    up_template = cfg.get("up", "")
    
    up = Template(up_template).render(
        post_title=post_title,
        content_summary=content_body[:200] if content_body else ""
    )
    
    llm_client = LLMClient()
    llm_config = cfg.get("config", {})
    llm_result = llm_client.invoke(
        messages=[
            SystemMessage(content=sp),
            HumanMessage(content=up)
        ],
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.7),
        max_completion_tokens=llm_config.get("max_completion_tokens", 4096)
    )
    image_suggestion = llm_result.content if isinstance(llm_result.content, str) else str(llm_result)
    
    # 3. 更新内容成品库
    update_url = f"{base_url}/bitable/v1/apps/{state.feishu_app_token}/tables/{state.feishu_content_table_id}/records/batch_update"
    update_body = {
        "records": [{
            "record_id": content_record_id,
            "fields": {
                "正文": content_body + f"\n\n---\n**图片建议**：\n{image_suggestion}"
            }
        }]
    }
    
    update_resp = requests.post(update_url, headers=headers, json=update_body)
    update_data = update_resp.json()
    
    if update_data.get("code") == 0:
        return FeishuWorkflowOutput(
            workflow_type="feishu_image_suggestion",
            result=f"✓ {post_title} 图片建议已更新",
            processed_count=1,
            success_count=1
        )
    else:
        return FeishuWorkflowOutput(
            workflow_type="feishu_image_suggestion",
            result=f"✗ {post_title} 更新失败: {update_data.get('msg', '')}",
            processed_count=1,
            success_count=0
        )


# ============================================
# 工作流⑤：数据复盘（读取数据 → 分析 → 写入选题建议）
# ============================================
def feishu_weekly_review_workflow_node(
    state: FeishuWeeklyReviewInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 飞书数据复盘
    desc: 从飞书数据复盘表读取本周数据，生成分析报告和下周选题建议
    integrations: 飞书多维表格
    """
    # 获取访问令牌
    client = Client()
    access_token = client.get_integration_credential("integration-feishu-base")
    
    # 构建请求头
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # 读取数据复盘表
    search_url = f"https://open.larkoffice.com/open-apis/bitable/v1/apps/{state.feishu_app_token}/tables/{state.feishu_review_table_id}/records/search"
    search_body = {"page_size": 10}
    
    search_resp = requests.post(search_url, headers=headers, json=search_body)
    search_data = search_resp.json()
    
    if search_data.get("code") != 0:
        list_url = f"https://open.larkoffice.com/open-apis/bitable/v1/apps/{state.feishu_app_token}/tables/{state.feishu_review_table_id}/records"
        list_resp = requests.get(list_url, headers=headers, params={"page_size": 10})
        search_data = list_resp.json()
        
        if search_data.get("code") != 0:
            return FeishuWorkflowOutput(
                workflow_type="feishu_weekly_review",
                result=f"读取数据复盘表失败: {search_data.get('msg', '')}",
                processed_count=0,
                success_count=0
            )
        records = search_data.get("data", {}).get("items", [])
    else:
        records = search_data.get("data", {}).get("items", [])
    
    if not records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_weekly_review",
            result="没有找到待复盘的记录",
            processed_count=0,
            success_count=0
        )
    
    # 格式化周数据
    weekly_data_lines = []
    for record in records:
        fields = record.get("fields", {})
        post_title = extract_feishu_field(fields, "发布标题")
        account = extract_feishu_field(fields, "发布账号")
        likes = extract_feishu_field(fields, "点赞数")
        collects = extract_feishu_field(fields, "收藏数")
        comments = extract_feishu_field(fields, "评论数")
        dms = extract_feishu_field(fields, "私信数")
        
        weekly_data_lines.append(f"- {post_title} | {account} | 点赞{likes} 收藏{collects} 评论{comments} 私信{dms}")
    
    weekly_data_str = "\n".join(weekly_data_lines)
    
    # 加载配置并调用LLM生成分析报告
    cfg = load_llm_config("config/feishu_weekly_review_cfg.json")
    sp = cfg.get("sp", "")
    up_template = cfg.get("up", "")
    
    up = Template(up_template).render(
        weekly_data=weekly_data_str
    )
    
    llm_client = LLMClient()
    llm_config = cfg.get("config", {})
    response = llm_client.invoke(
        messages=[
            SystemMessage(content=sp),
            HumanMessage(content=up)
        ],
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.7),
        max_completion_tokens=llm_config.get("max_completion_tokens", 4096)
    )
    result = response.content if isinstance(response.content, str) else str(response.content)
    
    return FeishuWorkflowOutput(
        workflow_type="feishu_weekly_review",
        result=f"✓ 数据复盘已完成，共分析{len(records)}条记录\n\n分析结果：\n{result}",
        processed_count=len(records),
        success_count=1
    )


# ============================================
# 条件路由函数
# ============================================
def route_workflow(state: WorkflowInput) -> str:
    """根据workflow_type路由到对应的工作流节点"""
    return state.workflow_type


# ============================================
# 构建主图
# ============================================
builder = StateGraph(
    GlobalState,
    input_schema=WorkflowInput,
    output_schema=WorkflowOutput
)

# 添加飞书自动化工作流节点
builder.add_node("feishu_hot_topic", feishu_hot_topic_workflow_node)
builder.add_node("feishu_topic_post", feishu_topic_post_workflow_node)
builder.add_node("feishu_customer_story", feishu_customer_story_workflow_node)
builder.add_node("feishu_image_suggestion", feishu_image_suggestion_workflow_node)
builder.add_node("feishu_weekly_review", feishu_weekly_review_workflow_node)

# 添加条件边作为入口
builder.add_conditional_edges(
    source="__start__",
    path=route_workflow,
    path_map={
        "feishu_hot_topic": "feishu_hot_topic",
        "feishu_topic_post": "feishu_topic_post",
        "feishu_customer_story": "feishu_customer_story",
        "feishu_image_suggestion": "feishu_image_suggestion",
        "feishu_weekly_review": "feishu_weekly_review"
    }
)

# 所有节点都直接结束
builder.add_edge("feishu_hot_topic", END)
builder.add_edge("feishu_topic_post", END)
builder.add_edge("feishu_customer_story", END)
builder.add_edge("feishu_image_suggestion", END)
builder.add_edge("feishu_weekly_review", END)

# 编译图
main_graph = builder.compile()
