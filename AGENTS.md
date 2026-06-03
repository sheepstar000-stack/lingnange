# 小红书内容生成系统

## 项目概述
- **名称**: 小红书内容生成工作流系统
- **功能**: 5个独立的小红书内容生成工作流，支持热点选题、产品文案、客户故事、图片建议和数据复盘

## 工作流清单

| 工作流名称 | workflow_type | 功能描述 | 输入参数 |
|-----------|---------------|---------|---------|
| 热点选题生成器 | hot_topic | 根据节日、节气、热播剧、传统文化热点生成小红书选题 | 热点名称、日期、账号、产品、人群、风格 |
| 产品发布文案生成器 | product_post | 为产品生成完整的小红书笔记内容包 | 产品名称、材质、卖点、场景、人群、价格 |
| 客户故事生成器 | customer_story | 将客户购买经历转化为有温度的小红书故事 | 客户背景、购买产品、购买原因、使用场景、反馈 |
| 图片/封面建议器 | image_suggestion | 为笔记设计图片发布方案 | 产品名称、图片描述、内容主题、账号 |
| 每周数据复盘器 | weekly_review | 分析账号内容表现，输出优化建议 | 本周数据、上周数据 |

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 | 配置文件 |
|-------|---------|------|---------|---------|
| hot_topic | `nodes/hot_topic_generator_node.py` | agent | 热点选题生成 | `config/hot_topic_generator_cfg.json` |
| product_post | `nodes/product_post_generator_node.py` | agent | 产品文案生成 | `config/product_post_generator_cfg.json` |
| customer_story | `nodes/customer_story_generator_node.py` | agent | 客户故事生成 | `config/customer_story_generator_cfg.json` |
| image_suggestion | `nodes/image_suggestion_node.py` | agent | 图片建议生成 | `config/image_suggestion_cfg.json` |
| weekly_review | `nodes/weekly_review_node.py` | agent | 数据复盘分析 | `config/weekly_review_cfg.json` |

**类型说明**: agent(大模型节点)

## 文件结构

```
src/graphs/
├── state.py                    # 状态定义：5个工作流的Input/Output
├── graph.py                    # 主图编排：条件路由到5个工作流
└── nodes/
    ├── hot_topic_generator_node.py      # 热点选题生成器节点
    ├── product_post_generator_node.py   # 产品文案生成器节点
    ├── customer_story_generator_node.py # 客户故事生成器节点
    ├── image_suggestion_node.py         # 图片建议器节点
    └── weekly_review_node.py            # 数据复盘器节点

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

## 使用方式

调用工作流时，通过 `workflow_type` 参数指定要执行的工作流：

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

## 输出格式

所有工作流统一返回：

```json
{
  "workflow_type": "hot_topic",
  "result": "生成的内容..."
}
```
