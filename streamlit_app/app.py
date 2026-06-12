import streamlit as st
import requests
import json
import os
import sys

# 添加项目路径以导入飞书读取模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# API配置
API_URL = 'https://jv7dr2vk3d.coze.site/run'
TOKEN = 'eyJhbGciOiJSUzI1NiIsImtpZCI6ImMwNTQ1ZjM1LWY0M2YtNDU1OS1iNmUzLTc3ODc1MTFiZDc4YiJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbIlpoZFlSU0NXMVlLZEhvNmNaVWlDaXpjMVY0M2dGUkRvIl0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzgwODk4NTYwLCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3NjQ3MDEzMzg4NjAxNTI0MjI0Iiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3NjQ4OTAxMDcyNzMxMjQyNTAyIn0.FBHQs6vSVwDqTteTyqXNANC5-sOTi00OUeiPF6zRE_uPU3Bf5J7NmhF3acywTh4Tqb8yYJ5cqJWlPf-vdBJOevaX4lZxwzMk3ybICThjC7lCCEd9jvjw2rBinv_0OGYfL9jonIWwo4L6AGIeM1qkOGityYIrau8iFffhTlpkVTCYNKM3cpWH3RV2AIdp3wJBMll6jSJnYZLCws7aT9C1v9LQQrzWzfmVPSunbGOAiARv95u2tSjR32MEkJqKaCkWg2oKy1hMdKSE8kkcZ_3xZA304xcm0jjZrZxNhNhOVjRiruz0zWPjCIoSN8oUPCz0Ibdge4-QnMrTwDQPfR4bLg'

# 预填飞书表格ID
FEISHU_CONFIG = {
    'app_token': 'HF7dYv7ubaLkWss7d3fVcA4ynugcqhJJfAbpmc',
    'product_table_id': 'tbllExTlKURFJP2j',
    'topic_table_id': 'tblJNjx74uZ3s1vs',
    'content_table_id': 'tblsCeJXz0OcL01T',
    'review_table_id': 'tblZ3EZ74uZ3s1vs',
    'hot_calendar_table_id': 'tblT1KM0397UcGeM'
}

# 页面配置（必须放在最前面）
st.set_page_config(
    page_title='灵楠阁 · 内容生成助手',
    page_icon='🎋',
    layout='wide',
    initial_sidebar_state='collapsed'
)

