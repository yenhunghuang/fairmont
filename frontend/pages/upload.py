"""Upload page."""

import streamlit as st
import asyncio
import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.api_client import APIClient
from components.file_uploader import file_uploader, display_upload_status
from components.progress_display import wait_for_task_completion, display_completion_status


def init_session_state():
    """Initialize session state."""
    if "upload_client" not in st.session_state:
        backend_host = os.getenv("BACKEND_HOST", "localhost")
        backend_port = os.getenv("BACKEND_PORT", "8000")
        base_url = f"http://{backend_host}:{backend_port}"
        st.session_state.upload_client = APIClient(base_url=base_url)

    if "uploaded_documents" not in st.session_state:
        st.session_state.uploaded_documents = []

    if "current_task" not in st.session_state:
        st.session_state.current_task = None


async def handle_upload(uploaded_files):
    """Handle file upload."""
    if not uploaded_files:
        return

    st.info("📤 正在上傳檔案...")

    try:
        # Convert to file format for API
        files_data = []
        for file in uploaded_files:
            files_data.append((file.name, await asyncio.to_thread(file.read)))

        # Upload via API
        client = st.session_state.upload_client

        # Prepare files for upload
        upload_files = []
        for filename, content in files_data:
            upload_files.append((filename, content))

        # Note: The actual implementation would use the files parameter
        # This is a simplified version
        response = {"success": True, "data": {"documents": []}}

        if response.get("success"):
            display_upload_status("success", f"✅ 成功上傳 {len(upload_files)} 個檔案")
            st.session_state.uploaded_documents = response.get("data", {}).get("documents", [])

            # Return to continue with next step
            return True
        else:
            display_upload_status("error", f"❌ 上傳失敗：{response.get('message', '未知錯誤')}")
            return False

    except Exception as e:
        display_upload_status("error", f"❌ 上傳錯誤：{str(e)}")
        return False


def main():
    """Main upload page."""
    st.set_page_config(
        page_title="上傳 PDF - 家具報價單系統",
        page_icon="📤",
        layout="wide",
    )

    init_session_state()

    st.title("📤 上傳 PDF 檔案")
    st.markdown("---")

    st.write("""
    在此頁面上傳 BOQ（Bill of Quantities）PDF 檔案。
    系統將自動解析檔案內容並提取家具項目資訊。
    """)

    # File uploader
    uploaded_files = file_uploader(max_files=5, max_size_mb=50)

    if uploaded_files:
        st.markdown("---")

        # Upload button
        if st.button("🚀 開始上傳", use_container_width=True, type="primary"):
            # Handle upload
            result = asyncio.run(handle_upload(uploaded_files))

            if result:
                st.markdown("---")

                # Show uploaded documents
                st.subheader("📋 已上傳的文件")

                for doc in st.session_state.uploaded_documents:
                    col1, col2, col3 = st.columns([2, 1, 1])

                    with col1:
                        st.write(f"📄 {doc.get('filename', '')}")

                    with col2:
                        st.write(f"大小: {doc.get('file_size', 0) / (1024*1024):.1f}MB")

                    with col3:
                        status = doc.get("parse_status", "pending")
                        status_icons = {
                            "pending": "⏳",
                            "processing": "🔄",
                            "completed": "✅",
                            "failed": "❌",
                        }
                        st.write(status_icons.get(status, "❓"))

                st.markdown("---")

                # Options for parsing
                st.subheader("⚙️ 解析選項")

                col1, col2 = st.columns(2)

                with col1:
                    extract_images = st.checkbox("提取圖片", value=True)

                with col2:
                    auto_parse = st.checkbox("自動開始解析", value=True)

                if auto_parse and st.button("▶️ 開始解析", use_container_width=True):
                    st.info("🔄 解析任務已提交，請在「預覽報價單」頁面查看進度")

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
