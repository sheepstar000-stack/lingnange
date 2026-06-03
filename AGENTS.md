# 小红书内容生成系统

## 项目概述
- **名称**: 小红书内容生成工作流系统
- **功能**: 6个独立的小红书内容生成工作流，支持热点选题、产品文案、客户故事、图片建议、数据复盘，以及飞书表格自动化

## 工作流清单

| 工作流名称 | workflow_type | 功能描述 | 输入参数 |
|-----------|---------------|---------|---------|
| 热点选题生成器 | hot_topic | 根据节日、节气、热播剧、传统文化热点生成小红书选题 | 热点名称、日期、账号、产品、人群、风格 |
| 产品发布文案生成器 | product_post | 为产品生成完整的小红书笔记内容包 | 产品名称、材质、卖点、场景、人群、价格 |
| 客户故事生成器 | customer_story | 将客户购买经历转化为有温度的小红书故事 | 客户背景、购买产品、购买原因、使用场景、反馈 |
| 图片/封面建议器 | image_suggestion | 为笔记设计图片发布方案 | 产品名称、图片描述、内容主题、账号 |
| 每周数据复盘器 | weekly_review | 分析账号内容表现，输出优化建议 | 本周数据、上周数据 |
| **飞书产品文案自动化** | feishu_product | 从飞书产品库读取→生成文案→写入内容表 | 飞书app_token、产品表ID、内容表ID |
| **飞书热点选题自动化** | feishu_hot_topic | 从飞书热点日历+产品库读取→生成选题→写入选题库 | 飞书app_token、热点日历ID、产品表ID、选题库ID |
| **飞书选题文案自动化** | feishu_topic_post | 从选题库读取通过的选题→生成文案→写入内容库 | 飞书app_token、选题库ID、产品表ID、内容库ID |
| **飞书客户故事自动化** | feishu_customer_story | 手动输入客户信息→生成故事→写入内容库 | 客户背景、购买产品、购买原因、使用场景、反馈 |
| **飞书图片建议自动化** | feishu_image_suggestion | 从内容库读取待审核内容→生成图片建议→更新内容库 | 飞书app_token、内容库ID、产品表ID |

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| hot_topic | `nodes/hot_topic_generator_node.py` | agent | 热点选题生成 | `config/hot_topic_generator_cfg.json` |
| product_post | `nodes/product_post_generator_node.py` | agent | 产品文案生成 | `config/product_post_generator_cfg.json` |
| customer_story | `nodes/customer_story_generator_node.py` | agent | 客户故事生成 | `config/customer_story_generator_cfg.json` |
| image_suggestion | `nodes/image_suggestion_node.py` | agent | 图片建议生成 | `config/image_suggestion_cfg.json` |
| weekly_review | `nodes/weekly_review_node.py` | agent | 数据复盘分析 | `config/weekly_review_cfg.json` |
| feishu_product | `nodes/feishu_read_node.py` + `nodes/feishu_write_node.py` | agent | 飞书产品文案自动化 | `config/product_post_generator_cfg.json` |
| feishu_hot_topic | `graph.py` (内联) | agent | 飞书热点选题自动化 | `config/hot_topic_generator_cfg.json` |
| feishu_topic_post | `graph.py` (内联) | agent | 飞书选题文案自动化 | `config/product_post_generator_cfg.json` |
| feishu_customer_story | `graph.py` (内联) | agent | 飞书客户故事自动化 | `config/customer_story_generator_cfg.json` |
| feishu_image_suggestion | `graph.py` (内联) | agent | 飞书图片建议自动化 | `config/image_suggestion_cfg.json` |
| feishu_read | `nodes/feishu_read_node.py` | task | 飞书表格读取 | - |
| feishu_write | `nodes/feishu_write_node.py` | task | 飞书表格写入 | - |

**类型说明**: agent(大模型节点) / task(普通任务节点)

## 文件结构

