"""
小红书内容生成系统 - 飞书自动化工作流状态定义
包含飞书多维表格读取/写入节点及5个工作流的输入输出状态定义
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================
# 飞书多维表格配置
# ============================================
class FeishuConfig(BaseModel):
    """飞书多维表格配置"""
    app_token: str = Field(..., description="多维表格的app_token")
    table_id: str = Field(..., description="数据表的table_id")
    view_id: Optional[str] = Field(default="", description="视图ID（可选）")


class FeishuReadInput(BaseModel):
    """飞书读取节点输入"""
    app_token: str = Field(..., description="多维表格的app_token")
    table_id: str = Field(..., description="数据表的table_id")
    filter_field: str = Field(default="", description="筛选字段名")
    filter_value: str = Field(default="", description="筛选字段值")
    page_size: int = Field(default=20, description="每页记录数")


class FeishuReadOutput(BaseModel):
    """飞书读取节点输出"""
    records: list = Field(default=[], description="读取到的记录列表")
    record_count: int = Field(default=0, description="记录数量")
    error: str = Field(default="", description="错误信息（空字符串表示正常）")


class FeishuWriteInput(BaseModel):
    """飞书写入节点输入"""
    app_token: str = Field(..., description="多维表格的app_token")
    table_id: str = Field(..., description="数据表的table_id")
    record_id: Optional[str] = Field(default="", description="要更新的记录ID（可选，不填则新增）")
    fields: Dict[str, Any] = Field(default={}, description="要写入的字段数据")


class FeishuWriteOutput(BaseModel):
    """飞书写入节点输出"""
    success: bool = Field(..., description="是否写入成功")
    record_id: str = Field(default="", description="写入的记录ID")
    message: str = Field(default="", description="操作结果消息")


# ============================================
# 工作流①：飞书热点选题
# ============================================
class FeishuHotTopicInput(BaseModel):
    """飞书热点选题工作流输入"""
    feishu_app_token: str = Field(..., description="飞书多维表格的app_token")
    feishu_hot_calendar_table_id: str = Field(default="tblT1KM0397UcGeM", description="热点日历表的table_id")
    feishu_product_table_id: str = Field(default="tbllExTlKURFJP2j", description="产品素材表的table_id")
    feishu_topic_table_id: str = Field(default="tblJNjx74uZ3s1vs", description="选题库的table_id")
    publish_account: str = Field(default="灵楠阁品牌号", description="发布账号")
    target_audience: str = Field(default="25-35岁女性，喜欢传统文化和审美生活方式", description="目标人群")
    content_style: str = Field(default="新中式、克制、种草但不硬广", description="内容风格")


class FeishuHotTopicOutput(BaseModel):
    """飞书热点选题工作流输出"""
    result: str = Field(..., description="执行结果：成功生成的选题数量和详情")
    topics_created: int = Field(default=0, description="生成的选题数量")


# ============================================
# 工作流②：飞书选题文案
# ============================================
class FeishuTopicPostInput(BaseModel):
    """飞书选题文案工作流输入"""
    feishu_app_token: str = Field(..., description="飞书多维表格app_token")
    feishu_topic_table_id: str = Field(..., description="选题库table_id")
    feishu_product_table_id: str = Field(..., description="产品素材库table_id")
    feishu_content_table_id: str = Field(..., description="内容成品库table_id")
    filter_status: str = Field(default="通过", description="选题状态筛选条件")
    publish_account: str = Field(default="灵楠阁品牌号", description="发布账号")


class FeishuTopicPostOutput(BaseModel):
    """飞书选题文案工作流输出"""
    workflow_type: str = Field(default="feishu_topic_post", description="工作流类型")
    result: str = Field(default="", description="执行结果")


# ============================================
# 工作流③：飞书客户故事
# ============================================
class FeishuCustomerStoryInput(BaseModel):
    """飞书客户故事工作流输入"""
    feishu_app_token: str = Field(..., description="飞书多维表格app_token")
    feishu_content_table_id: str = Field(..., description="内容成品库table_id")
    customer_background: str = Field(..., description="客户背景")
    purchased_product: str = Field(..., description="购买产品")
    purchase_reason: str = Field(..., description="购买原因")
    usage_scenario: str = Field(..., description="使用场景")
    customer_feedback: str = Field(..., description="客户反馈")
    account: str = Field(default="灵楠阁品牌号", description="发布账号")


# ============================================
# 工作流④：飞书图片建议
# ============================================
class FeishuImageSuggestionInput(BaseModel):
    """飞书图片建议工作流输入"""
    feishu_app_token: str = Field(..., description="飞书多维表格app_token")
    feishu_content_table_id: str = Field(..., description="内容成品库table_id")
    feishu_product_table_id: str = Field(..., description="产品素材库table_id")


# ============================================
# 工作流⑤：飞书数据复盘
# ============================================
class FeishuWeeklyReviewInput(BaseModel):
    """飞书数据复盘工作流输入"""
    feishu_app_token: str = Field(..., description="飞书多维表格app_token")
    feishu_review_table_id: str = Field(..., description="数据复盘表table_id")
    feishu_topic_table_id: str = Field(..., description="选题库table_id")


class FeishuWeeklyReviewOutput(BaseModel):
    """飞书数据复盘工作流输出"""
    result: str = Field(default="", description="执行结果")


# ============================================
# 全局状态（用于图编排）
# ============================================
class GlobalState(BaseModel):
    """全局状态定义"""
    # 工作流类型
    workflow_type: str = Field(default="", description="工作流类型")
    # 飞书集成参数
    feishu_app_token: str = Field(default="", description="飞书多维表格app_token")
    feishu_product_table_id: str = Field(default="", description="产品素材表table_id")
    feishu_topic_table_id: str = Field(default="", description="选题库table_id")
    feishu_content_table_id: str = Field(default="", description="内容成品库table_id")
    feishu_review_table_id: str = Field(default="", description="数据复盘表table_id")
    feishu_hot_calendar_table_id: str = Field(default="", description="热点日历表table_id")
    # 工作流参数
    target_audience: str = Field(default="", description="目标人群")
    content_style: str = Field(default="", description="内容风格")
    publish_account: str = Field(default="", description="发布账号")
    # 客户故事参数
    customer_background: str = Field(default="", description="客户背景")
    purchased_product: str = Field(default="", description="购买产品")
    purchase_reason: str = Field(default="", description="购买原因")
    usage_scenario: str = Field(default="", description="使用场景")
    customer_feedback: str = Field(default="", description="客户反馈")
