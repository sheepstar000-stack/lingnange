#!/usr/bin/env python3
"""
灵楠阁内容生成控制脚本
使用方法：python control.py
"""

import requests
import json

# API配置
API_URL = "https://jv7dr2vk3d.coze.site/run"
API_TOKEN = ""  # 请填写你的API Token

# 默认参数配置
DEFAULT_PARAMS = {
    "热点选题": {
        "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
        "feishu_hot_calendar_table_id": "tblT1KM0397UcGeM",
        "feishu_product_table_id": "tbllExTlKURFJP2j",
        "feishu_topic_table_id": "tblJNjx74uZ3s1vs"
    },
    "选题文案": {
        "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
        "feishu_topic_table_id": "tblJNjx74uZ3s1vs",
        "feishu_product_table_id": "tbllExTlKURFJP2j",
        "feishu_content_table_id": "tblg7zZuWKcUvqQX"
    },
    "客户故事": {
        "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
        "feishu_content_table_id": "tblg7zZuWKcUvqQX",
        "customer_background": "",
        "purchased_product": "",
        "purchase_reason": "",
        "usage_scenario": "",
        "customer_feedback": ""
    },
    "图片建议": {
        "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
        "feishu_content_table_id": "tblg7zZuWKcUvqQX"
    },
    "数据复盘": {
        "feishu_app_token": "FoWqb7NLuah1gdssEHbc7Wk9nQh",
        "feishu_review_table_id": "tblfSaXuLDh6OKEq",
        "feishu_topic_table_id": "tblJNjx74uZ3s1vs"
    }
}


def run_workflow(workflow_type: str, custom_params: dict = None):
    """运行工作流"""
    if not API_TOKEN:
        print("❌ 请先设置API_TOKEN")
        return
    
    # 合并参数
    params = DEFAULT_PARAMS.get(workflow_type, {})
    if custom_params:
        params.update(custom_params)
    params["workflow_type"] = workflow_type
    
    print(f"\n🚀 正在运行工作流: {workflow_type}")
    print("⏳ 请稍候...")
    
    try:
        response = requests.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_TOKEN}"
            },
            json=params,
            timeout=300  # 5分钟超时
        )
        
        result = response.json()
        
        if result.get("error") or result.get("message"):
            print(f"\n❌ 执行失败: {result.get('error') or result.get('message')}")
        else:
            print(f"\n✅ 执行成功!")
            print(f"\n结果:\n{result.get('result', json.dumps(result, indent=2, ensure_ascii=False))}")
        
        return result
        
    except requests.exceptions.Timeout:
        print("\n❌ 请求超时，请稍后重试")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求失败: {e}")
    except json.JSONDecodeError:
        print("\n❌ 响应解析失败")


def main():
    print("=" * 50)
    print("   灵楠阁 - 小红书内容生成控制面板")
    print("=" * 50)
    
    if not API_TOKEN:
        print("\n⚠️  请先在脚本顶部设置 API_TOKEN")
        print("   API Token 从 Coze 平台部署详情页获取")
        return
    
    while True:
        print("\n请选择工作流:")
        print("  1. 热点选题")
        print("  2. 选题文案")
        print("  3. 客户故事")
        print("  4. 图片建议")
        print("  5. 数据复盘")
        print("  0. 退出")
        
        choice = input("\n输入编号: ").strip()
        
        workflow_map = {
            "1": "热点选题",
            "2": "选题文案",
            "3": "客户故事",
            "4": "图片建议",
            "5": "数据复盘"
        }
        
        if choice == "0":
            print("👋 再见!")
            break
        elif choice in workflow_map:
            workflow = workflow_map[choice]
            
            # 客户故事需要额外输入
            if workflow == "客户故事":
                print("\n请输入客户故事相关信息:")
                customer_background = input("客户背景: ").strip()
                purchased_product = input("购买产品: ").strip()
                purchase_reason = input("购买原因: ").strip()
                usage_scenario = input("使用场景: ").strip()
                customer_feedback = input("客户反馈: ").strip()
                
                custom_params = {
                    "customer_background": customer_background,
                    "purchased_product": purchased_product,
                    "purchase_reason": purchase_reason,
                    "usage_scenario": usage_scenario,
                    "customer_feedback": customer_feedback
                }
                run_workflow(workflow, custom_params)
            else:
                run_workflow(workflow)
        else:
            print("❌ 无效选择，请重新输入")


if __name__ == "__main__":
    main()