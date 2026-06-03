"""
小红书内容生成系统 - 主图编排
包含5个独立的工作流，可通过workflow_type参数选择调用
"""

from typing import Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context

from graphs.state import (
    GlobalState,
    HotTopicInput,
    ProductPostInput,
    CustomerStoryInput,
    ImageSuggestionInput,
    WeeklyReviewInput,
)

from graphs.nodes.hot_topic_generator_node import hot_topic_generator_node
from graphs.nodes.product_post_generator_node import product_post_generator_node
from graphs.nodes.customer_story_generator_node import customer_story_generator_node
from graphs.nodes.image_suggestion_node import image_suggestion_node
from graphs.nodes.weekly_review_node import weekly_review_node


# ============================================
# 统一入参定义
# ============================================
class WorkflowInput(BaseModel):
    """工作流统一输入参数"""
    workflow_type: Literal["hot_topic", "product_post", "customer_story", "image_suggestion", "weekly_review"] = Field(
        ..., 
        description="工作流类型：hot_topic(热点选题)、product_post(产品文案)、customer_story(客户故事)、image_suggestion(图片建议)、weekly_review(数据复盘)"
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

# 添加条件边作为入口
builder.add_conditional_edges(
    source="__start__",
    path=route_workflow,
    path_map={
        "hot_topic": "hot_topic",
        "product_post": "product_post",
        "customer_story": "customer_story",
        "image_suggestion": "image_suggestion",
        "weekly_review": "weekly_review"
    }
)

# 所有节点都直接结束
builder.add_edge("hot_topic", END)
builder.add_edge("product_post", END)
builder.add_edge("customer_story", END)
builder.add_edge("image_suggestion", END)
builder.add_edge("weekly_review", END)

# 编译图
main_graph = builder.compile()