```
src/graphs/
├── state.py                    # 状态定义：工作流Input/Output + 飞书配置
├── graph.py                    # 主图编排：条件路由到6个工作流
└── nodes/
    ├── hot_topic_generator_node.py      # 热点选题生成器节点
    ├── product_post_generator_node.py   # 产品文案生成器节点
    ├── customer_story_generator_node.py # 客户故事生成器节点
    ├── image_suggestion_node.py         # 图片建议器节点
    ├── weekly_review_node.py            # 数据复盘器节点
    ├── feishu_read_node.py              # 飞书表格读取节点
    └── feishu_write_node.py             # 飞书表格写入节点

config/
├── hot_topic_generator_cfg.json    # 热点选题生成器配置
├── product_post_generator_cfg.json # 产品文案生成器配置
├── customer_story_generator_cfg.json # 客户故事生成器配置
├── image_suggestion_cfg.json       # 图片建议器配置
└── weekly_review_cfg.json          # 数据复盘器配置
```

## 技能使用

| 节点 | 使用的技能 | 说明 |
|-----|-----------|------|
| hot_topic | 大语言模型 | doubao-seed-2-0-pro-260215 |
| product_post | 大语言模型 | doubao-seed-2-0-pro-260215 |
| customer_story | 大语言模型 | doubao-seed-2-0-pro-260215 |
| image_suggestion | 大语言模型 | doubao-seed-2-0-pro-260215 |
| weekly_review | 大语言模型 | doubao-seed-2-0-pro-260215 |
| feishu_read | 飞书多维表格 | 读取飞书表格数据 |
| feishu_write | 飞书多维表格 | 写入飞书表格数据 |

## 使用方式

### 1. 普通工作流调用

```json
{
  "workflow_type": "hot_topic",
  "hot_topic_name": "端午节",
  "hot_topic_date": "2026年6月19日",
  "account": "灵楠阁品牌号",
  "available_products": "金丝楠手串+温润细腻",
  "target_audience": "25-35岁女性",
  "content_style": "新中式、克制、种草但不硬广"
}
```

### 2. 飞书自动化工作流调用

#### 热点选题自动化
```json
{
  "workflow_type": "feishu_hot_topic",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_hot_calendar_table_id": "tblT1KM0397UcGeM",
  "feishu_product_table_id": "tbllExTlKURFJP2j",
  "feishu_topic_table_id": "tblJNjx74uZ3s1vs",
  "target_audience": "25-35岁女性",
  "content_style": "新中式、克制、种草但不硬广"
}
```

#### 选题文案自动化
```json
{
  "workflow_type": "feishu_topic_post",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_topic_table_id": "tblJNjx74uZ3s1vs",
  "feishu_product_table_id": "tbllExTlKURFJP2j",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "publish_account": "灵楠阁品牌号"
}
```

#### 客户故事自动化
```json
{
  "workflow_type": "feishu_customer_story",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "customer_background": "30岁设计师",
  "purchased_product": "金丝楠手串",
  "purchase_reason": "生日礼物",
  "usage_scenario": "日常佩戴",
  "customer_feedback": "很喜欢"
}
```

#### 图片建议自动化
```json
{
  "workflow_type": "feishu_image_suggestion",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "feishu_product_table_id": "tbllExTlKURFJP2j"
}
```

## 飞书表格字段配置说明

### 产品数据表（读取）
需要包含以下字段：
- 产品名称（文本）
- 产品材质（文本）
- 产品卖点（文本）
- 适合场景（文本）
- 目标人群（文本）
- 价格区间（文本）
- 参考文案（文本，可选）
- 处理状态（单选：待处理/已处理）

### 内容输出表（写入）
需要包含以下字段：
- 产品名称（文本）
- 生成文案（多行文本）
- 来源记录ID（文本）
- 处理状态（单选：已生成）

## 输出格式

所有工作流统一返回：

```json
{
  "workflow_type": "hot_topic",
  "result": "生成的内容..."
}
```

飞书工作流返回：

```json
{
  "workflow_type": "feishu_product",
  "result": "✓ 产品A 文案已生成并写入\n✓ 产品B 文案已生成并写入",
  "processed_count": 2,
  "success_count": 2
}
```
