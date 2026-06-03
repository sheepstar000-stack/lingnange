"""
飞书多维表格读取节点
从飞书表格读取待处理的记录
"""

import requests
from functools import wraps
from typing import Optional, List, Dict, Any

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from cozeloop.decorator import observe
from coze_workload_identity import Client

from graphs.state import FeishuReadInput, FeishuReadOutput


def get_feishu_access_token() -> str:
    """获取飞书多维表格的访问令牌"""
    client = Client()
    access_token = client.get_integration_credential("integration-feishu-base")
    return access_token


class FeishuBitableReader:
    """飞书多维表格读取客户端"""
    
    def __init__(self, base_url: str = "https://open.larkoffice.com/open-apis", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.access_token = get_feishu_access_token()
    
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else "",
            "Content-Type": "application/json; charset=utf-8",
        }
    
    @observe
    def _request(self, method: str, path: str, params: dict = None, json: dict = None) -> dict:
        try:
            url = f"{self.base_url}{path}"
            resp = requests.request(method, url, headers=self._headers(), params=params, json=json, timeout=self.timeout)
            resp_data = resp.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"FeishuBitable API request error: {e}")
        if resp_data.get("code") != 0:
            raise Exception(f"FeishuBitable API error: {resp_data}")
        return resp_data
    
    def search_records(
        self,
        app_token: str,
        table_id: str,
        filter_field: str = "",
        filter_value: str = "",
        page_size: int = 100
    ) -> dict:
        """
        搜索符合条件的记录
        
        Args:
            app_token: 多维表格的app_token
            table_id: 数据表的table_id
            filter_field: 筛选字段名（为空则不筛选）
            filter_value: 筛选字段值
            page_size: 分页大小，最大500
        
        Returns:
            包含记录列表的响应数据
        """
        body = {
            "page_size": page_size
        }
        
        # 只有当筛选字段和值都不为空时才添加筛选条件
        if filter_field and filter_value:
            body["filter"] = {
                "conditions": [{
                    "field_name": filter_field,
                    "operator": "is",
                    "value": [filter_value]
                }],
                "conjunction": "and"
            }
        
        return self._request("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/search", json=body)
    
    def list_fields(self, app_token: str, table_id: str) -> dict:
        """列出数据表所有字段"""
        return self._request("GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields")


def feishu_read_node(
    state: FeishuReadInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuReadOutput:
    """
    title: 飞书表格读取
    desc: 从飞书多维表格读取待处理的记录
    integrations: 飞书多维表格
    """
    ctx = runtime.context
    
    try:
        reader = FeishuBitableReader()
        
        # 搜索符合条件的记录
        result = reader.search_records(
            app_token=state.app_token,
            table_id=state.table_id,
            filter_field=state.filter_field,
            filter_value=state.filter_value
        )
        
        items = result.get("data", {}).get("items", [])
        
        return FeishuReadOutput(
            records=items,
            record_count=len(items)
        )
    except Exception as e:
        return FeishuReadOutput(
            records=[],
            record_count=0
        )
