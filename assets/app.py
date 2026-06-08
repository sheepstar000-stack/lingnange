#!/usr/bin/env python3
"""
灵楠阁内容生成界面 - Streamlit应用
使用方法：streamlit run app.py
"""

import streamlit as st
import requests
import json

# API配置
API_URL = "https://jv7dr2vk3d.coze.site/run"
API_TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImMwNTQ1ZjM1LWY0M2YtNDU1OS1iNmUzLTc3ODc1MTFiZDc4YiJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbIlpoZFlSU0NXMVlLZEhvNmNaVWlDaXpjMVY0M2dGUkRvIl0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzgwODk4NTYwLCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3NjQ3MDEzMzg4NjAxNTI0MjI0Iiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3NjQ4OTAxMDcyNzMxMjQyNTAyIn0.FBHQs6vSVwDqTteTyqXNANC5-sOTi00OUeiPF6zRE_uPU3Bf5J7NmhF3acywTh4Tqb8yYJ5cqJWlPf-vdBJOevaX4lZxwzMk3ybICThjC7lCCEd9jvjw2rBinv_0OGYfL9jonIWwo4L6AGIeM1qkOGityYIrau8iFffhTlpkVTCYNKM3cpWH3RV2AIdp3wJBMll6jSJnYZLCws7aT9C1v9LQQrzWzfmVPSunbGOAiARv95u2tSjR32MEkJqKaCkWg2oKy1hMdKSE8kkcZ_3xZA304xcm0jjZrZxNhNhOVjRiruz0zWPjCIoSN8oUPCz0Ibdge4-QnMrTwDQPfR4bLg"

# 页面配置
st.set_page_config(
    page_title="灵楠阁 · 小红书内容生成",
    page_icon="📝",
    layout="centered"
)

# 样式
st.markdown("""
<style>
.main-title {
    font-size: 2.5rem;
    font-weight: 700;
    text-align: center;
    color: #1a1a1a;
    margin-bottom: 0.5rem;
}
.sub-title {
    font-size: 1.1rem;
    text-align: center;
    color: #666;
    margin-bottom: 2rem;
}
.workflow-card {
    background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
}
.result-box {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid #e9ecef;
}
</style>
""", unsafe_allow_html=True)

# 标题
st.markdown('<p class="main-title">灵楠阁 · 小红书内容生成</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">一键生成高质量小红书内容</p>', unsafe_allow_html=True)

# 工作流选择
workflow_options = {
    "一键生成": "🔥 推荐：一键生成选题+文案+图片建议",
    "热点选题": "从热点日历生成选题方案",
    "选题文案": "根据选题生成正文文案",
    "图片建议": "为文案生成图片拍摄建议",
    "内容整理": "整理成完整发布格式"
}

workflow_type = st.selectbox(
    "选择工作流",
    options=list(workflow_options.keys()),
    format_func=lambda x: workflow_options[x]
)

# 账号选择（仅一键生成需要）
if workflow_type == "一键生成":
    account = st.selectbox(
        "选择发布账号",
        options=["古典家具号", "灵楠阁品牌号"],
        index=0
    )
else:
    account = None

# 生成按钮
if st.button("🚀 开始生成", use_container_width=True):
    # 构建请求参数
    params = {"workflow_type": workflow_type}
    if account:
        params["publish_account"] = account
    
    # 显示进度
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("⏳ 正在生成内容，请稍候...")
    progress_bar.progress(30)
    
    try:
        # 调用API
        response = requests.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_TOKEN}"
            },
            json=params,
            timeout=300
        )
        
        progress_bar.progress(70)
        result = response.json()
        
        progress_bar.progress(100)
        
        if result.get("error") or result.get("message"):
            st.error(f"❌ 生成失败: {result.get('error') or result.get('message')}")
        else:
            st.success("✅ 生成成功！")
            
            # 显示结果
            result_text = result.get("result", "")
            if result_text:
                st.markdown("### 📝 生成结果")
                st.markdown('<div class="result-box">', unsafe_allow_html=True)
                st.text_area("", result_text, height=400)
                st.markdown('</div>', unsafe_allow_html=True)
                
                # 复制和下载按钮
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "📋 下载结果",
                        result_text,
                        file_name=f"灵楠阁_{workflow_type}_{st.session_state.get('date', 'today')}.txt",
                        mime="text/plain"
                    )
                with col2:
                    processed = result.get("processed_count", 0)
                    success = result.get("success_count", 0)
                    st.info(f"📊 处理: {processed} 条，成功: {success} 条")
    
    except requests.exceptions.Timeout:
        st.error("❌ 请求超时，请稍后重试")
    except requests.exceptions.RequestException as e:
        st.error(f"❌ 请求失败: {e}")
    except Exception as e:
        st.error(f"❌ 发生错误: {e}")

# 使用说明
st.markdown("---")
st.markdown("""
### 💡 使用说明

1. **一键生成**：自动生成选题、文案、图片建议，输出完整内容整理格式
2. **热点选题**：从热点日历读取热点，生成选题方案
3. **选题文案**：根据已通过的选题生成正文
4. **图片建议**：为已通过的文案生成拍摄建议
5. **内容整理**：将文案整合成完整发布格式

**注意**：一键生成工作流已预填飞书表格ID，无需额外配置。
""")