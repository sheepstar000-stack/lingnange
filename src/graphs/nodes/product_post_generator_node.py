"""
产品发布文案生成器节点
从产品库选品后自动生成完整小红书笔记内容包
"""

import os
import json
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient

from graphs.state import ProductPostInput, ProductPostOutput


def product_post_generator_node(
    state: ProductPostInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ProductPostOutput:
    """
    title: 产品发布文案生成器
    desc: 为产品生成完整的小红书笔记内容包，包含5种类型标题、正文、封面文案、图片建议、标签和风险词提醒
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
        "product_material": state.product_material,
        "product_selling_points": state.product_selling_points,
        "suitable_scenarios": state.suitable_scenarios,
        "target_audience": state.target_audience,
        "price_range": state.price_range,
        "reference_copy": state.reference_copy or "无",
        "publish_account": state.publish_account
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
        text_parts = []
        for item in response.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        result = " ".join(text_parts)
    else:
        result = str(response.content)
    
    return ProductPostOutput(result=result)
