"""
小红书内容生成系统 - 主图编排
包含5个独立的工作流，可通过workflow_type参数选择调用
支持飞书多维表格读取和写入（方案C）
"""

import re
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import (
    GlobalState,
    HotTopicInput,
    ProductPostInput,
    CustomerStoryInput,
    ImageSuggestionInput,
    WeeklyReviewInput,
    FeishuReadInput,
    FeishuWriteInput,
    FeishuHotTopicInput,
    FeishuTopicPostInput,
    FeishuTopicPostOutput,
    FeishuImageSuggestionInput,
)

from graphs.nodes.hot_topic_generator_node import hot_topic_generator_node
from graphs.nodes.product_post_generator_node import product_post_generator_node
from graphs.nodes.customer_story_generator_node import customer_story_generator_node
from graphs.nodes.image_suggestion_node import image_suggestion_node
from graphs.nodes.weekly_review_node import weekly_review_node
from graphs.nodes.feishu_read_node import feishu_read_node
from graphs.nodes.feishu_write_node import feishu_write_node


# ============================================
# 统一入参定义
# ============================================
class WorkflowInput(BaseModel):
    """工作流统一输入参数"""
    workflow_type: Literal["hot_topic", "product_post", "customer_story", "image_suggestion", "weekly_review", "feishu_product", "feishu_hot_topic", "feishu_topic_post", "feishu_customer_story", "feishu_image_suggestion"] = Field( 
        ..., 
        description="工作流类型：hot_topic(热点选题)、product_post(产品文案)、customer_story(客户故事)、image_suggestion(图片建议)、weekly_review(数据复盘)、feishu_product(飞书产品文案)、feishu_hot_topic(飞书热点选题)、feishu_topic_post(飞书选题文案)、feishu_customer_story(飞书客户故事)" 
    )
    
    # 热点选题生成器参数
    hot_topic_name: str = Field(default="", description="热点名称")
    hot_topic_date: str = Field(default="", description="热点日期")
    account: str = Field(default="", description="发布账号")
    available_products: str = Field(default="", description="可用产品")
    target_audience: str = Field(default="", description="目标人群")
    content_style: str = Field(default="", description="内容风格")
    
    # 产品发布文案生成器参数
    product_name: str = Field(default="", description="产品名称")
    product_material: str = Field(default="", description="产品材质")
    product_selling_points: str = Field(default="", description="产品卖点")
    suitable_scenarios: str = Field(default="", description="适合场景")
    price_range: str = Field(default="", description="价格区间")
    reference_copy: str = Field(default="", description="参考文案")
    publish_account: str = Field(default="", description="发布账号")
    
    # 客户故事生成器参数
    customer_background: str = Field(default="", description="客户背景")
    purchased_product: str = Field(default="", description="购买产品")
    purchase_reason: str = Field(default="", description="购买原因")
    usage_scenario: str = Field(default="", description="使用场景")
    customer_feedback: str = Field(default="", description="客户反馈")
    
    # 图片建议器参数
    image_description: str = Field(default="", description="图片描述")
    content_theme: str = Field(default="", description="内容主题")
    
    # 数据复盘器参数
    weekly_data: str = Field(default="", description="本周数据")
    last_week_data: str = Field(default="", description="上周数据")
    
    # 飞书集成参数
    feishu_app_token: str = Field(default="", description="飞书多维表格的app_token")
    feishu_table_id: str = Field(default="", description="飞书产品数据表的table_id")
    feishu_content_table_id: str = Field(default="", description="飞书内容输出表的table_id")
    feishu_filter_field: str = Field(default="处理状态", description="飞书筛选字段名")
    feishu_filter_value: str = Field(default="待处理", description="飞书筛选字段值")
    
    # 飞书热点选题参数
    feishu_hot_calendar_table_id: str = Field(default="tblT1KM0397UcGeM", description="热点日历表table_id")
    feishu_product_table_id: str = Field(default="tbllExTlKURFJP2j", description="产品素材表table_id")
    feishu_topic_table_id: str = Field(default="tblJNjx74uZ3s1vs", description="选题库table_id")


class WorkflowOutput(BaseModel):
    """工作流统一输出"""
    workflow_type: str = Field(..., description="执行的工作流类型")
    result: str = Field(..., description="生成结果")


