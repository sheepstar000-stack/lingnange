"""
Streamlit 应用 - 小红书内容生成工作流
"""

import os
import sys
import requests
import streamlit as st

# 设置页面配置
st.set_page_config(
    page_title="小红书内容生成工作流",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 飞书配置
FEISHU_CONFIG = {
    'app_token': 'FoWqb7NLuah1gdssEHbc7Wk9nQh',
    'product_table_id': 'tbllExTlKURFJP2j',
    'topic_table_id': 'tblJNjx74uZ3s1vs',
    'content_table_id': 'tblg7zZuWKcUvqQX',
    'hot_calendar_table_id': 'tblT1KM0397UcGeM'
}

# 发布账号选项
PUBLISH_ACCOUNTS = ["灵楠阁品牌号", "古典家具号"]

# 自定义CSS样式 - 新中式暖色调
st.markdown("""
<style>
    /* 整体背景 */
    .stApp {
        background: linear-gradient(135deg, #f5f0e8 0%, #e8e0d5 100%);
    }
    
    /* 主标题 */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #5d4e37 !important;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 1px 1px 2px rgba(255,255,255,0.8);
    }
    
    /* 副标题 */
    .sub-title {
        font-size: 1rem;
        color: #8b7355 !important;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* 卡片样式 */
    .card {
        background: #fffdf8;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 12px rgba(93, 78, 55, 0.08);
        border: 1px solid rgba(139, 115, 85, 0.15);
        margin-bottom: 1rem;
    }
    
    .card-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #5d4e37 !important;
        margin-bottom: 0.8rem;
        border-bottom: 2px solid #d4a574;
        padding-bottom: 0.5rem;
    }
    
    /* 强制所有文字使用深色 */
    .stMarkdown, .stMarkdown p, .stMarkdown span,
    .stAlert > div, .stAlert p, .stAlert span,
    label, .st-emotion-cache-1hyd6ym, .st-emotion-cache-1v0mbdj,
    .stMultiSelect label, .stMultiSelect span,
    .stSelectbox label, .stSelectbox span,
    .stTextInput label, .stTextInput input,
    .stRadio label, .stRadio span,
    .stCheckbox label, .stCheckbox span,
    p, span, div, li {
        color: #5d4e37 !important;
    }
    
    /* 输入框样式 */
    .stTextInput input, .stSelectbox input {
        background-color: #fffdf8 !important;
        color: #5d4e37 !important;
        border: 1px solid #d4a574 !important;
    }
    
    /* 下拉选择框 */
    .stMultiSelect, .stSelectbox {
        color: #5d4e37 !important;
    }
    
    /* 下拉菜单选项 */
    div[data-baseweb="select"] div {
        color: #5d4e37 !important;
        background-color: #fffdf8 !important;
    }
    
    /* 按钮样式 */
    .stButton > button {
        background: linear-gradient(135deg, #8b7355 0%, #5d4e37 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 0.7rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(93, 78, 55, 0.3);
    }
    
    /* Tab标签页 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 253, 248, 0.8);
        color: #8b7355 !important;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: #fffdf8 !important;
        color: #5d4e37 !important;
        border-bottom: 3px solid #d4a574;
    }
    
    /* 成功/错误提示 */
    .stAlert {
        background-color: #fffdf8 !important;
        border: 1px solid #d4a574 !important;
    }
    
    .stAlert p, .stAlert span {
        color: #5d4e37 !important;
    }
    
    /* 表格样式 */
    .stDataFrame {
        background: #fffdf8;
        border-radius: 8px;
    }
    
    /* 结果展示 */
    .result-box {
        background: #fffdf8;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #d4a574;
        margin-top: 1rem;
    }
    
    .result-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #5d4e37;
        margin-bottom: 1rem;
    }
    
    /* 分隔线 */
    hr {
        border: none;
        border-top: 1px solid #d4a574;
        margin: 1.5rem 0;
    }
    
    /* 图标装饰 */
    .icon-decor {
        font-size: 1.2rem;
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def call_workflow(workflow_type: str, params: dict) -> dict:
    """调用后端工作流API"""
    # 从session_state或环境变量获取API地址
    if "api_url" in st.session_state and st.session_state.api_url:
        api_url = st.session_state.api_url
    else:
        api_url = os.getenv("API_URL", os.getenv("BACKEND_URL", "https://jv7dr2vk3d.coze.site/run"))
    
    # 获取API Token（优先使用session_state，否则使用默认Token）
    default_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjIyYmM0N2ZmLTJmZjYtNDM2OC1hYzIyLTllMTA3ZTI1MWU2ZSJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbIlpoZFlSU0NXMVlLZEhvNmNaVWlDaXpjMVY0M2dGUkRvIl0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzgxMjM4ODgxLCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3NjQ3MDEzMzg4NjAxNTI0MjI0Iiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3NjUwMzYyNzQxMTYwNDExMTc2In0.i3B615WHx6zbjA2KV705q4zhJJlK-AeXuYITTKQ94e-GXWTSVp80nUI85rMasfeILhrUaPp0HYDV407h_h52MEKp-JswfMkZuingLtUScurvwcRqU232qUAt55jUGjq25zBSWZPsrVkxg9pgkhmnrqaidm3xGt1yDtzhPGj7waL76UWHQ0N4T7lw2CyvN8STWqFSdbCXlO934YPgXJQNbCL6CRO1dY-ybHNSN8Uaz-NB5Yg7NX-5aUCnJdYPdfmYeXKuKNSi5AVyQF-OBhjhshhb0Mglm8tRFlv3KXRK_AItRgjC2WkUk_qnwyfTtSx7w-LLt9sKUn7NsIpLprmrrw"
    api_token = st.session_state.get("api_token", default_token)
    
    payload = {
        "workflow_type": workflow_type,
        **params
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=300)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"API请求失败: {resp.status_code} - {resp.text[:200]}"}
    except Exception as e:
        return {"error": f"API调用异常: {str(e)}"}


def main():
    # 主标题
    st.markdown('<h1 class="main-title">📝 小红书内容生成工作流</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">智能选题 · 文案生成 · 图片建议 · 数据复盘</p>', unsafe_allow_html=True)
    
    # 创建标签页
    tab1, tab2, tab3 = st.tabs(["⚡ 快速生成", "✨ 自选生成", "⚙️ 高级设置"])
    
    # ==================== Tab1: 快速生成 ====================
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 选择工作流类型</div>', unsafe_allow_html=True)
        
        workflow_options = {
            "一键生成": "一键生成（选题+文案+图片建议）",
            "热点选题": "从热点日历生成选题",
            "选题文案": "从选题生成文案",
            "客户故事": "生成客户故事内容",
            "图片建议": "生成图片建议",
            "数据复盘": "内容数据复盘分析"
        }
        
        selected_workflow = st.selectbox(
            "选择工作流",
            list(workflow_options.keys()),
            format_func=lambda x: workflow_options[x]
        )
        
        # 发布账号选择
        publish_account = st.selectbox("📱 发布账号", PUBLISH_ACCOUNTS)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 执行按钮
        if st.button("🚀 开始执行", key="run_workflow"):
            with st.spinner("正在执行工作流..."):
                params = {
                    "feishu_app_token": FEISHU_CONFIG['app_token'],
                    "feishu_product_table_id": FEISHU_CONFIG['product_table_id'],
                    "feishu_topic_table_id": FEISHU_CONFIG['topic_table_id'],
                    "feishu_content_table_id": FEISHU_CONFIG['content_table_id'],
                    "feishu_hot_calendar_table_id": FEISHU_CONFIG['hot_calendar_table_id'],
                    "publish_account": publish_account
                }
                
                result = call_workflow(selected_workflow, params)
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success("✅ 工作流执行完成！")
                    st.markdown('<div class="result-box">', unsafe_allow_html=True)
                    st.json(result)
                    st.markdown('</div>', unsafe_allow_html=True)
    
    # ==================== Tab2: 自选生成 ====================
    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 选择产品和热点生成定制内容</div>', unsafe_allow_html=True)
        
        # 产品输入
        st.markdown("### 📦 产品选择")
        st.markdown("**输入产品名称（多个产品用逗号分隔）**")
        st.markdown("*示例：金丝楠小凳, 茶盘, 香炉*")
        
        product_input = st.text_input(
            "产品名称",
            placeholder="金丝楠小凳, 茶盘, 香炉",
            key="product_input"
        )
        
        # 热点输入
        st.markdown("### 🔥 热点选择")
        st.markdown("**输入热点名称（多个热点用逗号分隔，可选）**")
        st.markdown("*示例：端午节, 父亲节, 618*")
        
        hot_input = st.text_input(
            "热点名称",
            placeholder="端午节, 父亲节",
            key="hot_input"
        )
        
        # 发布账号
        st.markdown("### 📱 发布账号")
        publish_account_2 = st.selectbox("选择发布账号", PUBLISH_ACCOUNTS, key="publish_account_2")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 执行按钮
        if st.button("✨ 生成定制内容", key="run_custom"):
            if not product_input.strip():
                st.warning("⚠️ 请输入至少一个产品名称")
            else:
                # 解析产品和热点
                products = [{"name": p.strip()} for p in product_input.split(",") if p.strip()]
                hots = [{"title": h.strip()} for h in hot_input.split(",") if h.strip()] if hot_input.strip() else []
                
                with st.spinner(f"正在为 {len(products)} 个产品生成内容..."):
                    params = {
                        "feishu_app_token": FEISHU_CONFIG['app_token'],
                        "feishu_product_table_id": FEISHU_CONFIG['product_table_id'],
                        "feishu_topic_table_id": FEISHU_CONFIG['topic_table_id'],
                        "feishu_content_table_id": FEISHU_CONFIG['content_table_id'],
                        "selected_products": products,
                        "selected_hots": hots,
                        "publish_account": publish_account_2
                    }
                    
                    result = call_workflow("一键生成", params)
                    
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success("✅ 内容生成完成！")
                        st.markdown('<div class="result-box">', unsafe_allow_html=True)
                        
                        # 显示生成结果
                        if "result" in result:
                            st.markdown(result["result"])
                        else:
                            st.json(result)
                        
                        st.markdown('</div>', unsafe_allow_html=True)
    
    # ==================== Tab3: 高级设置 ====================
    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">⚙️ API配置</div>', unsafe_allow_html=True)
        
        # API URL配置
        default_api_url = os.getenv("API_URL", os.getenv("BACKEND_URL", "https://jv7dr2vk3d.coze.site/run"))
        st.markdown("**后端API地址**")
        api_url_input = st.text_input("API URL", value=default_api_url, key="api_url_input")
        
        # API Token配置
        st.markdown("**API Token**")
        st.markdown("*提示：在Coze平台部署详情页可以查看API Token*")
        api_token_input = st.text_input("API Token", type="password", key="api_token_input", placeholder="请输入API Token进行认证")
        
        st.markdown('<div class="card-title">⚙️ 飞书表格配置</div>', unsafe_allow_html=True)
        
        st.markdown("**App Token**")
        app_token = st.text_input("飞书App Token", value=FEISHU_CONFIG['app_token'], key="app_token")
        
        st.markdown("**产品素材表 ID**")
        product_table = st.text_input("产品表", value=FEISHU_CONFIG['product_table_id'], key="product_table")
        
        st.markdown("**选题表 ID**")
        topic_table = st.text_input("选题表", value=FEISHU_CONFIG['topic_table_id'], key="topic_table")
        
        st.markdown("**成品表 ID**")
        content_table = st.text_input("成品表", value=FEISHU_CONFIG['content_table_id'], key="content_table")
        
        st.markdown("**热点日历表 ID**")
        hot_calendar = st.text_input("热点日历表", value=FEISHU_CONFIG['hot_calendar_table_id'], key="hot_calendar")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 更新配置按钮
        if st.button("💾 保存配置", key="save_config"):
            FEISHU_CONFIG['app_token'] = app_token
            FEISHU_CONFIG['product_table_id'] = product_table
            FEISHU_CONFIG['topic_table_id'] = topic_table
            FEISHU_CONFIG['content_table_id'] = content_table
            FEISHU_CONFIG['hot_calendar_table_id'] = hot_calendar
            st.session_state.api_url = api_url_input
            st.session_state.api_token = api_token_input
            st.success("✅ 配置已保存！")
            st.info(f"当前API地址: {api_url_input}")
            if api_token_input:
                st.info(f"API Token已设置（长度: {len(api_token_input)}字符）")


if __name__ == "__main__":
    main()
