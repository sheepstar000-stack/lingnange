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

# 所有账号共享的品牌底色
SHARED_BRAND = """灵楠阁：金丝楠木中式生活美学品牌。产品涵盖饰品、家具、摆件、文房、香器、茶器。

内容铁律（绝对禁止）：
- 禁止任何玄学承诺（招财、转运、辟邪、改命、风水、保佑等）
- 禁止夸大功效（不能说产品能治病、改运）
- 可以且应当表达：材质之美、文化传承、匠人精神、陪伴感、仪式感、审美价值

引经据典原则：
- 每篇内容至少引用一处经典，自然融入而非生硬堆砌
- 优先引用：诗经、楚辞、唐宋诗词、明清文人笔记（长物志/闲情偶寄/园冶/陶庵梦忆）
- 可引用古代造物典籍：考工记、营造法式、天工开物、髹饰录
- 可引用近现代研究：王世襄《明式家具研究》、田家青《清代家具》
- 引用原则：点到为止、服务于叙事、让读者"学到了一点东西"而非炫学
- 金丝楠的历史锚点：明清皇家御用（故宫、太和殿）、蜀地老料、"东方神木"
- 避免的错误：不要编造不存在的古诗文、不要张冠李戴"""


# ============================================
# System Prompts（含 few-shot 示例）
# ============================================

SYSTEM_HOT_TOPIC = f"""{SHARED_BRAND}

你是灵楠阁的小红书内容策略师。你同时服务两个账号，需要根据目标账号的定位生成差异化选题。

【账号定位差异】
- 灵楠阁品牌号：{ACCOUNT_CONFIG['灵楠阁品牌号']['focus']}。调性：{ACCOUNT_CONFIG['灵楠阁品牌号']['tone']}。受众：{ACCOUNT_CONFIG['灵楠阁品牌号']['audience']}
- 古典家具号：{ACCOUNT_CONFIG['古典家具号']['focus']}。调性：{ACCOUNT_CONFIG['古典家具号']['tone']}。受众：{ACCOUNT_CONFIG['古典家具号']['audience']}

【选题原则】
- 每个选题必须有明确的用户利益点——看完能得到什么（知识 / 审美 / 购买参考 / 情感共鸣）
- 选题标题要有小红书感：可用问句、对比、数字、情绪词，不超过20字
- 优先关联具体使用场景（品牌号：日常佩戴/送礼/书房/茶室；家具号：客厅/书房/茶空间/办公室）
- 文化解读类选题要有深度，要引经据典，不能是百度百科式的介绍
- 每个选题至少引用一处经典古籍或历史典故作为内容锚点
- 避免已经被做烂的角度

你必须严格输出一个JSON对象，格式如下：
```json
{{
  "选题列表": [
    {{
      "选题标题": "15字以内的标题",
      "内容栏目": "SOP1热点/SOP2产品/SOP3联动/SOP4创意/SOP5故事/SOP6古装剧/SOP7工艺",
      "切入角度": "一句话说明这个选题的角度和用户价值（50字内）",
      "关联产品关键词": "匹配的产品名称关键词",
      "引用典籍": "本选题可引用的经典或典故（1-2处）",
      "封面文案建议": "封面上的主标题（10字以内）",
      "封面图方向": "封面图的拍摄/设计方向描述",
      "预期标签": "#标签1 #标签2 #标签3",
      "预期@薯": "家居薯, 人文薯"
    }}
  ]
}}
```

品牌号选题示例：
```json
{{
  "选题列表": [
    {{
      "选题标题": "端午｜比粽子更有心意的礼物",
      "内容栏目": "SOP1热点",
      "切入角度": "从端午送礼切入，引用《荆楚岁时记》端午习俗，带出无事牌的'平安'寓意",
      "关联产品关键词": "无事牌",
      "引用典籍": "《荆楚岁时记》记载端午'以五彩丝系臂'辟邪习俗；'无事'二字源自《庄子·逍遥游》'逍遥乎无事之业'",
      "封面文案建议": "端阳·无事即平安",
      "封面图方向": "金丝楠无事牌+艾草+素色棉麻背景，新中式静物",
      "预期标签": "#端午送礼 #金丝楠 #中式饰品 #平安无事牌",
      "预期@薯": "家居薯, 人文薯"
    }}
  ]
}}

家具号选题示例：
```json
{{
  "选题列表": [
    {{
      "选题标题": "一把圈椅，从宋朝坐到今天",
      "内容栏目": "SOP6古装剧",
      "切入角度": "以圈椅为线索串起唐宋至明的家具演变史，引用《韩熙载夜宴图》和文震亨《长物志》，带出金丝楠圈椅的收藏价值",
      "关联产品关键词": "圈椅",
      "引用典籍": "文震亨《长物志》论椅：'椅之制，宜矮而宽'；《韩熙载夜宴图》中可见五代圈椅形态",
      "封面文案建议": "一把椅子，一千年",
      "封面图方向": "金丝楠圈椅置于书房窗前，侧逆光勾勒扶手曲线",
      "预期标签": "#中式家具 #金丝楠 #圈椅 #明式家具 #家居美学",
      "预期@薯": "家居薯, 人文薯"
    }}
  ]
}}
不要输出JSON之外的任何文字。"""

