"""
小红书内容生成系统 - 状态定义
包含5个工作流的独立输入输出状态定义
支持飞书多维表格读取和写入
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
    filter_field: str = Field(default="处理状态", description="筛选字段名")
    filter_value: str = Field(default="待处理", description="筛选字段值")


class FeishuReadOutput(BaseModel):
    """飞书读取节点输出"""
    records: list = Field(default=[], description="读取到的记录列表")
    record_count: int = Field(default=0, description="记录数量")


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
# 工作流1：热点选题生成器
# ============================================
class HotTopicInput(BaseModel):
    """热点选题生成器的输入"""
    hot_topic_name: str = Field(..., description="热点名称，如'端午节'、'立夏'、'《XXX》热播'")
    hot_topic_date: str = Field(..., description="热点日期，如'2026年6月19日'")
    account: str = Field(..., description="发布账号：'灵楠阁品牌号' 或 '古典家具号'")
    available_products: str = Field(..., description="可用产品，格式：产品名+核心卖点，逗号分隔")
    target_audience: str = Field(..., description="目标人群，如'25-35岁女性，喜欢传统文化和审美生活方式'")
    content_style: str = Field(..., description="内容风格，如'新中式、克制、种草但不硬广'")


class HotTopicOutput(BaseModel):
    """热点选题生成器的输出"""
    result: str = Field(..., description="生成的小红书选题完整内容，包含10个选题、标题、切入角度、产品匹配、封面文案、图片建议、标签等")


# ============================================
# 工作流2：产品发布文案生成器
# ============================================
class ProductPostInput(BaseModel):
    """产品发布文案生成器的输入"""
    product_name: str = Field(..., description="产品全称")
    product_material: str = Field(..., description="产品材质说明")
    product_selling_points: str = Field(..., description="产品3-5个核心卖点")
    suitable_scenarios: str = Field(..., description="产品使用/佩戴/陈设场景")
    target_audience: str = Field(..., description="适合什么样的人")
    price_range: str = Field(..., description="价格区间")
    reference_copy: Optional[str] = Field(default="", description="品牌手册中的参考描述（可选）")
    publish_account: str = Field(..., description="发布账号：品牌号 / 家具号")


class ProductPostOutput(BaseModel):
    """产品发布文案生成器的输出"""
    result: str = Field(..., description="生成的完整小红书笔记内容包，包含5个标题、正文、封面文案、图片建议、标签、风险词提醒等")


# ============================================
# 工作流3：客户故事生成器
# ============================================
class CustomerStoryInput(BaseModel):
    """客户故事生成器的输入"""
    customer_background: str = Field(..., description="客户大致身份，如'30岁设计师'、'刚入职场的女生'")
    purchased_product: str = Field(..., description="购买的产品")
    purchase_reason: str = Field(..., description="购买原因，如送自己/送人/收藏等")
    usage_scenario: str = Field(..., description="买回去之后怎么用/摆/戴")
    customer_feedback: str = Field(..., description="客户原话或感受（隐去隐私后）")
    account: str = Field(..., description="发布账号：品牌号 / 家具号")


class CustomerStoryOutput(BaseModel):
    """客户故事生成器的输出"""
    result: str = Field(..., description="生成的客户故事型小红书笔记，包含5个标题、正文（400-700字）、封面文案、标签、评论区互动问题")


# ============================================
# 工作流4：图片/封面建议器
# ============================================
class ImageSuggestionInput(BaseModel):
    """图片/封面建议器的输入"""
    product_name: str = Field(..., description="要出镜的产品")
    image_description: str = Field(..., description="现有图片素材描述")
    content_theme: str = Field(..., description="这篇笔记的主题/标题")
    account: str = Field(..., description="发布账号：品牌号 / 家具号")


class ImageSuggestionOutput(BaseModel):
    """图片/封面建议器的输出"""
    result: str = Field(..., description="生成的图片发布方案，包含封面图建议、多图排序、修图方向、补拍建议、AI生图提示词")


# ============================================
# 工作流5：每周数据复盘器
# ============================================
class WeeklyReviewInput(BaseModel):
    """每周数据复盘器的输入"""
    weekly_data: str = Field(..., description="本周数据，含账号、标题、栏目、标签、发布时间、点赞、收藏、评论、私信、是否成交")
    last_week_data: Optional[str] = Field(default="", description="上周同期数据（可选）")


class WeeklyReviewOutput(BaseModel):
    """每周数据复盘器的输出"""
    result: str = Field(..., description="生成的数据分析报告，包含表现最好内容、栏目分析、标题结构分析、产品转化分析、下周选题建议、发布排期建议")


# ============================================
# 全局状态（用于图编排）
# ============================================
class GlobalState(BaseModel):
    """全局状态定义"""
    # 热点选题相关
    hot_topic_result: str = Field(default="", description="热点选题生成结果")
    # 产品文案相关
    product_post_result: str = Field(default="", description="产品文案生成结果")
    # 客户故事相关
    customer_story_result: str = Field(default="", description="客户故事生成结果")
    # 图片建议相关
    image_suggestion_result: str = Field(default="", description="图片建议生成结果")
    # 数据复盘相关
    weekly_review_result: str = Field(default="", description="每周数据复盘结果")