# 自定义CSS样式
st.markdown("""
<style>
    /* 全局背景 */
    .stApp {
        background: linear-gradient(135deg, #f5f0e8 0%, #e8e0d5 100%);
    }
    
    /* 主容器 */
    .block-container {
        padding-top: 1.5rem !important;
        max-width: 1100px !important;
    }
    
    /* 标题样式 */
    .main-title {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #4a3728 !important;
        text-align: center;
        margin-bottom: 0.2rem !important;
    }
    
    .sub-title {
        font-size: 1rem !important;
        color: #7a6a5a !important;
        text-align: center;
        margin-bottom: 1.5rem !important;
    }
    
    /* 卡片样式 */
    .card {
        background: #fffdf8;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(74, 55, 40, 0.08);
        border: 1px solid #e8e0d5;
        margin-bottom: 1rem;
    }
    
    /* Tab样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #fffdf8;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 500;
        color: #7a6a5a;
        border: 1px solid #e8e0d5;
        border-bottom: none;
    }
    
    .stTabs [aria-selected="true"] {
        background: #fff !important;
        color: #4a3728 !important;
        font-weight: 600 !important;
    }
    
    .stTabs [data-baseweb="tab-panel"] {
        background: #fff;
        border-radius: 0 0 12px 12px;
        padding: 1.5rem;
        border: 1px solid #e8e0d5;
        border-top: none;
    }
    
    /* 按钮样式 */
    .stButton>button {
        background: linear-gradient(135deg, #8b7355 0%, #6b5344 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 500;
        width: 100%;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #6b5344 0%, #4a3728 100%);
    }
    
    /* 下拉选择框 */
    .stMultiSelect, .stSelectbox {
        background: #fffdf8;
    }
    
    /* 输入框 */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        background: #fffdf8;
        border: 1px solid #e8e0d5;
        border-radius: 8px;
    }
    
    /* 结果显示 */
    .result-box {
        background: #f9f6f1;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid #e8e0d5;
        margin-top: 1rem;
    }
    
    /* 隐藏Streamlit元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 标签样式 */
    .tag {
        display: inline-block;
        background: #e8dfd3;
        color: #5a4a3a;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        margin: 2px;
    }
    
    /* 选择提示 */
    .select-hint {
        color: #8a7a6a;
        font-size: 0.85rem;
        margin-top: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)


def get_feishu_data(table_id: str, fields: list = None) -> list:
    """从飞书表格获取数据"""
    try:
        from src.graphs.nodes.feishu_read_node import FeishuBitableReader
        
        reader = FeishuBitableReader()
        result = reader.search_records(
            app_token=FEISHU_CONFIG['app_token'],
            table_id=table_id
        )
        
        items = result.get("data", {}).get("items", [])
        return items
    except Exception as e:
        st.warning(f"获取飞书数据失败: {e}")
        return []


def parse_products(records: list) -> list:
    """解析产品记录，返回产品名称列表"""
    products = []
    for record in records:
        fields = record.get("fields", {})
        name = fields.get("产品名称") or fields.get("名称") or fields.get("name") or fields.get("产品名")
        category = fields.get("产品分类") or fields.get("分类") or fields.get("category") or ""
        if name:
            products.append({"name": name, "category": category})
    return products


def parse_hots(records: list) -> list:
    """解析热点记录，返回热点信息列表"""
    hots = []
    for record in records:
        fields = record.get("fields", {})
        title = fields.get("热点名称") or fields.get("标题") or fields.get("热点") or fields.get("title") or fields.get("name")
        date = fields.get("日期") or fields.get("时间") or fields.get("date") or ""
        status = fields.get("状态") or ""
        if title and status != "已使用":
            hots.append({"title": title, "date": date, "status": status})
    return hots


def call_api(payload: dict) -> dict:
    """调用后端API"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TOKEN}'
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=180)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def display_result(result: dict):
    """显示生成结果"""
    if "error" in result:
        st.error(f"❌ 生成失败: {result['error']}")
        return
    
    st.success("✅ 生成成功！")
    
    # 提取结果文本
    result_text = result.get("result", "")
    
    if result_text:
        st.markdown(f"""
        <div class="result-box">
            <pre style="white-space: pre-wrap; word-wrap: break-word; font-size: 0.9rem; color: #4a3728;">{result_text}</pre>
        </div>
        """, unsafe_allow_html=True)


# 主界面
st.markdown('<h1 class="main-title">🎋 灵楠阁 · 内容生成助手</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">小红书内容一键生成，助力品牌传播</p>', unsafe_allow_html=True)

# 标签页
tab1, tab2, tab3 = st.tabs(["⚡ 快速生成", "🎯 自选生成", "⚙️ 设置"])

with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    
    # 工作流选择
    workflow_type = st.selectbox(
        "选择工作流",
        ["一键生成", "热点选题", "选题文案", "客户故事", "图片建议", "数据复盘"],
        help="选择要执行的工作流类型"
    )
    
    # 发布账号选择
    publish_account = st.selectbox(
        "📱 发布账号",
        ["灵楠阁品牌号", "古典家具号"],
        help="选择发布内容的账号"
    )
    
    # 执行按钮
    if st.button("🚀 开始生成", key="quick_gen"):
        with st.spinner("生成中，请稍候..."):
            payload = {
                "workflow_type": workflow_type,
                "feishu_app_token": FEISHU_CONFIG['app_token'],
                "feishu_product_table_id": FEISHU_CONFIG['product_table_id'],
                "feishu_topic_table_id": FEISHU_CONFIG['topic_table_id'],
                "feishu_content_table_id": FEISHU_CONFIG['content_table_id'],
                "feishu_hot_calendar_table_id": FEISHU_CONFIG['hot_calendar_table_id'],
                "publish_account": publish_account
            }
            result = call_api(payload)
            display_result(result)
    
    st.markdown('</div>', unsafe_allow_html=True)