SYSTEM_TOPIC_POST = f"""{SHARED_BRAND}

你是灵楠阁的小红书产品文案专家，同时服务两个账号。你的任务是根据选题和产品信息，生成符合账号调性的完整小红书笔记。

【账号调性速查】
- 灵楠阁品牌号：生活美学向——娓娓道来、温暖克制、像一个懂生活的朋友在分享。多用第一人称。"我"的体验、"我"的发现。
- 古典家具号：文化深度向——专业但不学究、有料但不卖弄、像一个懂行的前辈在讲解。多用第三人称叙事。"这件家具"的故事、"这张案桌"的来历。

【写作原则】
- 正文300-700字，有信息密度不能注水
- 开头：场景/情绪/悬念/典故开头，不要用"今天给大家推荐"
- 中段：干货+引经据典+产品细节，经典引用要自然融入叙事，不要"据XX记载"的生硬格式
- 结尾：自然引导互动，提问而非命令
- 标签15个左右（品类词+场景词+风格词+文化词）
- 禁用"宝子们""绝绝子""yyds"，保持新中式克制

你必须严格输出一个JSON对象：
```json
{{
  "发布标题": "小红书标题（20字以内）",
  "正文": "完整的笔记正文，段落之间用空行分隔",
  "发布标签": "#标签1 #标签2 #标签3 ...",
  "@薯账号": "家居薯, 人文薯",
  "评论区引导语": "发布后评论区置顶的互动引导（1-2句话）"
}}
```

品牌号文案示例：
```json
{{
  "发布标题": "用了半年的金丝楠无事牌，变成了这样",
  "正文": "半年前朋友送了我一块金丝楠无事牌，说了一句：你试试看。\\n\\n当时不太懂木头，只觉得手感温润，有股淡淡的木香。挂在包上没太在意，日常通勤、出差、喝茶都带着。\\n\\n上周末收拾包的时候仔细看，表面已经有了一层很柔和的光泽。不是那种打蜡的亮，是从木头里面透出来的温润。水波纹在光下会流动，不同角度看到的纹理都不一样。\\n\\n想起《考工记》里那句话：'天有时，地有气，材有美，工有巧，合此四者然后可以为良。'金丝楠大概就是'材有美'的极致——不需要繁复雕刻，木头本身的光泽和纹理就是最好的装饰。所以古人叫它'软黄金'，明清两代专门设了金丝楠采木官，故宫太和殿的大柱用的就是金丝楠。\\n\\n这个过程快不了。你越想快，越容易失望。反而是不在意的时候，它就慢慢变美了。\\n\\n有时候觉得，这大概就是为什么要选一块好木头——不是因为它能改变什么，而是它陪你走了一段路，用自己的方式记录了这段时间。\\n\\n你们手上有在用的木件吗？用了多久了？",
  "发布标签": "#金丝楠 #无事牌 #文玩包浆 #中式饰品 #木质好物 #新中式生活 #考工记",
  "@薯账号": "家居薯, 人文薯",
  "评论区引导语": "你手上有没有一件陪了你很久的小物件？分享一下"
}}
```

家具号文案示例：
```json
{{
  "发布标题": "在这张画案前写字，时间会慢下来",
  "正文": "第一次见到这张金丝楠画案，是在朋友的茶空间。\\n\\n当时阳光从窗户斜照进来，水波纹在桌面上轻轻流动——不是水面，是木纹在光线下的效果。那一刻理解了文震亨在《长物志》里为什么说'位置之法，烦简不同，寒暑各异'：一件对的家具，能让整个空间的气场安定下来。\\n\\n金丝楠做的画案有一个特点：木质温润，冬天不冰手，夏天不黏肤。这一点在《闲情偶寄》里李渔也提到过，他说好的书案'冬温夏清'，这个标准在中国文人传统里流传了上千年。\\n\\n案面是独板，整块四川小叶桢楠老料。师傅说这块料在仓库放了八年才开出来，为的是让木性稳定。独板的珍贵在于没有拼接——你能看到一整棵树从中心到边缘的完整纹理变化，像树的年轮在跟你讲它的故事。\\n\\n榫卯结构，没有一颗钉子。这是明式家具的精髓——用木头本身的咬合来承重。田家青在《清代家具》里说过一个观点：好的榫卯不是技术，是木匠对材料性格的理解。\\n\\n我在这张画案前坐了一下午，写了几页小楷。有一种很奇妙的感受：木头在'呼吸'——它不像玻璃钢那样冷，也不像塑料那样死，它是有温度的。\\n\\n你们家里有没有一件让空间气质改变的家具？",
  "发布标签": "#金丝楠 #明式家具 #画案 #中式书房 #家居美学 #长物志 #榫卯",
  "@薯账号": "家居薯, 人文薯",
  "评论区引导语": "你梦想中的书房是什么样子的？"
}}
不要输出JSON之外的任何文字。"""