# ============================================
# 入口节点输入输出定义
# ============================================
class EntryNodeInput(BaseModel):
    """入口节点输入 - 使用统一入参"""
    workflow_type: str = Field(default="", description="工作流类型")
    hot_topic_name: str = Field(default="", description="热点名称")
    hot_topic_date: str = Field(default="", description="热点日期")
    account: str = Field(default="", description="发布账号")
    available_products: str = Field(default="", description="可用产品")
    target_audience: str = Field(default="", description="目标人群")
    content_style: str = Field(default="", description="内容风格")
    product_name: str = Field(default="", description="产品名称")
    product_material: str = Field(default="", description="产品材质")
    product_selling_points: str = Field(default="", description="产品卖点")
    suitable_scenarios: str = Field(default="", description="适合场景")
    price_range: str = Field(default="", description="价格区间")
    reference_copy: str = Field(default="", description="参考文案")
    publish_account: str = Field(default="", description="发布账号")
    customer_background: str = Field(default="", description="客户背景")
    purchased_product: str = Field(default="", description="购买产品")
    purchase_reason: str = Field(default="", description="购买原因")
    usage_scenario: str = Field(default="", description="使用场景")
    customer_feedback: str = Field(default="", description="客户反馈")
    image_description: str = Field(default="", description="图片描述")
    content_theme: str = Field(default="", description="内容主题")
    weekly_data: str = Field(default="", description="本周数据")
    last_week_data: str = Field(default="", description="上周数据")
    # 飞书参数
    feishu_app_token: str = Field(default="", description="飞书app_token")
    feishu_table_id: str = Field(default="", description="飞书产品表table_id")
    feishu_content_table_id: str = Field(default="", description="飞书内容表table_id")
    feishu_filter_field: str = Field(default="处理状态", description="飞书筛选字段")
    feishu_filter_value: str = Field(default="待处理", description="飞书筛选值")
    # 飞书热点选题参数
    feishu_hot_calendar_table_id: str = Field(default="tblT1KM0397UcGeM", description="热点日历表table_id")
    feishu_product_table_id: str = Field(default="tbllExTlKURFJP2j", description="产品素材表table_id")
    feishu_topic_table_id: str = Field(default="tblJNjx74uZ3s1vs", description="选题库table_id")


class EntryNodeOutput(BaseModel):
    """入口节点输出"""
    workflow_type: str = Field(..., description="工作流类型")
    result: str = Field(..., description="生成结果")


