"""
飞书多维表格写入节点
将生成的内容写入飞书表格
"""

import requests
from functools import wraps
from typing import Dict, Any

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from cozeloop.decorator import observe
from coze_workload_identity import Client

from graphs.state import FeishuWriteInput, FeishuWriteOutput


def get_feishu_access_token() -> str:
    """获取飞书多维表格的访问令牌"""
    client = Client()
    access_token = client.get_integration_credential("integration-feishu-base")
    return access_token


class FeishuBitableWriter:
    """飞书多维表格写入客户端"""
    
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
    
    def add_record(self, app_token: str, table_id: str, fields: Dict[str, Any]) -> dict:
        """
        新增一条记录
        
        Args:
            app_token: 多维表格的app_token
            table_id: 数据表的table_id
            fields: 字段数据，如 {"选题标题": "xxx", "正文": "yyy"}
        
        Returns:
            创建的记录信息
        """
        body = {
            "records": [{
                "fields": fields
            }]
        }
        return self._request("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create", json=body)
    
    def update_record(self, app_token: str, table_id: str, record_id: str, fields: Dict[str, Any]) -> dict:
        """
        更新一条记录
        
        Args:
            app_token: 多维表格的app_token
            table_id: 数据表的table_id
            record_id: 要更新的记录ID
            fields: 要更新的字段数据
        
        Returns:
            更新后的记录信息
        """
        body = {
            "records": [{
                "record_id": record_id,
                "fields": fields
            }]
        }
        return self._request("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update", json=body)


def feishu_write_node(
    state: FeishuWriteInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FeishuWriteOutput:
    """
    title: 飞书表格写入
    desc: 将生成的内容写入飞书多维表格
    integrations: 飞书多维表格
    """
    ctx = runtime.context
    
    try:
        writer = FeishuBitableWriter()
        
        if state.record_id:
            # 更新已有记录
            result = writer.update_record(
                app_token=state.app_token,
                table_id=state.table_id,
                record_id=state.record_id,
                fields=state.fields
            )
            record_id = result.get("data", {}).get("records", [{}])[0].get("record_id", "")
            return FeishuWriteOutput(
                success=True,
                record_id=record_id,
                message="更新记录成功"
            )
        else:
            # 新增记录
            result = writer.add_record(
                app_token=state.app_token,
                table_id=state.table_id,
                fields=state.fields
            )
            record_id = result.get("data", {}).get("records", [{}])[0].get("record_id", "")
            return FeishuWriteOutput(
                success=True,
                record_id=record_id,
                message="新增记录成功"
            )
    except Exception as e:
        return FeishuWriteOutput(
            success=False,
            record_id="",
            message=f"写入失败: {str(e)}"
        )