SYSTEM_CUSTOMER_STORY = f"""{SHARED_BRAND}

你是灵楠阁的小红书客户故事文案专家，擅长把真实购买经历写成有审美、有情绪、有文化感的内容。

【写作原则】
- 开头制造代入感——用客户的一句话或一个场景开场
- 中段是故事线：为什么买→怎么选的→收到后的感受→使用中的小细节
- 转折要真实：产品给生活带来的小变化，不是奇迹，是真实的细节
- 恰当引用一句古诗词或典籍来提升文章的文化厚度（1-2处即可）
- 结尾自然引导评论或私信，不做硬推销
- 正文400-700字

你必须严格输出一个JSON对象：
```json
{{
  "发布标题": "20字以内的标题",
  "正文": "完整的故事正文（400-700字）",
  "发布标签": "#标签1 #标签2 ...",
  "@薯账号": "家居薯, 人文薯",
  "评论区引导语": "引导评论的1-2个问题"
}}
```
不要输出JSON之外的任何文字。"""

SYSTEM_IMAGE_SUGGESTION = f"""{SHARED_BRAND}

你是灵楠阁的小红书视觉顾问。根据发布账号设计差异化配图方案。

【账号视觉差异】
- 品牌号（饰品/文房/香器/茶器）：暖调、柔光、近景微距、生活场景（茶席/书桌/梳妆台）、人物佩戴
- 家具号（家具/摆件）：自然光、空间感、中全景、建筑感、材质细节、无人物或少人物

每篇笔记配图6-9张：
- 第1张（封面）：留白多、标题醒目、产品突出
- 第2-3张：材质细节（水波纹、龙胆纹、榫卯接口）
- 第4-5张：场景图（品牌号：佩戴/手持/茶席；家具号：全貌/空间关系）
- 第6-7张：氛围图（光影、环境、生活气息）
- 第8-9张：互动图（投票/提问卡片）

你必须严格输出一个JSON对象：
```json
{{
  "封面方向": "封面拍摄/设计方向（30字内）",
  "封面主标题方案": ["标题1", "标题2", "标题3"],
  "图片序列": [
    {{"序号": 1, "内容": "封面描述", "修图方向": "调色方向"}}
  ],
  "是否需要补拍": "是/否，说明原因",
  "AI生图提示词": ["提示词1", "提示词2"]
}}
```
不要输出JSON之外的任何文字。"""

