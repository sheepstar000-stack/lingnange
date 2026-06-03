"""
图片/封面建议器节点
为每篇内容生成图片拍摄/制作方案，指导设计执行
"""

import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import ImageSuggestionInput, ImageSuggestionOutput


def image_suggestion_node(
    state: ImageSuggestionInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ImageSuggestionOutput:
    """
    title: 图片/封面建议器
    desc: 为小红书笔记设计图片发布方案，包含封面选择、多图排序、修图方向、补拍建议和AI生图提示词
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
        "product_name": state.product_name,
        "image_description": state.image_description,
        "content_theme": state.content_theme,
        "account": state.account
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
        temperature=llm_config.get("temperature", 0.7),
        top_p=llm_config.get("top_p", 0.9),
        max_completion_tokens=llm_config.get("max_completion_tokens", 6000)
    )
    
    # 处理响应内容
    if isinstance(response.content, str):
        result = response.content
    elif isinstance(response.content, list):
        text_parts = []
        for item in response.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        result = " ".join(text_parts)
    else:
        result = str(response.content)
    
    return ImageSuggestionOutput(result=result)