# ============================================
# 入口节点实现
# ============================================
def hot_topic_entry_node(
    state: EntryNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EntryNodeOutput:
    """
    title: 热点选题生成器
    desc: 根据节日、节气、热播剧、传统文化热点生成小红书选题
    integrations: 大语言模型
    """
    # 创建核心节点输入
    node_input = HotTopicInput(
        hot_topic_name=state.hot_topic_name,
        hot_topic_date=state.hot_topic_date,
        account=state.account,
        available_products=state.available_products,
        target_audience=state.target_audience,
        content_style=state.content_style
    )
    
    # 调用核心节点
    node_output = hot_topic_generator_node(node_input, config, runtime)
    
    return EntryNodeOutput(
        workflow_type="hot_topic",
        result=node_output.result
    )


def product_post_entry_node(
    state: EntryNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EntryNodeOutput:
    """
    title: 产品发布文案生成器
    desc: 为产品生成完整的小红书笔记内容包
    integrations: 大语言模型
    """
    node_input = ProductPostInput(
        product_name=state.product_name,
        product_material=state.product_material,
        product_selling_points=state.product_selling_points,
        suitable_scenarios=state.suitable_scenarios,
        target_audience=state.target_audience,
        price_range=state.price_range,
        reference_copy=state.reference_copy,
        publish_account=state.publish_account
    )
    
    node_output = product_post_generator_node(node_input, config, runtime)
    
    return EntryNodeOutput(
        workflow_type="product_post",
        result=node_output.result
    )


def customer_story_entry_node(
    state: EntryNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EntryNodeOutput:
    """
    title: 客户故事生成器
    desc: 将真实客户购买经历转化为有温度的小红书故事笔记
    integrations: 大语言模型
    """
    node_input = CustomerStoryInput(
        customer_background=state.customer_background,
        purchased_product=state.purchased_product,
        purchase_reason=state.purchase_reason,
        usage_scenario=state.usage_scenario,
        customer_feedback=state.customer_feedback,
        account=state.account
    )
    
    node_output = customer_story_generator_node(node_input, config, runtime)
    
    return EntryNodeOutput(
        workflow_type="customer_story",
        result=node_output.result
    )


def image_suggestion_entry_node(
    state: EntryNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EntryNodeOutput:
    """
    title: 图片/封面建议器
    desc: 为小红书笔记设计图片发布方案
    integrations: 大语言模型
    """
    node_input = ImageSuggestionInput(
        product_name=state.product_name,
        image_description=state.image_description,
        content_theme=state.content_theme,
        account=state.account
    )
    
    node_output = image_suggestion_node(node_input, config, runtime)
    
    return EntryNodeOutput(
        workflow_type="image_suggestion",
        result=node_output.result
    )


def weekly_review_entry_node(
    state: EntryNodeInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> EntryNodeOutput:
    """
    title: 每周数据复盘器
    desc: 分析两个账号的内容表现，输出优化建议
    integrations: 大语言模型
    """
    node_input = WeeklyReviewInput(
        weekly_data=state.weekly_data,
        last_week_data=state.last_week_data
    )
    
    node_output = weekly_review_node(node_input, config, runtime)
    
    return EntryNodeOutput(
        workflow_type="weekly_review",
        result=node_output.result
    )


# ============================================
# 飞书集成工作流节点（方案C：读取→生成→写入）
# ============================================
class FeishuWorkflowInput(BaseModel):
    """飞书工作流输入"""
    feishu_app_token: str = Field(default="", description="飞书app_token")
    feishu_table_id: str = Field(default="", description="飞书产品表table_id")
    feishu_content_table_id: str = Field(default="", description="飞书内容表table_id")
    feishu_filter_field: str = Field(default="处理状态", description="飞书筛选字段")
    feishu_filter_value: str = Field(default="待处理", description="飞书筛选值")
    publish_account: str = Field(default="", description="发布账号")


class FeishuWorkflowOutput(BaseModel):
    """飞书工作流输出"""
    workflow_type: str = Field(..., description="工作流类型")
    result: str = Field(..., description="处理结果")
    processed_count: int = Field(default=0, description="处理记录数")
    success_count: int = Field(default=0, description="成功写入数")


def extract_feishu_field(field_value: Any) -> str:
    """
    从飞书字段值中提取文本内容
    飞书字段格式通常是: [{'text': '内容', 'type': 'text'}]
    """
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


def feishu_product_workflow_node(
    state: FeishuWorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 飞书产品文案自动生成
    desc: 从飞书产品库读取产品信息，自动生成小红书文案，并写入飞书内容表
    integrations: 大语言模型, 飞书多维表格
    """
    ctx = runtime.context
    
    # 步骤1: 从飞书读取待处理产品
    read_input = FeishuReadInput(
        app_token=state.feishu_app_token,
        table_id=state.feishu_table_id,
        filter_field=state.feishu_filter_field,
        filter_value=state.feishu_filter_value
    )
    read_output = feishu_read_node(read_input, config, runtime)
    
    if read_output.record_count == 0:
        return FeishuWorkflowOutput(
            workflow_type="feishu_product",
            result="没有找到待处理的记录",
            processed_count=0,
            success_count=0
        )
    
    # 步骤2: 遍历记录生成文案
    success_count = 0
    results = []
    
    for record in read_output.records:
        fields = record.get("fields", {})
        record_id = record.get("record_id", "")
        
        # 从飞书记录中提取产品信息，使用extract_feishu_field处理字段格式
        product_name = extract_feishu_field(fields.get("产品名称"))
        product_material = extract_feishu_field(fields.get("产品材质"))
        product_selling_points = extract_feishu_field(fields.get("产品卖点"))
        suitable_scenarios = extract_feishu_field(fields.get("适合场景"))
        target_audience = extract_feishu_field(fields.get("目标人群"))
        price_range = extract_feishu_field(fields.get("价格区间"))
        reference_copy = extract_feishu_field(fields.get("参考文案"))
        
        if not product_name:
            continue
        
        # 调用产品文案生成器
        post_input = ProductPostInput(
            product_name=product_name,
            product_material=product_material,
            product_selling_points=product_selling_points,
            suitable_scenarios=suitable_scenarios,
            target_audience=target_audience,
            price_range=price_range,
            reference_copy=reference_copy,
            publish_account=state.publish_account
        )
        post_output = product_post_generator_node(post_input, config, runtime)
        
        # 解析生成的内容，提取各字段
        generated_content = post_output.result
        
        # 提取第一个标题作为发布标题
        title_match = re.search(r"1\. 种草型[：:]\s*(.+?)(?:\n|$)", generated_content)
        publish_title = title_match.group(1).strip() if title_match else product_name
        
        # 提取正文
        content_match = re.search(r"二、正文.*?\n(.+?)(?=三、|$)", generated_content, re.DOTALL)
        content_body = content_match.group(1).strip() if content_match else generated_content[:500]
        
        # 提取标签
        tags_match = re.search(r"五、15个小红书标签.*?核心标签[^\n]*\n(.+?)(?:\n|$)", generated_content, re.DOTALL)
        tags = tags_match.group(1).strip() if tags_match else ""
        
        # 提取@账号
        at_match = re.search(r"六、适合@的官方账号.*?\n(.+?)(?:\n|$)", generated_content, re.DOTALL)
        at_accounts = at_match.group(1).strip() if at_match else ""
        
        # 提取评论区引导语
        comment_match = re.search(r"七、评论区引导语.*?\n(.+?)(?:\n|$)", generated_content, re.DOTALL)
        comment_guide = comment_match.group(1).strip() if comment_match else ""
        
        # 步骤3: 写入飞书内容表（使用正确的字段名）
        write_input = FeishuWriteInput(
            app_token=state.feishu_app_token,
            table_id=state.feishu_content_table_id,
            record_id="",  # 新增记录
            fields={
                "发布标题": publish_title,
                "正文": content_body,
                "内容栏目": "产品种草",  # 单选
                "发布账号": state.publish_account,  # 单选
                "发布标签": tags,
                "@薯账号": at_accounts,
                "评论区引导语": comment_guide,
                "发布状态": "待审核"  # 单选
            }
        )
        write_output = feishu_write_node(write_input, config, runtime)
        
        if write_output.success:
            success_count += 1
            results.append(f"✓ {product_name} 文案已生成并写入")
        else:
            results.append(f"✗ {product_name} 写入失败: {write_output.message}")
    
    return FeishuWorkflowOutput(
        workflow_type="feishu_product",
        result="\n".join(results),
        processed_count=read_output.record_count,
        success_count=success_count
    )


def feishu_hot_topic_workflow_node(
    state: EntryNodeInput,
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
        filter_field=state.feishu_filter_field or "状态",
        filter_value=state.feishu_filter_value or "待准备",
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
        product_name = extract_feishu_field(fields.get("产品名称"))
        selling_point = extract_feishu_field(fields.get("核心卖点"))
        if product_name:
            products.append(f"{product_name}+{selling_point}" if selling_point else product_name)
    
    available_products = "，".join(products)
    
    # 步骤3: 处理第一条热点生成选题（测试用）
    success_count = 0
    results = []
    
    # 只取第一条记录进行测试
    if hot_calendar_output.records:
        record = hot_calendar_output.records[0]
        fields = record.get("fields", {})
        hot_record_id = record.get("record_id", "")
        
        # 提取热点信息
        hot_topic_name = extract_feishu_field(fields.get("热点名称"))
        hot_topic_date = extract_feishu_field(fields.get("热点日期"))
        account = extract_feishu_field(fields.get("适合账号")) or state.publish_account
        
        if hot_topic_name:
            # 调用热点选题生成器
            topic_input = HotTopicInput(
                hot_topic_name=hot_topic_name,
                hot_topic_date=hot_topic_date,
                account=account,
                available_products=available_products,
                target_audience=state.target_audience or "25-35岁女性，喜欢传统文化和审美生活方式",
                content_style=state.content_style or "新中式、克制、种草但不硬广"
            )
            topic_output = hot_topic_generator_node(topic_input, config, runtime)
            
            # 步骤4: 写入选题库（关联热点需要传入记录ID列表）
            write_input = FeishuWriteInput(
                app_token=state.feishu_app_token,
                table_id=state.feishu_topic_table_id,
                record_id="",
                fields={
                    "选题标题": hot_topic_name,  # 暂用热点名称作为选题标题
                    "切入角度": topic_output.result,  # 全文写入
                    "目标账号": account,
                    "关联热点": [hot_record_id] if hot_record_id else [],  # 单向链接需要记录ID列表
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
# 工作流②：产品文案生成器（飞书版）
# 读取选题库 → 读取产品素材库 → 生成文案 → 写入内容成品库
# ============================================
def feishu_topic_post_workflow_node(
    state: FeishuTopicPostInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuTopicPostOutput:
    """
    title: 飞书产品文案工作流
    desc: 从选题库读取通过的选题→读取产品素材→生成文案→写入内容库
    integrations: 飞书多维表格, 大语言模型
    """
    import os
    import json
    import re
    from jinja2 import Template
    from cozeloop.decorator import observe
    from coze_coding_dev_sdk import LLMClient
    
    ctx = runtime.context
    
    # 读取LLM配置
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/product_post_generator_cfg.json")
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        llm_cfg = json.load(fd)
    
    app_token = state.feishu_app_token
    topic_table_id = state.feishu_topic_table_id
    product_table_id = state.feishu_product_table_id
    content_table_id = state.feishu_content_table_id
    filter_status = getattr(state, 'filter_status', '通过') or '通过'
    
    results = []
    success_count = 0
    
    # 1. 读取选题库（筛选：选题状态 = "通过"）
    topic_input = FeishuReadInput(
        app_token=app_token,
        table_id=topic_table_id,
        filter_field="选题状态",
        filter_value=filter_status,
        page_size=1  # 只取一条
    )
    topic_output = feishu_read_node(topic_input, config, runtime)
    
    if not topic_output.records:
        return FeishuWorkflowOutput(
            workflow_type="feishu_topic_post",
            result="没有找到待处理的选题记录"
        )
    
    # 2. 读取产品素材库（获取所有可发布产品）
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
        product_name = extract_feishu_field(fields.get("产品名称", ""))
        if product_name:
            product_map[product_name] = {
                "材质": extract_feishu_field(fields.get("材质说明", "")),
                "卖点": extract_feishu_field(fields.get("核心卖点", "")),
                "场景": extract_feishu_field(fields.get("使用场景", "")),
                "价格": extract_feishu_field(fields.get("价格区间", "")),
                "人群": extract_feishu_field(fields.get("适合人群", ""))
            }
    
    # 3. 处理选题记录
    for topic_record in topic_output.records:
        topic_fields = topic_record.get("fields", {})
        topic_id = topic_record.get("record_id", "")
        topic_title = extract_feishu_field(topic_fields.get("选题标题", ""))
        topic_angle = extract_feishu_field(topic_fields.get("切入角度", ""))
        account = extract_feishu_field(topic_fields.get("目标账号", "灵楠阁品牌号"))
        
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
        
        # 4. 调用LLM生成文案
        user_prompt = f"""产品名称：{product_info.split('，')[0] if '，' in product_info else product_info}
产品材质：{product_map.get(product_info.split('，')[0], {}).get('材质', '金丝楠木')}
产品卖点：{product_map.get(product_info.split('，')[0], {}).get('卖点', '温润细腻，越戴越亮')}
适合场景：{product_map.get(product_info.split('，')[0], {}).get('场景', '日常佩戴')}
目标人群：{product_map.get(product_info.split('，')[0], {}).get('人群', '25-45岁喜欢传统文化的人群')}
价格区间：{product_map.get(product_info.split('，')[0], {}).get('价格', '500-2000元')}
参考文案：{topic_angle}
发布账号：{account}"""
        
        sp = llm_cfg.get("sp", "")
        up_tpl = Template(llm_cfg.get("up", ""))
        user_prompt_content = up_tpl.render({
            "product_name": product_info.split('，')[0] if '，' in product_info else product_info,
            "product_material": product_map.get(product_info.split('，')[0], {}).get('材质', '金丝楠木'),
            "product_selling_points": product_map.get(product_info.split('，')[0], {}).get('卖点', ''),
            "suitable_scenarios": product_map.get(product_info.split('，')[0], {}).get('场景', ''),
            "target_audience": product_map.get(product_info.split('，')[0], {}).get('人群', ''),
            "price_range": product_map.get(product_info.split('，')[0], {}).get('价格', ''),
            "reference_copy": topic_angle,
            "publish_account": account
        })
        
        llm_client = LLMClient(ctx=ctx)
        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=user_prompt_content)
        ]
        response = llm_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-pro-260215"
        )
        
        content_result = response.content if hasattr(response, 'content') else str(response)
        
        # 解析文案内容
        title_match = re.search(r'1\.\s*种草型[：:]\s*(.+)', content_result)
        post_title = title_match.group(1).strip() if title_match else topic_title
        
        body_match = re.search(r'二、正文[^\n]*\n(.+?)(?=\n三、)', content_result, re.DOTALL)
        post_body = body_match.group(1).strip() if body_match else content_result[:500]
        
        tags_match = re.search(r'五、15个小红书标签[^\n]*\n(.+?)(?=\n六、)', content_result, re.DOTALL)
        post_tags = tags_match.group(1).strip() if tags_match else ""
        
        at_match = re.search(r'六、适合@的官方账号[^\n]*\n(.+?)(?=\n七、)', content_result, re.DOTALL)
        at_accounts = at_match.group(1).strip() if at_match else ""
        
        comment_match = re.search(r'七、评论区引导语[^\n]*\n(.+?)(?=\n八、)', content_result, re.DOTALL)
        comment_guide = comment_match.group(1).strip() if comment_match else ""
        
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
                "@薯账号": at_accounts,
                "评论区引导语": comment_guide,
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
# 工作流③：客户故事生成器（手动输入 → 写入内容库）
# ============================================
class FeishuCustomerStoryInput(BaseModel):
    """客户故事工作流输入"""
    workflow_type: str = Field(default="feishu_customer_story", description="工作流类型")
    feishu_app_token: str = Field(..., description="飞书多维表格app_token")
    feishu_content_table_id: str = Field(..., description="内容成品库table_id")
    # 手动输入的参数
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
    
    # 构建提示词
    prompt = f"""你是小红书客户故事文案专家，擅长把真实购买经历写成有审美、有情绪、有文化感的内容。

请根据以下信息写一篇客户故事型小红书笔记：
客户背景：{state.customer_background}
购买产品：{state.purchased_product}
购买原因：{state.purchase_reason}
使用场景：{state.usage_scenario}
客户反馈：{state.customer_feedback}
发布账号：{state.account}

请输出：
一、5个标题（不同类型：情绪型、故事型、产品亮点型、文化型、反转型）
二、正文（400-700字）
结构要求：
- 开头：客户的一句话/一个场景（制造代入感）
- 中段：为什么买、怎么选的、收到后的感受（故事线）
- 转折：产品给生活带来的小变化（不是奇迹，是真实细节）
- 结尾：自然引导评论或私信
三、封面文案（不超过10字）
四、8-12个标签
五、评论区互动问题（2-3个）

要求：
- 故事真实、克制、动人，不要夸张
- 突出产品外观、材质、文化气息、陪伴感、仪式感
- 不要写成玄学承诺（禁止：招财、转运、辟邪、改命）
- 可以表达："给自己一点稳定感""在忙乱生活里保留一点仪式感""讨一个美好寓意"
"""
    
    # 调用LLM
    from langchain_core.messages import HumanMessage
    llm_client = LLMClient()
    llm_result = llm_client.invoke(
        messages=[HumanMessage(content=prompt)],
        model="doubao-seed-2-0-pro-260215",
        temperature=0.7
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
    
    # 提取互动问题
    interaction_match = re.search(r"五[、\.．]\s*评论区互动问题[^国]*$", content, re.DOTALL)
    comment_guide = ""
    if interaction_match:
        questions = re.findall(r"\d+[\.、．]\s*(.+?)(?=\n\d|\n$|$)", interaction_match.group(0), re.DOTALL)
        if questions:
            comment_guide = questions[0].strip()
    
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
            "评论区引导语": comment_guide,
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
# 工作流④：图片建议器（读内容库+产品库 → 更新内容库）
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
    from coze_coding_dev_sdk import llm
    from coze_workload_identity import Client
    import requests
    
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
    post_title = extract_feishu_field(content_fields.get("发布标题", ""))
    content_body = extract_feishu_field(content_fields.get("正文", ""))
    
    # 2. 生成图片建议
    prompt = f"""你是小红书视觉运营和新中式审美设计顾问。
请为以下内容设计图片发布方案：

内容标题：{post_title}

请输出：
一、封面图建议
1. 推荐哪种图做封面
2. 封面主标题3个（每个不超过12字）

二、多图笔记图片顺序（1-9编号）

三、每张图的修图方向

四、是否需要补拍

五、AI生图提示词（3个）
"""
    
    from langchain_core.messages import HumanMessage
    llm_client = LLMClient()
    llm_result = llm_client.invoke(
        messages=[HumanMessage(content=prompt)],
        model="doubao-seed-2-0-pro-260215",
        temperature=0.7
    )
    image_suggestion = llm_result.content if hasattr(llm_result, 'content') else str(llm_result)
    
    # 3. 更新内容成品库（追加图片建议到正文）
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
# 条件路由函数
# ============================================
def route_workflow(state: EntryNodeInput) -> str:
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

# 添加节点（带配置文件元数据）
builder.add_node(
    "hot_topic",
    hot_topic_entry_node,
    metadata={"type": "agent", "llm_cfg": "config/hot_topic_generator_cfg.json"}
)
builder.add_node(
    "product_post",
    product_post_entry_node,
    metadata={"type": "agent", "llm_cfg": "config/product_post_generator_cfg.json"}
)
builder.add_node(
    "customer_story",
    customer_story_entry_node,
    metadata={"type": "agent", "llm_cfg": "config/customer_story_generator_cfg.json"}
)
builder.add_node(
    "image_suggestion",
    image_suggestion_entry_node,
    metadata={"type": "agent", "llm_cfg": "config/image_suggestion_cfg.json"}
)
builder.add_node(
    "weekly_review",
    weekly_review_entry_node,
    metadata={"type": "agent", "llm_cfg": "config/weekly_review_cfg.json"}
)
builder.add_node(
    "feishu_product",
    feishu_product_workflow_node,
    metadata={"type": "agent", "llm_cfg": "config/product_post_generator_cfg.json"}
)
builder.add_node(
    "feishu_hot_topic",
    feishu_hot_topic_workflow_node,
    metadata={"type": "agent", "llm_cfg": "config/hot_topic_generator_cfg.json"}
)
builder.add_node(
    "feishu_topic_post",
    feishu_topic_post_workflow_node,
    metadata={"type": "agent", "llm_cfg": "config/product_post_generator_cfg.json"}
)
builder.add_node(
    "feishu_customer_story",
    feishu_customer_story_workflow_node,
    metadata={"type": "agent", "llm_cfg": "config/customer_story_generator_cfg.json"}
)
builder.add_node(
    "feishu_image_suggestion",
    feishu_image_suggestion_workflow_node,
    metadata={"type": "agent", "llm_cfg": "config/image_suggestion_cfg.json"}
)

# 添加条件边作为入口
builder.add_conditional_edges(
    source="__start__",
    path=route_workflow,
    path_map={
        "hot_topic": "hot_topic",
        "product_post": "product_post",
        "customer_story": "customer_story",
        "image_suggestion": "image_suggestion",
        "weekly_review": "weekly_review",
        "feishu_product": "feishu_product",
        "feishu_hot_topic": "feishu_hot_topic",
        "feishu_topic_post": "feishu_topic_post",
        "feishu_customer_story": "feishu_customer_story",
        "feishu_image_suggestion": "feishu_image_suggestion"
    }
)

# 所有节点都直接结束
builder.add_edge("hot_topic", END)
builder.add_edge("product_post", END)
builder.add_edge("customer_story", END)
builder.add_edge("image_suggestion", END)
builder.add_edge("weekly_review", END)
builder.add_edge("feishu_product", END)
builder.add_edge("feishu_hot_topic", END)
builder.add_edge("feishu_topic_post", END)
builder.add_edge("feishu_customer_story", END)
builder.add_edge("feishu_image_suggestion", END)

# 编译图
main_graph = builder.compile()