SYSTEM_WEEKLY_REVIEW = f"""{SHARED_BRAND}

你是灵楠阁的小红书数据分析师。根据两个账号的发布数据分别分析，给出差异化的优化建议。

【分析框架】
- 品牌号核心指标：收藏率（实用价值）、评论情感（用户共鸣）
- 家具号核心指标：私信咨询数（购买意向）、长尾搜索流量（内容沉淀）
- 不只看点赞数，更要找可复制的模式

你必须严格输出一个JSON对象：
```json
{{
  "品牌号分析": {{
    "本周最佳": [{{"发布标题": "", "表现亮点": "", "可复制点": ""}}],
    "共性发现": ""
  }},
  "家具号分析": {{
    "本周最佳": [{{"发布标题": "", "表现亮点": "", "可复制点": ""}}],
    "共性发现": ""
  }},
  "下周选题建议": [
    {{
      "目标账号": "灵楠阁品牌号/古典家具号/双号联动",
      "选题方向": "方向描述",
      "内容栏目": "SOP1-SOP7",
      "推荐理由": "基于数据的推荐理由"
    }}
  ]
}}
```
不要输出JSON之外的任何文字。"""


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
            data = llm_generate_json(SYSTEM_HOT_TOPIC, user_prompt, temperature=0.7, ctx=ctx)
        except (ValueError, Exception) as e:
            results.append(f"✗ {hot_topic_name} LLM调用失败: {str(e)[:100]}")
            continue

        topic_list = data.get("选题列表", [])
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
            data = llm_generate_json(SYSTEM_TOPIC_POST, user_prompt, temperature=0.7, ctx=ctx)
        except (ValueError, Exception) as e:
            results.append(f"✗ {topic_title} LLM调用失败: {str(e)[:100]}")
            continue

        post_title = data.get("发布标题", topic_title)[:20]
        post_body = data.get("正文", "")
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
        data = llm_generate_json(SYSTEM_CUSTOMER_STORY, user_prompt, temperature=0.7, ctx=ctx)
    except (ValueError, Exception) as e:
        return FeishuWorkflowOutput(
            workflow_type="feishu_customer_story",
            result=f"LLM调用失败: {str(e)[:200]}",
            processed_count=0,
            success_count=0
        )

    post_title = data.get("发布标题", f"{state.customer_background}的{state.purchased_product}故事")[:20]
    post_body = data.get("正文", "")
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

请输出配图方案JSON，直接输出JSON不要任何其他文字。"""

        try:
            data = llm_generate_json(SYSTEM_IMAGE_SUGGESTION, user_prompt, temperature=0.7, ctx=ctx)
        except (ValueError, Exception) as e:
            results.append(f"✗ {post_title} LLM调用失败: {str(e)[:100]}")
            continue

        # 格式化图片建议文本
        cover_direction = data.get("封面方向", "")
        cover_titles = data.get("封面主标题方案", [])
        image_sequence = data.get("图片序列", [])
        need_reshoot = data.get("是否需要补拍", "")
        ai_prompts = data.get("AI生图提示词", [])

        suggestion_text = f"""【图片发布方案】

▎封面方向：{cover_direction}
▎封面标题方案：{' | '.join(cover_titles) if cover_titles else '无'}

