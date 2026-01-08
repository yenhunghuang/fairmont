"""Upload page."""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.file_uploader import file_uploader, display_upload_status
from components.progress_display import wait_for_task_completion, display_completion_status
from app import init_session_state, get_api_client

# Ensure session state is initialized
init_session_state()

# Additional session state for upload page
if "current_task" not in st.session_state:
    st.session_state.current_task = None


def handle_upload_and_parse(uploaded_files, extract_images: bool = True):
    """
    Handle file upload with automatic parsing.

    上傳 API 已整合自動解析功能，不需要額外呼叫 parse_document。
    API 返回 documents 和 parse_tasks，可直接用於追蹤進度。
    """
    if not uploaded_files:
        return None

    try:
        # Convert to file format for API
        files_data = []
        for file in uploaded_files:
            content = file.read()
            files_data.append((file.name, content))

        # Upload via API (自動啟動解析)
        client = st.session_state.api_client
        response = client.upload_files(files_data)

        if not response.get("success"):
            return {"error": response.get("message", "上傳失敗")}

        data = response.get("data", {})
        documents = data.get("documents", [])
        parse_tasks = data.get("parse_tasks", [])  # 直接從上傳回應取得

        st.session_state.uploaded_documents = documents

        return {"documents": documents, "parse_tasks": parse_tasks}

    except Exception as e:
        return {"error": str(e)}


def main():
    """Main upload page."""
    init_session_state()

    st.title("📤 上傳 PDF 檔案")
    st.markdown("---")

    st.write("""
    在此頁面上傳 BOQ（Bill of Quantities）PDF 檔案。
    系統將自動解析檔案內容並提取家具項目資訊。
    """)

    # Options
    extract_images = st.checkbox("提取圖片", value=True)

    # File uploader
    uploaded_files = file_uploader(max_files=5, max_size_mb=50)

    if uploaded_files:
        st.markdown("---")

        # Upload button
        if st.button("🚀 上傳並解析", use_container_width=True, type="primary"):
            with st.spinner("📤 正在上傳並解析檔案..."):
                result = handle_upload_and_parse(uploaded_files, extract_images)

            if result and "error" in result:
                st.error(f"❌ 錯誤：{result['error']}")
            elif result:
                documents = result.get("documents", [])
                parse_tasks = result.get("parse_tasks", [])

                st.success(f"✅ 成功上傳 {len(documents)} 個檔案")

                if parse_tasks:
                    st.info(f"🔄 已啟動 {len(parse_tasks)} 個解析任務")

                st.markdown("---")

                # Show uploaded documents
                st.subheader("📋 已上傳的文件")

                for doc in documents:
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        st.write(f"📄 {doc.get('filename', '')}")

                    with col2:
                        size_mb = doc.get('file_size', 0) / (1024*1024)
                        st.write(f"大小: {size_mb:.2f} MB")

                    with col3:
                        st.write(f"ID: {doc.get('id', '')[:8]}...")

                # Next steps
                st.markdown("---")
                st.info("""
                ✅ **下一步：**
                1. 前往「預覽報價單」頁面查看解析進度
                2. 確認提取的項目資訊無誤
                3. 產出 Excel 報價單
                """)


if __name__ == "__main__":
    main()