with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎯 选择产品和热点生成定制内容")
    
    # 获取飞书数据
    with st.spinner("加载产品数据..."):
        product_records = get_feishu_data(FEISHU_CONFIG['product_table_id'])
        products = parse_products(product_records)
    
    with st.spinner("加载热点数据..."):
        hot_records = get_feishu_data(FEISHU_CONFIG['hot_calendar_table_id'])
        hots = parse_hots(hot_records)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📦 产品选择")
        
        if products:
            # 创建产品选项列表
            product_options = [f"{p['name']} ({p['category']})" if p['category'] else p['name'] for p in products]
            
            selected_products = st.multiselect(
                "选择产品（可多选）",
                product_options,
                help="从产品素材表中选择产品"
            )
            
            st.caption(f"共 {len(products)} 个产品可选")
        else:
            st.warning("⚠️ 暂无产品数据，请手动输入")
            selected_products = []
            
            # 手动输入备用
            manual_products = st.text_input(
                "手动输入产品名称",
                placeholder="多个产品用逗号分隔，如：金丝楠小凳, 茶盘"
            )
            if manual_products:
                selected_products = [p.strip() for p in manual_products.split(",") if p.strip()]
    
    with col2:
        st.markdown("#### 🔥 热点选择")
        
        if hots:
            # 创建热点选项列表
            hot_options = [f"{h['title']} ({h['date']})" if h['date'] else h['title'] for h in hots]
            
            selected_hots = st.multiselect(
                "选择热点（可多选，可选）",
                hot_options,
                help="从热点日历表中选择热点"
            )
            
            st.caption(f"共 {len(hots)} 个热点可选")
        else:
            st.warning("⚠️ 暂无热点数据，请手动输入")
            selected_hots = []
            
            # 手动输入备用
            manual_hots = st.text_input(
                "手动输入热点名称",
                placeholder="多个热点用逗号分隔，如：端午节, 父亲节"
            )
            if manual_hots:
                selected_hots = [h.strip() for h in manual_hots.split(",") if h.strip()]
    
    # 发布账号选择
    st.markdown("---")
    publish_account_custom = st.selectbox(
        "📱 发布账号",
        ["灵楠阁品牌号", "古典家具号"],
        key="custom_account"
    )
    
    # 执行按钮
    st.markdown("---")
    if st.button("✨ 生成定制内容", key="custom_gen", type="primary"):
        # 验证选择
        if not selected_products:
            st.error("❌ 请至少选择一个产品")
        else:
            with st.spinner("生成中，请稍候..."):
                # 提取产品名称（去掉分类后缀）
                product_names = []
                for p in selected_products:
                    # 如果是 "产品名 (分类)" 格式，提取产品名
                    if " (" in p:
                        product_names.append(p.split(" (")[0])
                    else:
                        product_names.append(p)
                
                # 提取热点名称
                hot_names = []
                for h in selected_hots:
                    if " (" in h:
                        hot_names.append(h.split(" (")[0])
                    else:
                        hot_names.append(h)
                
                payload = {
                    "workflow_type": "一键生成",
                    "feishu_app_token": FEISHU_CONFIG['app_token'],
                    "feishu_product_table_id": FEISHU_CONFIG['product_table_id'],
                    "feishu_topic_table_id": FEISHU_CONFIG['topic_table_id'],
                    "feishu_content_table_id": FEISHU_CONFIG['content_table_id'],
                    "feishu_hot_calendar_table_id": FEISHU_CONFIG['hot_calendar_table_id'],
                    "publish_account": publish_account_custom,
                    "selected_products": [{"name": name} for name in product_names],
                    "selected_hots": [{"title": name} for name in hot_names] if hot_names else []
                }
                result = call_api(payload)
                display_result(result)
    
    st.markdown('</div>', unsafe_allow_html=True)


with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### ⚙️ 飞书配置")
    
    st.text_input("App Token", value=FEISHU_CONFIG['app_token'], disabled=True)
    st.text_input("产品素材表 ID", value=FEISHU_CONFIG['product_table_id'], disabled=True)
    st.text_input("热点日历表 ID", value=FEISHU_CONFIG['hot_calendar_table_id'], disabled=True)
    st.text_input("选题记录表 ID", value=FEISHU_CONFIG['topic_table_id'], disabled=True)
    st.text_input("内容记录表 ID", value=FEISHU_CONFIG['content_table_id'], disabled=True)
    
    st.caption("💡 配置已预设，如需修改请联系管理员")
    st.markdown('</div>', unsafe_allow_html=True)

# 页脚
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #8a7a6a; font-size: 0.8rem;">
    🎋 灵楠阁 · 让东方美学融入日常生活
</div>
""", unsafe_allow_html=True)
