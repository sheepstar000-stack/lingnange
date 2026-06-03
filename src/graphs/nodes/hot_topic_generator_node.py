"""
热点选题生成器节点
根据节日、节气、热播剧、传统文化热点生成小红书选题
"""

import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import HotTopicInput, HotTopicOutput


def hot_topic_generator_node(
    state: HotTopicInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> HotTopicOutput:
    """
    title: 热点选题生成器
    desc: 根据节日、节气、热播剧、传统文化热点生成小红书选题，包含10个选题方案、标题、切入角度、产品匹配、封面文案、图片建议和标签
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config["metadata"]["llm_cfg"]
    )
    with open(cfg_file, "r", encoding="utf-8") as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up = _cfg.get("up", "")
    
    # 使用jinja2模板渲染用户提示词
    up_tpl = Template(up)
    user_prompt = up_tpl.render({
        "hot_topic_name": state.hot_topic_name,
        "hot_topic_date": state.hot_topic_date,
        "account": state.account,
        "available_products": state.available_products,
        "target_audience": state.target_audience,
        "content_style": state.content_style
    })
    
    # 构建消息
    messages = [
        SystemMessage(content=sp),
        HumanMessage(content=user_prompt)
    ]
    
    # 调用大模型
    client = LLMClient(ctx=ctx)
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.8),
        top_p=llm_config.get("top_p", 0.9),
        max_completion_tokens=llm_config.get("max_completion_tokens", 8000)
    )
    
    # 处理响应内容
    if isinstance(response.content, str):
        result = response.content
    elif isinstance(response.content, list):
        # 处理多模态响应
        text_parts = []
        for item in response.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        result = " ".join(text_parts)
    else:
        result = str(response.content)
    
    return HotTopicOutput(result=result)
