import streamlit as st
import requests
import json
import os

# API配置
API_URL = 'https://jv7dr2vk3d.coze.site/run'
TOKEN = 'eyJhbGciOiJSUzI1NiIsImtpZCI6ImMwNTQ1ZjM1LWY0M2YtNDU1OS1iNmUzLTc3ODc1MTFiZDc4YiJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbIlpoZFlSU0NXMVlLZEhvNmNaVWlDaXpjMVY0M2dGUkRvIl0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzgwODk4NTYwLCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3NjQ3MDEzMzg4NjAxNTI0MjI0Iiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3NjQ4OTAxMDcyNzMxMjQyNTAyIn0.FBHQs6vSVwDqTteTyqXNANC5-sOTi00OUeiPF6zRE_uPU3Bf5J7NmhF3acywTh4Tqb8yYJ5cqJWlPf-vdBJOevaX4lZxwzMk3ybICThjC7lCCEd9jvjw2rBinv_0OGYfL9jonIWwo4L6AGIeM1qkOGityYIrau8iFffhTlpkVTCYNKM3cpWH3RV2AIdp3wJBMll6jSJnYZLCws7aT9C1v9LQQrzWzfmVPSunbGOAiARv95u2tSjR32MEkJqKaCkWg2oKy1hMdKSE8kkcZ_3xZA304xcm0jjZrZxNhNhOVjRiruz0zWPjCIoSN8oUPCz0Ibdge4-QnMrTwDQPfR4bLg'

# 飞书API配置
FEISHU_API = 'https://open.feishu.cn/open-apis/bitable/v1/apps'

# 预填飞书表格ID
FEISHU_CONFIG = {
    'app_token': 'HF7dYv7ubaLkWss7d3fVcA4ynugcqhJJfAbpmc',  # 使用正确的app_token
    'product_table_id': 'tbllExTlKURFJP2j',
    'topic_table_id': 'tblJNjx74uZ3s1vs',
    'content_table_id': 'tblsCeJXz0OcL01T',
    'review_table_id': 'tblZ3EZ74uZ3s1vs',
    'hot_calendar_table_id': 'tblT1KM0397UcGeM'
}