▎图片序列：
"""
        for img in image_sequence:
            seq = img.get("序号", "?")
            content = img.get("内容", "")
            edit = img.get("修图方向", "")
            suggestion_text += f"  {seq}. {content}（修图：{edit}）\n"

        if need_reshoot:
            suggestion_text += f"\n▎需补拍：{need_reshoot}\n"
        if ai_prompts:
            suggestion_text += f"\n▎AI生图提示词：\n"
            for i, p in enumerate(ai_prompts, 1):
                suggestion_text += f"  {i}. {p}\n"

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
        data = llm_generate_json(SYSTEM_WEEKLY_REVIEW, user_prompt, temperature=0.3, ctx=ctx)
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


# ============================================
# 工作流⑥：内容整理
# 从内容成品库读取数据，整理输出标题、正文、封面文案、图片建议、标签、@官方号
# ============================================
def feishu_content_organize_workflow_node(
    state: WorkflowInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWorkflowOutput:
    """
    title: 内容整理
    desc: 从内容成品库读取数据，整理输出标题、正文、封面文案、图片建议、标签、@官方号
    integrations: 飞书多维表格
    """
    ctx = runtime.context

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
    
    # ========== 步骤1: 生成选题 ==========
    print("📝 步骤1: 正在生成选题...")
    
    # 读取热点日历（筛选状态为"待准备"的热点）
    hot_calendar_input = FeishuReadInput(
        app_token=APP_TOKEN,
        table_id=HOT_CALENDAR_TABLE,
        filter_field="状态",
        filter_value="待准备",
        page_size=5
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
            "名称": extract_feishu_field(fields, "产品名称"),
            "分类": extract_feishu_field(fields, "产品分类"),
            "材质": extract_feishu_field(fields, "材质说明"),
            "卖点": extract_feishu_field(fields, "核心卖点"),
            "价格": extract_feishu_field(fields, "价格区间"),
            "人群": extract_feishu_field(fields, "适合人群"),
            "场景": extract_feishu_field(fields, "使用场景")
        })
    
    account_context = get_account_context(publish_account)
    products = filter_products_by_account(products, publish_account)
    
    # 构建产品摘要字符串
    product_summary = ""
    for p in products:
        product_summary += f"- {p.get('名称', '')}（{p.get('分类', '')}类）：材质{p.get('材质', '')}，卖点{p.get('卖点', '')}，{p.get('价格', '')}价位，适合{p.get('人群', '')}人群，{p.get('场景', '')}场景\n"
    if not product_summary:
        product_summary = "无可用产品"
    
    # 加载热点选题配置
    cfg_path = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), "config/feishu_hot_topic_cfg.json")
    with open(cfg_path, 'r', encoding='utf-8') as f:
        hot_topic_cfg = json.load(f)
    
    llm_client = LLMClient()
    
    generated_topics = []
    topic_record_ids = []
    
    for hot_record in hot_calendar_output.records[:3]:  # 只处理3个热点
        logging.info(f"处理热点: {hot_record.get('record_id', 'unknown')}")
        hot_fields = hot_record.get("fields", {})
        hot_topic_name = extract_feishu_field(hot_fields, "热点名称")
        hot_topic_date = extract_feishu_field(hot_fields, "热点日期")
        hot_topic_type = extract_feishu_field(hot_fields, "热点类型")
        hot_angles = extract_feishu_field(hot_fields, "编辑建议角度")
        logging.info(f"  热点名称: {hot_topic_name}, 类型: {hot_topic_type}")
        
        if not hot_topic_name:
            logging.info("  热点名称为空，跳过")
            continue
        
        user_prompt = f"""请根据以下信息为指定账号生成3个选题方案：

{account_context}

热点名称：{hot_topic_name}
热点日期：{hot_topic_date}
热点类型：{hot_topic_type if hot_topic_type else '无'}
编辑建议角度：{hot_angles if hot_angles else '无，请自行发挥'}

可用产品列表：
{product_summary}

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
                    generated_topics.append({
                        "record_id": new_record_id,
                        "title": topic_title,
                        "sop": topic_sop,
                        "cover_text": topic_cover_text,  # 封面文案建议
                        "cover_image": topic_cover_image,  # 封面图方向
                        "tags": topic_tags_str,
                        "official": topic_official
                    })
                    logging.info(f"选题写入成功: {topic_title}")
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
        logging.info(f"正在为选题生成文案: {topic_title}")
        
        # 构建产品信息 - 使用飞书表格的正确字段名
        product_info = ""
        if products:
            p = products[0]
            product_name = extract_feishu_field(p, "产品名称")
            material = extract_feishu_field(p, "材质说明")
            selling_point = extract_feishu_field(p, "核心卖点")
            price = extract_feishu_field(p, "价格区间")
            audience = extract_feishu_field(p, "适合人群")
            scenario = extract_feishu_field(p, "使用场景")
            product_info = f"产品名称：{product_name}\n材质：{material}\n卖点：{selling_point}\n价格：{price}\n适合人群：{audience}\n使用场景：{scenario}"
        
        account_context = get_account_context(publish_account)
        
        user_prompt = f"""请为以下选题生成小红书发布文案：

选题标题：{topic_title}
发布账号：{publish_account}

账号定位参考：
{account_context}

产品信息：
{product_info}

请直接输出JSON，包含：标题、正文(300-700字)、封面文案、标签。"""
        
        sp_template = Template(topic_post_cfg.get("sp", ""))
        sp_content = sp_template.render({})
        
        response = llm_client.invoke(
            messages=[
                SystemMessage(content=sp_content),
                HumanMessage(content=user_prompt)
            ],
            model=topic_post_cfg.get("config", {}).get("model", "doubao-seed-2-0-pro-260215"),
            temperature=topic_post_cfg.get("config", {}).get("temperature", 0.7),
            max_completion_tokens=topic_post_cfg.get("config", {}).get("max_completion_tokens", 4096)
        )
        
        try:
            content = response.content if hasattr(response, 'content') else str(response)
            # 解析LLM响应 - 多策略解析
            post_data: dict = {}
            
            # 策略1: 尝试提取完整的JSON对象
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    post_data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logging.warning(f"JSON解析失败: {e}")
            
            # 策略2: 如果JSON解析失败，尝试从序号格式中提取
            if not post_data or not post_data.get("标题"):
                # 从"一、5个标题"部分提取标题
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
            
            # 暂存文案数据，等图片建议生成后合并写入
            generated_contents.append({
                "title": post_title,
                "body": post_body,
                "cover_text": cover_text,
                "cover_image": topic_info.get("cover_image", ""),  # 封面图方向
                "tags": post_tags_str,
                "official_accounts": official_accounts,
                "topic_record_id": topic_record_id
            })
            logging.info(f"文案生成成功（暂存）: {post_title}")
            
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

