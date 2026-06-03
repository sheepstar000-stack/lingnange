"""
每周数据复盘器节点
每周日基于数据复盘表自动分析两个账号的内容表现，输出优化建议
"""

import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import WeeklyReviewInput, WeeklyReviewOutput


def weekly_review_node(
    state: WeeklyReviewInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> WeeklyReviewOutput:
    """
    title: 每周数据复盘器
    desc: 分析两个账号的内容表现，输出数据驱动的优化建议，包含表现分析、栏目分析、标题结构分析、选题建议和发布排期
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
        "weekly_data": state.weekly_data,
        "last_week_data": state.last_week_data or "无上周数据"
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
        temperature=llm_config.get("temperature", 0.5),
        top_p=llm_config.get("top_p", 0.9),
        max_completion_tokens=llm_config.get("max_completion_tokens", 8000)
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
    
    return WeeklyReviewOutput(result=result)