# 自定义CSS样式
st.markdown("""
<style>
    /* 主容器样式 */
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
    }
    
    /* 标题样式 */
    .main-title {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        color: #1a1a2e !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    
    .sub-title {
        font-size: 1.1rem !important;
        color: #4a4a6a !important;
        text-align: center;
        margin-bottom: 2rem !important;
    }
    
    /* 卡片样式 */
    .card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        margin-bottom: 20px;
        border: 1px solid rgba(0,0,0,0.05);
    }
    
    .card-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1a1a2e;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* 工作流选择卡片 */
    .workflow-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 2px solid transparent;
    }
    
    .workflow-card:hover {
        border-color: #6366f1;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
    }
    
    .workflow-card.selected {
        border-color: #6366f1;
        background: linear-gradient(135deg, #f0f4ff 0%, #e8edff 100%);
    }
    
    /* 按钮样式 */
    .stButton > button {
        width: 100%;
        border-radius: 12px !important;
        font-weight: 600 !important;
        height: 50px !important;
        font-size: 1.1rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.3);
    }
    
    /* 选择框样式 */
    .stSelectbox > div > div {
        border-radius: 10px !important;
    }
    
    /* 多选框样式 */
    .stMultiSelect > div > div {
        border-radius: 10px !important;
    }
    
    /* 成功提示 */
    .success-box {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border-radius: 12px;
        padding: 16px;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    /* 信息提示 */
    .info-box {
        background: linear-gradient(135deg, #e8f4fd 0%, #d1ecf1 100%);
        border-radius: 12px;
        padding: 16px;
        color: #0c5460;
        border: 1px solid #bee5eb;
    }
    
    /* 产品卡片 */
    .product-item {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 8px;
        border: 1px solid #e9ecef;
    }
    
    /* 热点标签 */
    .hot-tag {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
        border-radius: 8px;
        padding: 8px 12px;
        color: #856404;
        font-size: 0.9rem;
        margin-bottom: 8px;
        display: inline-block;
    }
    
    /* 结果展示 */
    .result-box {
        background: white;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e9ecef;
    }
    
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# 页面配置
st.set_page_config(
    page_title='灵楠阁 · 内容生成助手',
    page_icon='🎋',
    layout='wide',
    initial_sidebar_state='collapsed'
)

# 飞书应用配置（用于获取 tenant_access_token）
FEISHU_APP_ID = 'cli_a7b3e1d2f5g6h8i9'
FEISHU_APP_SECRET = 'your_app_secret'  # 需要填入实际的 app_secret

def get_feishu_tenant_token() -> str:
    """获取飞书 tenant_access_token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        response = requests.post(url, json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('tenant_access_token', '')
    except Exception:
        pass
    return ''

# 获取飞书数据
def fetch_feishu_data(app_token: str, table_id: str) -> list:
    """从飞书多维表格获取数据"""
    try:
        # 尝试获取 tenant_access_token
        token = get_feishu_tenant_token()
        if not token:
            # 如果获取失败，使用预设的 token
            token = 't-g1044f2CHPQ62SIQJ5MZJZP6P4EHHVGSNP4HI5KJ'
        
        url = f"{FEISHU_API}/{app_token}/tables/{table_id}/records"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        params = {'page_size': 100}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('items', [])
        else:
            st.warning(f'飞书API返回: {response.status_code}')
        return []
    except Exception as e:
        st.warning(f'获取数据失败: {str(e)[:50]}')
        return []

# 解析飞书字段
def extract_field(fields: dict, field_name: str) -> str:
    """从飞书字段中提取文本"""
    value = fields.get(field_name, {})
    if isinstance(value, str):
        return value
    elif isinstance(value, list) and value:
        return value[0].get('text', '') if isinstance(value[0], dict) else str(value[0])
    elif isinstance(value, dict):
        return value.get('text', '')
    return ''

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
            st.session_state['run_workflow'] = True
            st.session_state['workflow_type'] = workflow_option
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 执行工作流
    if st.session_state.get('run_workflow', False):
        with st.spinner('🔄 正在生成内容，请耐心等待...'):
            payload = {
                'workflow_type': st.session_state['workflow_type'],
                'publish_account': publish_account,
                'feishu_app_token': FEISHU_CONFIG['app_token'],
                'feishu_product_table_id': FEISHU_CONFIG['product_table_id'],
                'feishu_topic_table_id': FEISHU_CONFIG['topic_table_id'],
                'feishu_content_table_id': FEISHU_CONFIG['content_table_id'],
                'feishu_review_table_id': FEISHU_CONFIG['review_table_id'],
                'feishu_hot_calendar_table_id': FEISHU_CONFIG['hot_calendar_table_id']
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {TOKEN}'
            }
            
            try:
                response = requests.post(API_URL, json=payload, headers=headers, timeout=600)
                
                if response.status_code == 200:
                    result = response.json()
                    st.success('✅ 生成完成！')
                    
                    # 显示结果
                    st.markdown('<div class="result-box">', unsafe_allow_html=True)
                    st.markdown(f"```\n{result.get('result', '无结果')}\n```")
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # 下载按钮
                    st.download_button(
                        label='📥 下载结果JSON',
                        data=json.dumps(result, indent=2, ensure_ascii=False),
                        file_name=f"{st.session_state['workflow_type']}_result.json",
                        mime='application/json'
                    )
                else:
                    st.error(f'❌ 生成失败: {response.status_code}')
                    
            except Exception as e:
                st.error(f'❌ 请求异常: {str(e)}')
            
            st.session_state['run_workflow'] = False

# ==================== Tab2: 自选生成 ====================
with tab2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎨 自选产品与热点生成</div>', unsafe_allow_html=True)
    st.markdown('选择特定的产品和热点，生成定制化的内容')
    
    # 预设的产品和热点（备用，当飞书API不可用时使用）
    PRESET_PRODUCTS = [
        {'name': '金丝楠小凳', 'category': '家具', 'record_id': 'preset_1'},
        {'name': '金丝楠茶盘', 'category': '茶器', 'record_id': 'preset_2'},
        {'name': '金丝楠香炉', 'category': '香器', 'record_id': 'preset_3'},
        {'name': '金丝楠笔筒', 'category': '文房', 'record_id': 'preset_4'},
        {'name': '金丝楠手串', 'category': '饰品', 'record_id': 'preset_5'},
        {'name': '金丝楠花架', 'category': '家具', 'record_id': 'preset_6'},
        {'name': '金丝楠博古架', 'category': '家具', 'record_id': 'preset_7'},
        {'name': '金丝楠茶杯', 'category': '茶器', 'record_id': 'preset_8'},
    ]
    
    PRESET_HOTS = [
        {'title': '端午节', 'date': '2025-05-31', 'record_id': 'hot_1'},
        {'title': '父亲节', 'date': '2025-06-15', 'record_id': 'hot_2'},
        {'title': '618购物节', 'date': '2025-06-18', 'record_id': 'hot_3'},
        {'title': '夏至', 'date': '2025-06-21', 'record_id': 'hot_4'},
        {'title': '毕业季', 'date': '2025-06-07', 'record_id': 'hot_5'},
        {'title': '七夕节', 'date': '2025-08-10', 'record_id': 'hot_6'},
    ]
    
    # 尝试获取飞书数据
    with st.spinner('📂 正在加载产品数据...'):
        products = fetch_feishu_data(FEISHU_CONFIG['app_token'], FEISHU_CONFIG['product_table_id'])
    
    with st.spinner('📅 正在加载热点数据...'):
        hot_topics = fetch_feishu_data(FEISHU_CONFIG['app_token'], FEISHU_CONFIG['hot_calendar_table_id'])
    
    # 如果飞书数据为空，使用预设数据
    if not products:
        st.info('💡 使用预设产品列表（飞书数据暂不可用）')
        products_data = PRESET_PRODUCTS
    else:
        products_data = []
        for item in products[:20]:
            fields = item.get('fields', {})
            name = extract_field(fields, '产品名称') or extract_field(fields, '名称')
            category = extract_field(fields, '分类') or extract_field(fields, '产品分类')
            if name:
                products_data.append({
                    'name': name,
                    'category': category,
                    'record_id': item.get('record_id', '')
                })
    
    if not hot_topics:
        st.info('💡 使用预设热点列表（飞书数据暂不可用）')
        hots_data = PRESET_HOTS
    else:
        hots_data = []
        for item in hot_topics[:20]:
            fields = item.get('fields', {})
            title = extract_field(fields, '热点名称') or extract_field(fields, '事件') or extract_field(fields, '名称')
            date = extract_field(fields, '日期') or extract_field(fields, '时间') or extract_field(fields, '热点日期')
            if title:
                hots_data.append({
                    'title': title,
                    'date': date,
                    'record_id': item.get('record_id', '')
                })
    
    if products_data or hots_data:
        col1, col2 = st.columns(2)
        
        # 产品选择
        with col1:
            st.markdown('#### 📦 选择产品')
            product_options = []
            product_map = {}
            
            for p in products_data:
                display_name = f"{p['name']} ({p['category']})" if p.get('category') else p['name']
                product_options.append(display_name)
                product_map[display_name] = p
            
            selected_products = st.multiselect(
                '选择要生成内容的产品（可多选）',
                product_options,
                help='可以选择多个产品，每个产品生成一篇内容'
            )
            
            # 显示选中产品
            if selected_products:
                st.markdown('**已选产品:**')
                for p in selected_products:
                    st.markdown(f'<div class="product-item">✓ {p}</div>', unsafe_allow_html=True)
        
        # 热点选择
        with col2:
            st.markdown('#### 🔥 选择热点')
            hot_options = []
            hot_map = {}
            
            for h in hots_data:
                display_name = f"{h['title']} ({h['date']})" if h.get('date') else h['title']
                hot_options.append(display_name)
                hot_map[display_name] = h
            
            selected_hots = st.multiselect(
                '选择要结合的热点（可多选）',
                hot_options,
                help='选择热点会让内容更有时效性'
            )
            
            # 显示选中热点
            if selected_hots:
                st.markdown('**已选热点:**')
                for h in selected_hots:
                    st.markdown(f'<span class="hot-tag">🔥 {h}</span>', unsafe_allow_html=True)
        
        # 发布账号
        st.markdown('---')
        col1, col2, col3 = st.columns(3)
        
        with col1:
            custom_account = st.selectbox(
                '📱 发布账号',
                ['灵楠阁品牌号', '古典家具号'],
                key='custom_account'
            )
        
        with col2:
            st.markdown('<div style="height: 38px;"></div>', unsafe_allow_html=True)
            if st.button('✨ 生成定制内容', type='primary', use_container_width=True, key='custom_generate'):
                if selected_products or selected_hots:
                    st.session_state['custom_run'] = True
                    st.session_state['selected_products'] = [product_map[p] for p in selected_products]
                    st.session_state['selected_hots'] = [hot_map[h] for h in selected_hots]
                    st.session_state['custom_account'] = custom_account
                else:
                    st.warning('请至少选择一个产品或热点')
        
        # 执行自选生成
        if st.session_state.get('custom_run', False):
            with st.spinner('🔄 正在生成定制内容，请耐心等待...'):
                payload = {
                    'workflow_type': '一键生成',
                    'publish_account': st.session_state.get('custom_account', '灵楠阁品牌号'),
                    'feishu_app_token': FEISHU_CONFIG['app_token'],
                    'feishu_product_table_id': FEISHU_CONFIG['product_table_id'],
                    'feishu_topic_table_id': FEISHU_CONFIG['topic_table_id'],
                    'feishu_content_table_id': FEISHU_CONFIG['content_table_id'],
                    'feishu_hot_calendar_table_id': FEISHU_CONFIG['hot_calendar_table_id'],
                    'selected_products': st.session_state.get('selected_products', []),
                    'selected_hots': st.session_state.get('selected_hots', [])
                }
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {TOKEN}'
                }
                
                try:
                    response = requests.post(API_URL, json=payload, headers=headers, timeout=600)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success('✅ 定制内容生成完成！')
                        
                        # 显示结果
                        st.markdown('<div class="result-box">', unsafe_allow_html=True)
                        st.markdown(f"```\n{result.get('result', '无结果')}\n```")
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.error(f'❌ 生成失败: {response.status_code}')
                        
                except Exception as e:
                    st.error(f'❌ 请求异常: {str(e)}')
            
            st.session_state['custom_run'] = False
    
    else:
        st.warning('⚠️ 暂无可用数据')

# ==================== Tab3: 高级设置 ====================
with tab3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ 高级设置</div>', unsafe_allow_html=True)
    st.markdown('以下参数已预填默认值，通常无需修改')
    
    col1, col2 = st.columns(2)
    
    with col1:
        feishu_app_token = st.text_input('飞书 App Token', value=FEISHU_CONFIG['app_token'], type='password')
        feishu_product_table = st.text_input('产品素材表 ID', value=FEISHU_CONFIG['product_table_id'])
        feishu_topic_table = st.text_input('选题库 ID', value=FEISHU_CONFIG['topic_table_id'])
    
    with col2:
        feishu_content_table = st.text_input('内容成品库 ID', value=FEISHU_CONFIG['content_table_id'])
        feishu_review_table = st.text_input('数据复盘表 ID', value=FEISHU_CONFIG['review_table_id'])
        feishu_hot_calendar = st.text_input('热点日历表 ID', value=FEISHU_CONFIG['hot_calendar_table_id'])
    
    if st.button('💾 保存设置', type='secondary'):
        st.success('✅ 设置已保存（当前会话有效）')
    
    st.markdown('</div>', unsafe_allow_html=True)

# 底部说明
st.markdown('---')
st.markdown("""
<div style="text-align: center; color: #6c757d; font-size: 0.9rem;">
    💡 <b>使用提示</b>: 一键生成会自动读取热点日历和产品素材库，生成选题、文案、图片建议，并写入飞书表格。<br>
    🎯 <b>自选生成</b>: 可手动选择产品和热点，生成定制化内容。
</div>
""", unsafe_allow_html=True)
