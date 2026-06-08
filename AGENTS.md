# 小红书内容生成系统 - 飞书自动化工作流

## 项目概述
- **名称**: 小红书内容生成飞书自动化系统
- **功能**: 7个飞书自动化工作流，实现从飞书读取→LLM生成→写入飞书的完整流程

## 工作流清单

| 工作流名称 | workflow_type | 功能描述 | 输入参数 |
|-----------|---------------|---------|---------|
| **一键生成** | 一键生成 | 一键完成全流程：热点→选题→文案→图片建议，直接生成最终成品 | publish_account（默认古典家具号） |
| 热点选题 | 热点选题 | 从热点日历+产品库读取→生成选题→写入选题库 | app_token、热点日历ID、产品表ID、选题库ID |
| 选题文案 | 选题文案 | 从选题库读取通过的选题→生成文案→写入内容库 | app_token、选题库ID、产品表ID、内容库ID |
| 客户故事 | 客户故事 | 手动输入客户信息→生成故事→写入内容库 | 客户背景、购买产品、购买原因、使用场景、反馈 |
| 图片建议 | 图片建议 | 从内容库读取待审核内容→生成图片建议→更新内容库 | app_token、内容库ID、产品表ID |
| 数据复盘 | 数据复盘 | 从数据复盘表读取本周数据→分析→生成选题建议 | app_token、复盘表ID、选题库ID |
| 内容整理 | 内容整理 | 从内容库读取数据→整理输出标题、正文、封面文案、图片建议、标签、发布账号 | app_token、内容库ID、筛选状态 |

## 节点清单

| 节点名 | 文件位置 | 类型 | 功能描述 |
|-------|---------|------|---------|
| **一键生成** | `graph.py` | agent | 一键完成选题+文案+图片建议全流程 |
| 热点选题 | `graph.py` | agent | 热点选题自动化 |
| 选题文案 | `graph.py` | agent | 选题文案自动化 |
| 客户故事 | `graph.py` | agent | 客户故事自动化 |
| 图片建议 | `graph.py` | agent | 图片建议自动化 |
| 数据复盘 | `graph.py` | agent | 数据复盘自动化 |
| 内容整理 | `graph.py` | task | 内容整理输出 |
| feishu_read | `nodes/feishu_read_node.py` | task | 飞书表格读取 |
| feishu_write | `nodes/feishu_write_node.py` | task | 飞书表格写入 |

**类型说明**: agent(大模型节点) / task(普通任务节点)

## 文件结构

```
src/graphs/
├── state.py                    # 状态定义：飞书读取/写入 + 7个工作流Input/Output
├── graph.py                    # 主图编排：条件路由到7个飞书自动化工作流
└── nodes/
    ├── __init__.py
    ├── feishu_read_node.py     # 飞书表格读取节点
    └── feishu_write_node.py    # 飞书表格写入节点
```

## 配置文件

| 配置文件 | 对应工作流 | 说明 |
|---------|-----------|------|
| config/feishu_hot_topic_cfg.json | 热点选题/一键生成 | 热点选题生成器提示词 |
| config/feishu_topic_post_cfg.json | 选题文案/一键生成 | 产品文案生成器提示词 |
| config/feishu_customer_story_cfg.json | 客户故事 | 客户故事生成器提示词 |
| config/feishu_image_suggestion_cfg.json | 图片建议 | 图片建议生成器提示词 |
| config/feishu_weekly_review_cfg.json | 数据复盘 | 数据复盘分析提示词 |

每个配置文件包含：
- `config`: 模型配置（model、temperature等）
- `sp`: 系统提示词（角色定义、任务目标、约束规则）
- `up`: 用户提示词模板（使用jinja2变量）

## 技能使用

| 节点 | 使用的技能 | 说明 |
|-----|-----------|------|
| 热点选题 | 大语言模型 + 飞书多维表格 | doubao-seed-2-0-pro-260215 |
| 选题文案 | 大语言模型 + 飞书多维表格 | doubao-seed-2-0-pro-260215 |
| 客户故事 | 大语言模型 + 飞书多维表格 | doubao-seed-2-0-pro-260215 |
| 图片建议 | 大语言模型 + 飞书多维表格 | doubao-seed-2-0-pro-260215 |
| 数据复盘 | 大语言模型 + 飞书多维表格 | doubao-seed-2-0-pro-260215 |
| feishu_read | 飞书多维表格 | 读取飞书表格数据 |
| feishu_write | 飞书多维表格 | 写入飞书表格数据 |

## 调用示例

### 1. 一键生成（推荐）
```json
{
  "workflow_type": "一键生成"
}
```
一键生成会自动完成全流程，默认参数已预填：
- 从热点日历读取可发布热点
- 从产品素材库读取可发布产品
- 生成选题方案并写入选题库
- 生成完整文案并写入内容库
- 自动生成图片建议
- 根据内容类型自动添加薯账号（家居薯、生活薯、知识薯等）

### 2. 热点选题
```json
{
  "workflow_type": "热点选题",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_hot_calendar_table_id": "tblT1KM0397UcGeM",
  "feishu_product_table_id": "tbllExTlKURFJP2j",
  "feishu_topic_table_id": "tblJNjx74uZ3s1vs",
  "target_audience": "25-35岁女性，喜欢传统文化和审美生活方式",
  "content_style": "新中式、克制、种草但不硬广"
}
```

### 2. 选题文案
```json
{
  "workflow_type": "选题文案",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_topic_table_id": "tblJNjx74uZ3s1vs",
  "feishu_product_table_id": "tbllExTlKURFJP2j",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "publish_account": "灵楠阁品牌号"
}
```

### 3. 客户故事
```json
{
  "workflow_type": "客户故事",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "customer_background": "30岁设计师",
  "purchased_product": "金丝楠手串",
  "purchase_reason": "生日礼物",
  "usage_scenario": "日常佩戴",
  "customer_feedback": "很喜欢"
}
```

### 4. 图片建议
```json
{
  "workflow_type": "图片建议",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "feishu_product_table_id": "tbllExTlKURFJP2j"
}
```

### 5. 数据复盘
```json
{
  "workflow_type": "数据复盘",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_review_table_id": "tblfSaXuLDh6OKEq",
  "feishu_topic_table_id": "tblJNjx74uZ3s1vs"
}
```

### 6. 内容整理
```json
{
  "workflow_type": "内容整理",
  "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
  "feishu_content_table_id": "tblg7zZuWKcUvqQX",
  "filter_status": "待审核",
  "page_size": 10
}
```

## 输出格式

所有工作流统一返回：

```json
{
  "workflow_type": "热点选题",
  "result": "执行结果描述",
  "processed_count": 1,
  "success_count": 1
}
```

## 飞书表格ID参考

| 表格名称 | table_id |
|---------|----------|
| 热点日历表 | tblT1KM0397UcGeM |
| 产品素材表 | tbllExTlKURFJP2j |
| 选题库 | tblJNjx74uZ3s1vs |
| 内容成品库 | tblg7zZuWKcUvqQX |
| 数据复盘表 | tblfSaXuLDh6OKEq |

**app_token**: `FoWqb7NLuah1gdssEHbc7Wk9nQh`