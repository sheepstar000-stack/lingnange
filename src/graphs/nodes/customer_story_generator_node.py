"""
客户故事生成器节点
将真实客户购买经历转化为有审美、有情绪的小红书故事笔记
"""

import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import CustomerStoryInput, CustomerStoryOutput


def customer_story_generator_node(
    state: CustomerStoryInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> CustomerStoryOutput:
    """
    title: 客户故事生成器
    desc: 将真实客户购买经历转化为有温度的小红书故事笔记，包含5种类型标题、正文、封面文案、标签和互动问题
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
        "customer_background": state.customer_background,
        "purchased_product": state.purchased_product,
        "purchase_reason": state.purchase_reason,
        "usage_scenario": state.usage_scenario,
        "customer_feedback": state.customer_feedback,
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
        temperature=llm_config.get("temperature", 0.85),
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
    
    return CustomerStoryOutput(result=result)
