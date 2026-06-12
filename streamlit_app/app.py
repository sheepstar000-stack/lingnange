import streamlit as st
import requests
import json
import os

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
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    /* 主容器 */
    .block-container {
        padding-top: 2rem !important;
        max-width: 1200px !important;
    }
    
    /* 标题样式 */
    .main-title {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: #2c3e50 !important;
        text-align: center;
        margin-bottom: 0.3rem !important;
    }
    
    .sub-title {
        font-size: 1rem !important;
        color: #7f8c8d !important;
        text-align: center;
        margin-bottom: 1.5rem !important;
    }
    
    /* 卡片样式 */
    .card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        margin-bottom: 20px;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .card-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 16px;
    }
    
    /* 按钮样式 */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        height: 46px !important;
        font-size: 1rem !important;
        border: none !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* 选择框样式 */
    .stSelectbox label, .stRadio label, .stMultiSelect label {
        color: #2c3e50 !important;
        font-weight: 500 !important;
    }
    
    /* 多选框增强 */
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #667eea !important;
        color: white !important;
        border-radius: 6px !important;
    }
    
    /* Tab样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: white;
        border-radius: 12px;
        padding: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-weight: 500 !important;
        color: #7f8c8d !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
    }
    
    /* 信息提示 */
    .stAlert {
        border-radius: 10px !important;
        border: none !important;
    }
    
    /* 选择卡片 */
    .select-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border: 2px solid transparent;
        transition: all 0.2s ease;
    }
    
    .select-card:hover {
        border-color: #667eea;
        background: #f0f4ff;
    }
    
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 修复深色模式问题 */
    .stMarkdown, .stText, p, span, label {
        color: #2c3e50 !important;
    }
    
    /* 结果展示 */
    .result-content {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px;
        margin-top: 16px;
        border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# 主界面
st.markdown('<h1 class="main-title">🎋 灵楠阁 · 内容生成助手</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">一键生成小红书选题与文案，自动写入飞书表格</p>', unsafe_allow_html=True)

# 创建标签页
tab1, tab2, tab3 = st.tabs(['🚀 快速生成', '✨ 自选生成', '⚙️ 高级设置'])

# ==================== Tab1: 快速生成 ====================
with tab1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 选择工作流</div>', unsafe_allow_html=True)
    
    workflow_option = st.radio(
        '选择要执行的工作流',
        ['一键生成', '热点选题', '选题文案', '图片建议', '内容整理'],
        horizontal=True,
        label_visibility='collapsed'
    )
    
    workflow_desc = {
        '一键生成': '🎉 自动完成选题→文案→图片建议全流程，无需中间审核',
        '热点选题': '📅 从热点日历读取热点，结合产品生成选题方案',
        '选题文案': '📝 根据已通过的选题生成正文内容',
        '图片建议': '📷 为文案生成图片拍摄和修图建议',
        '内容整理': '📋 整合内容成品库，输出发布格式'
    }
    
    st.info(workflow_desc[workflow_option])
    
    # 发布账号选择
    col1, col2 = st.columns(2)
    with col1:
        publish_account = st.selectbox(
            '📱 发布账号',
            ['灵楠阁品牌号', '古典家具号'],
            help='选择内容发布的账号'
        )
    with col2:
        st.markdown('<div style="height: 38px;"></div>', unsafe_allow_html=True)
        if st.button('🚀 开始生成', type='primary', use_container_width=True):
            with st.spinner('正在生成中，请稍候...'):
                # 构建请求
                payload = {
                    'workflow_type': workflow_option,
                    'feishu_app_token': FEISHU_CONFIG['app_token'],
                    'publish_account': publish_account
                }
                
                # 根据工作流类型添加必要参数
                if workflow_option == '热点选题':
                    payload['feishu_hot_calendar_table_id'] = FEISHU_CONFIG['hot_calendar_table_id']
                    payload['feishu_product_table_id'] = FEISHU_CONFIG['product_table_id']
                    payload['feishu_topic_table_id'] = FEISHU_CONFIG['topic_table_id']
                elif workflow_option == '选题文案':
                    payload['feishu_topic_table_id'] = FEISHU_CONFIG['topic_table_id']
                    payload['feishu_product_table_id'] = FEISHU_CONFIG['product_table_id']
                    payload['feishu_content_table_id'] = FEISHU_CONFIG['content_table_id']
                elif workflow_option == '图片建议':
                    payload['feishu_content_table_id'] = FEISHU_CONFIG['content_table_id']
                    payload['feishu_product_table_id'] = FEISHU_CONFIG['product_table_id']
                elif workflow_option == '内容整理':
                    payload['feishu_content_table_id'] = FEISHU_CONFIG['content_table_id']
                    payload['feishu_product_table_id'] = FEISHU_CONFIG['product_table_id']
                
                headers = {
                    'Authorization': f'Bearer {TOKEN}',
                    'Content-Type': 'application/json'
                }
                
                try:
                    response = requests.post(API_URL, json=payload, headers=headers, timeout=300)
                    result = response.json()
                    
                    if result.get('success'):
                        output = result.get('output', {})
                        st.markdown('<div class="result-content">', unsafe_allow_html=True)
                        st.markdown(f"**✅ 执行成功**")
                        st.markdown(output.get('result', '完成'))
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.error(f"执行失败: {result.get('message', '未知错误')}")
                except Exception as e:
                    st.error(f"请求失败: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== Tab2: 自选生成 ====================
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 选择产品和热点生成定制内容</div>', unsafe_allow_html=True)
    
    st.markdown("**产品列表**（输入产品名称，多个用逗号分隔）")
    products_input = st.text_input(
        '产品名称',
        placeholder='例如：金丝楠小凳, 茶盘, 香炉',
        label_visibility='collapsed'
    )
    
    st.markdown("**热点列表**（输入热点名称，多个用逗号分隔，可选）")
    hots_input = st.text_input(
        '热点名称',
        placeholder='例如：端午节, 父亲节',
        label_visibility='collapsed'
    )
    
    col1, col2 = st.columns(2)
    with col1:
        publish_account = st.selectbox(
            '📱 发布账号',
            ['灵楠阁品牌号', '古典家具号'],
            key='publish_account_select'
        )
    
    with col2:
        st.markdown('<div style="height: 38px;"></div>', unsafe_allow_html=True)
        if st.button('✨ 生成定制内容', type='primary', use_container_width=True):
            # 解析输入
            products = [p.strip() for p in products_input.split(',') if p.strip()]
            hots = [h.strip() for h in hots_input.split(',') if h.strip()]
            
            if not products:
                st.warning('请至少输入一个产品名称')
            else:
                with st.spinner('正在生成中，请稍候...'):
                    # 构建选中数据
                    selected_products = [{'name': p, 'category': '未分类'} for p in products]
                    selected_hots = [{'title': h, 'date': ''} for h in hots] if hots else []
                    
                    payload = {
                        'workflow_type': '一键生成',
                        'feishu_app_token': FEISHU_CONFIG['app_token'],
                        'selected_products': selected_products,
                        'selected_hots': selected_hots,
                        'publish_account': publish_account
                    }
                    
                    headers = {
                        'Authorization': f'Bearer {TOKEN}',
                        'Content-Type': 'application/json'
                    }
                    
                    try:
                        response = requests.post(API_URL, json=payload, headers=headers, timeout=300)
                        result = response.json()
                        
                        if result.get('success'):
                            output = result.get('output', {})
                            st.markdown('<div class="result-content">', unsafe_allow_html=True)
                            st.markdown(f"**✅ 执行成功**")
                            st.markdown(output.get('result', '完成'))
                            st.markdown('</div>', unsafe_allow_html=True)
                        else:
                            st.error(f"执行失败: {result.get('message', '未知错误')}")
                    except Exception as e:
                        st.error(f"请求失败: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==================== Tab3: 高级设置 ====================
with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ 飞书表格配置</div>', unsafe_allow_html=True)
    
    st.markdown("当前配置的飞书表格ID：")
    
    config_cols = st.columns(2)
    with config_cols[0]:
        st.text_input('App Token', FEISHU_CONFIG['app_token'], disabled=True)
        st.text_input('产品素材表', FEISHU_CONFIG['product_table_id'], disabled=True)
        st.text_input('选题表', FEISHU_CONFIG['topic_table_id'], disabled=True)
    
    with config_cols[1]:
        st.text_input('内容成品表', FEISHU_CONFIG['content_table_id'], disabled=True)
        st.text_input('复盘表', FEISHU_CONFIG['review_table_id'], disabled=True)
        st.text_input('热点日历表', FEISHU_CONFIG['hot_calendar_table_id'], disabled=True)
    
    st.caption('💡 如需修改配置，请联系管理员更新代码中的 FEISHU_CONFIG')
    st.markdown('</div>', unsafe_allow_html=True)
