"""Streamlit main application - POC version with simplified step-based flow."""

import streamlit as st
import os


# Page configuration
st.set_page_config(
    page_title="家具報價單系統",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def init_session_state():
    """Initialize session state variables."""
    # API Client
    if "api_client" not in st.session_state:
        from services.api_client import APIClient
        backend_host = os.getenv("BACKEND_HOST", "localhost")
        backend_port = os.getenv("BACKEND_PORT", "8000")
        base_url = f"http://{backend_host}:{backend_port}"
        st.session_state.api_client = APIClient(base_url=base_url)

    # Workflow step
    if "step" not in st.session_state:
        st.session_state.step = "upload"  # 三個步驟：upload, processing, download

    # Current task info
    if "current_task_id" not in st.session_state:
        st.session_state.current_task_id = None

    if "current_document_ids" not in st.session_state:
        st.session_state.current_document_ids = []

    if "quotation_id" not in st.session_state:
        st.session_state.quotation_id = None

    if "excel_content" not in st.session_state:
        st.session_state.excel_content = None


def get_api_client():
    """Get API client from session state."""
    if "api_client" not in st.session_state:
        init_session_state()
    return st.session_state.api_client


# Initialize session state at module level
init_session_state()


def show_step_indicator():
    """顯示簡單的步驟指示器"""
    steps = ["📤 上傳", "⏳ 處理", "📥 下載"]
    step_indices = {"upload": 0, "processing": 1, "download": 2}
    current_step = step_indices.get(st.session_state.step, 0)

    cols = st.columns(len(steps))
    for i, (col, step) in enumerate(zip(cols, steps)):
        with col:
            if i <= current_step:
                if i == current_step:
                    st.markdown(f"### {step} 💫")
                else:
                    st.markdown(f"### {step} ✅")
            else:
                st.markdown(f"### {step}")


def show_upload_page():
    """上傳頁面"""
    st.title("📋 家具報價單系統")
    st.markdown("上傳 BOQ PDF 檔案，系統自動解析並產出 Excel 報價單")
    st.markdown("---")

    show_step_indicator()
    st.markdown("---")

    # File uploader
    st.subheader("📁 上傳 PDF 檔案")
    uploaded_files = st.file_uploader(
        "選擇 PDF 檔案（最多 5 個，每個最大 50MB）",
        type=["pdf"],
        accept_multiple_files=True,
        key="file_uploader",
    )

    if uploaded_files:
        st.info(f"✅ 已選擇 {len(uploaded_files)} 個檔案")

        for file in uploaded_files:
            st.caption(f"📄 {file.name}")

        if st.button("🚀 上傳並開始解析", type="primary", use_container_width=True):
            with st.spinner("正在上傳..."):
                try:
                    client = get_api_client()

                    # Convert to file format
                    files_data = [(f.name, f.read()) for f in uploaded_files]

                    # Upload and parse
                    response = client.upload_files(files_data)

                    if not response.get("success"):
                        st.error(f"❌ 上傳失敗：{response.get('message', '未知錯誤')}")
                        return

                    # Extract document IDs and task info
                    data = response.get("data", {})
                    documents = data.get("documents", [])
                    parse_tasks = data.get("parse_tasks", [])

                    if not parse_tasks:
                        st.error("❌ 無法啟動解析任務")
                        return

                    # Store info and advance to processing step
                    st.session_state.current_document_ids = [d.get("id") for d in documents]
                    st.session_state.current_task_id = parse_tasks[0].get("task_id")  # Track first task
                    st.session_state.step = "processing"

                    st.success("✅ 上傳成功！正在解析...")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 錯誤：{str(e)}")
    else:
        st.info("👇 請選擇要上傳的 PDF 檔案")


def show_processing_page():
    """處理頁面 - 顯示即時進度"""
    st.title("📋 家具報價單系統")
    st.markdown("---")

    show_step_indicator()
    st.markdown("---")

    st.subheader("🔄 正在處理您的檔案...")

    client = get_api_client()
    task_id = st.session_state.current_task_id

    if not task_id:
        st.error("❌ 錯誤：無效的任務 ID")
        if st.button("返回上傳"):
            st.session_state.step = "upload"
            st.rerun()
        return

    # Progress display
    progress_bar = st.progress(0)
    status_text = st.empty()
    error_text = st.empty()

    try:
        import time
        max_wait = 300  # 5 minutes
        elapsed = 0

        while elapsed < max_wait:
            # Get task status
            task_response = client.get_task_status(task_id)

            if not task_response.get("success"):
                error_text.error(f"❌ 無法取得任務狀態：{task_response.get('message')}")
                time.sleep(2)
                elapsed += 2
                continue

            task_data = task_response.get("data", {})
            task_status = task_data.get("status")
            progress = task_data.get("progress", 0)
            message = task_data.get("message", "")

            # Update UI
            progress_bar.progress(min(progress / 100, 0.99))
            status_text.info(f"⏳ {message or '處理中...'} ({progress}%)")

            # Check if complete
            if task_status == "completed":
                progress_bar.progress(1.0)
                status_text.success("✅ 處理完成！")

                # Move to next step
                st.session_state.step = "download"
                st.rerun()
                return

            elif task_status == "failed":
                error_text.error(f"❌ 處理失敗：{task_data.get('error_message', '未知錯誤')}")
                if st.button("返回上傳"):
                    st.session_state.step = "upload"
                    st.rerun()
                return

            # Wait before next poll
            time.sleep(2)
            elapsed += 2
            st.rerun()

        # Timeout
        error_text.error(f"❌ 處理超時（{max_wait} 秒）")
        if st.button("返回上傳"):
            st.session_state.step = "upload"
            st.rerun()

    except Exception as e:
        error_text.error(f"❌ 錯誤：{str(e)}")
        if st.button("返回上傳"):
            st.session_state.step = "upload"
            st.rerun()


def show_download_page():
    """下載頁面 - 建立報價單並導出"""
    st.title("📋 家具報價單系統")
    st.markdown("---")

    show_step_indicator()
    st.markdown("---")

    st.subheader("📊 建立報價單")

    client = get_api_client()
    document_ids = st.session_state.current_document_ids

    if not document_ids:
        st.error("❌ 錯誤：無效的文件列表")
        if st.button("重新開始"):
            st.session_state.step = "upload"
            st.rerun()
        return

    try:
        # Create quotation
        with st.spinner("正在建立報價單..."):
            quotation_response = client.create_quotation(document_ids)

            if not quotation_response.get("success"):
                st.error(f"❌ 建立報價單失敗：{quotation_response.get('message')}")
                if st.button("返回上傳"):
                    st.session_state.step = "upload"
                    st.rerun()
                return

            quotation_id = quotation_response.get("data", {}).get("id")
            st.session_state.quotation_id = quotation_id

            st.success(f"✅ 報價單已建立 (ID: {quotation_id})")

        st.markdown("---")

        # Export to Excel
        st.subheader("📥 匯出 Excel")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.write("點擊按鈕產生並下載 Excel 報價單")

        with col2:
            if st.button("產出 Excel", type="primary", use_container_width=True):
                with st.spinner("正在產生 Excel..."):
                    try:
                        # Get Excel file
                        excel_content = client.get_quotation_excel(
                            quotation_id,
                            include_photos=True,
                            photo_height_cm=3.0,
                        )

                        # Download button
                        st.download_button(
                            label="⬇️ 點擊下載 Excel",
                            data=excel_content,
                            file_name=f"報價單_{quotation_id}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                        st.success("✅ Excel 已準備好下載！")

                    except Exception as e:
                        st.error(f"❌ 產生 Excel 失敗：{str(e)}")

        st.markdown("---")

        # Next steps
        st.subheader("🔄 後續步驟")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📤 上傳新檔案", use_container_width=True):
                st.session_state.step = "upload"
                st.session_state.current_task_id = None
                st.session_state.current_document_ids = []
                st.session_state.quotation_id = None
                st.rerun()

        with col2:
            if st.button("🔄 重新開始", use_container_width=True):
                # Reset all state
                for key in list(st.session_state.keys()):
                    if key not in ["api_client"]:
                        del st.session_state[key]
                st.session_state.step = "upload"
                st.rerun()

    except Exception as e:
        st.error(f"❌ 錯誤：{str(e)}")
        if st.button("返回上傳"):
            st.session_state.step = "upload"
            st.rerun()


def main():
    """Main application entry point."""

    # Route based on current step
    if st.session_state.step == "upload":
        show_upload_page()
    elif st.session_state.step == "processing":
        show_processing_page()
    elif st.session_state.step == "download":
        show_download_page()
    else:
        # Default to upload
        st.session_state.step = "upload"
        show_upload_page()


if __name__ == "__main__":
    main()
