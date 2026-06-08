import streamlit as st
import requests
import json

# API配置
API_URL = 'https://jv7dr2vk3d.coze.site/run'
TOKEN = 'eyJhbGciOiJSUzI1NiIsImtpZCI6ImMwNTQ1ZjM1LWY0M2YtNDU1OS1iNmUzLTc3ODc1MTFiZDc4YiJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbIlpoZFlSU0NXMVlLZEhvNmNaVWlDaXpjMVY0M2dGUkRvIl0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzgwODk4NTYwLCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3NjQ3MDEzMzg4NjAxNTI0MjI0Iiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3NjQ4OTAxMDcyNzMxMjQyNTAyIn0.FBHQs6vSVwDqTteTyqXNANC5-sOTi00OUeiPF6zRE_uPU3Bf5J7NmhF3acywTh4Tqb8yYJ5cqJWlPf-vdBJOevaX4lZxwzMk3ybICThjC7lCCEd9jvjw2rBinv_0OGYfL9jonIWwo4L6AGIeM1qkOGityYIrau8iFffhTlpkVTCYNKM3cpWH3RV2AIdp3wJBMll6jSJnYZLCws7aT9C1v9LQQrzWzfmVPSunbGOAiARv95u2tSjR32MEkJqKaCkWg2oKy1hMdKSE8kkcZ_3xZA304xcm0jjZrZxNhNhOVjRiruz0zWPjCIoSN8oUPCz0Ibdge4-QnMrTwDQPfR4bLg'

# 预填飞书表格ID
FEISHU_CONFIG = {
    'app_token': 'FoWqb7NLuah1gdssEHbc7Wk9nQh',
    'product_table_id': 'tbllExTlKURFJP2j',
    'topic_table_id': 'tblJNjx74uZ3s1vs',
    'content_table_id': 'tblg7zZuWKcUvqQX',
    'review_table_id': 'tblZ3EZ74uZ3s1vs',
    'hot_calendar_table_id': 'tblT1KM0397UcGeM'
}

# 页面配置
st.set_page_config(page_title='灵楠阁内容生成助手', page_icon='📝', layout='wide')

# 标题
st.title('📝 灵楠阁内容生成助手')
st.markdown('一键生成小红书选题与文案，自动写入飞书表格')

# 工作流选择
workflow_options = {
    '一键生成': '一键生成（推荐）- 自动生成选题+文案+图片建议',
    '热点选题': '热点选题 - 从热点日历生成选题方案',
    '选题文案': '选题文案 - 根据已通过的选题生成正文',
    '图片建议': '图片建议 - 为文案生成图片拍摄建议',
    '内容整理': '内容整理 - 整合发布格式'
}

col1, col2 = st.columns(2)

with col1:
    workflow_type = st.selectbox(
        '选择工作流',
        list(workflow_options.keys()),
        help='选择要执行的工作流类型'
    )
    st.info(workflow_options[workflow_type])

with col2:
    publish_account = st.selectbox(
        '发布账号（可选）',
        ['古典家具号', '灵楠阁品牌号'],
        help='选择内容发布的账号'
    )

# 一键生成说明
if workflow_type == '一键生成':
    st.success('✅ 一键生成已预填所有参数，只需点击生成即可！')

# 高级设置（折叠）
with st.expander('⚙️ 高级设置（可选）', expanded=False):
    st.markdown('以下参数已预填默认值，通常无需修改')
    
    feishu_app_token = st.text_input('飞书 App Token', value=FEISHU_CONFIG['app_token'])
    feishu_product_table = st.text_input('产品素材表 ID', value=FEISHU_CONFIG['product_table_id'])
    feishu_topic_table = st.text_input('选题库 ID', value=FEISHU_CONFIG['topic_table_id'])
    feishu_content_table = st.text_input('内容成品库 ID', value=FEISHU_CONFIG['content_table_id'])

# 生成按钮
if st.button('🚀 开始生成', type='primary', use_container_width=True):
    
    # 构建请求参数
    payload = {
        'workflow_type': workflow_type,
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
    
    # 显示进度
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text('🔄 正在生成内容，请稍候...')
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            progress_bar.progress(100)
            status_text.text('✅ 生成完成！')
            
            # 显示结果
            st.subheader('📋 生成结果')
            
            if 'result' in result:
                st.markdown(result['result'])
            
            # 统计信息
            if 'processed_count' in result:
                st.metric('处理数量', result.get('processed_count', 0))
            
            # 下载按钮
            st.download_button(
                label='📥 下载结果',
                data=json.dumps(result, indent=2, ensure_ascii=False),
                file_name=f'{workflow_type}_result.json',
                mime='application/json'
            )
            
        else:
            progress_bar.progress(100)
            status_text.text('❌ 生成失败')
            st.error(f'API返回错误: {response.status_code} - {response.text}')
            
    except Exception as e:
        progress_bar.progress(100)
        status_text.text('❌ 请求失败')
        st.error(f'请求异常: {str(e)}')

# 底部说明
st.markdown('---')
st.markdown('💡 **使用提示**: 一键生成会自动读取热点日历和产品素材库，生成选题、文案、图片建议，并写入飞书表格。')