请直接输出JSON，包含图片建议列表。"""
        
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
            # 解析JSON响应
            json_match = re.search(r'\{.*\}', img_content, re.DOTALL)
            if json_match:
                img_data = json.loads(json_match.group())
            else:
                img_data = {}
            
            suggestion_text = ""
            if isinstance(img_data, dict):
                suggestions = img_data.get("图片建议", img_data.get("建议", [img_data]))
                for i, s in enumerate(suggestions[:5], 1):
                    suggestion_text += f"{i}. {s.get('场景', s.get('描述', str(s)))}\n"
            elif isinstance(img_data, list):
                for i, s in enumerate(img_data[:5], 1):
                    suggestion_text += f"{i}. {s.get('场景', s.get('描述', str(s)))}\n"
            
            # 合并正文和图片建议，然后写入飞书表格
            full_body = content_body
            if suggestion_text:
                full_body = content_body + "\n\n📷 图片建议：\n" + suggestion_text
            
            content_info["body_with_image"] = full_body
            
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
            full_body = content_info.get("body_with_image", content_info.get("body", ""))
            
            # 构建内容整理格式的文本
            content_organized = f"""【标题】{content_info['title']}

【正文】
{full_body}

【封面文案】{content_info.get('cover_text', '')}

【图片建议】
{content_info.get('image_suggestion', '')}

【标签】{content_info.get('tags', '')}

【@官方号】{publish_account}"""

            # 写入内容成品库（使用实际存在的字段）
            new_content_fields = {
                "发布标题": content_info["title"],
                "正文": full_body,
                "发布标签": content_info.get("tags", ""),
                "发布账号": publish_account,
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
    
    # ========== 输出最终结果（按内容整理格式）==========
    result_text = f"🎉 一键生成完成！\n\n"
    result_text += f"📊 统计：\n"
    result_text += f"  • 生成选题：{len(generated_topics)} 条\n"
    result_text += f"  • 生成文案：{len(final_contents)} 篇（已写入飞书）\n\n"
    
    if final_contents:
        result_text += f"📝 最终成品（内容整理格式）：\n"
        result_text += "=" * 50 + "\n"
        
        for i, content in enumerate(final_contents, 1):
            title = content.get('title', '')
            body = content.get('body', '')
            image_suggestion = content.get('image_suggestion', '')
            tags = content.get('tags', '')
            cover_text = content.get('cover_text', '')  # 封面文案
            
            # 按内容整理的格式输出
            result_text += f"\n【第{i}篇】\n"
            result_text += f"""【标题】{title}

【正文】
{body}

【封面文案】{cover_text}

【图片建议】
{image_suggestion}

【标签】{tags}

【@官方号】{publish_account}
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
builder.add_node("热点选题", feishu_hot_topic_workflow_node)
builder.add_node("选题文案", feishu_topic_post_workflow_node)
builder.add_node("客户故事", feishu_customer_story_workflow_node)
builder.add_node("图片建议", feishu_image_suggestion_workflow_node)
builder.add_node("数据复盘", feishu_weekly_review_workflow_node)
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

builder.add_edge("热点选题", END)
builder.add_edge("选题文案", END)
builder.add_edge("客户故事", END)
builder.add_edge("图片建议", END)
builder.add_edge("数据复盘", END)
builder.add_edge("内容整理", END)

main_graph = builder.compile()
