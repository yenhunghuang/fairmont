"""Streamlit main application - POC version with simplified step-based flow."""

import streamlit as st
import os
from styles import apply_poc_styles


# Page configuration
st.set_page_config(
    page_title="家具報價單系統",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Apply POC styles
apply_poc_styles()


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

    # Current task info - 支援多任務追蹤
    if "current_task_id" not in st.session_state:
        st.session_state.current_task_id = None

    if "current_task_ids" not in st.session_state:
        st.session_state.current_task_ids = []  # 所有任務 ID

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
    """顯示簡單的步驟指示器（緊湊版）"""
    steps = ["📤 上傳", "⏳ 處理", "📥 下載"]
    step_indices = {"upload": 0, "processing": 1, "download": 2}
    current_step = step_indices.get(st.session_state.step, 0)

    # Build compact step indicator HTML
    step_html = '<div style="display: flex; justify-content: center; gap: 2rem; padding: 0.5rem 0;">'
    for i, step in enumerate(steps):
        if i == current_step:
            style = "color: #2C5F7F; font-weight: bold; font-size: 1.1rem;"
            label = f"{step} 💫"
        elif i < current_step:
            style = "color: #28A745; font-size: 1.1rem;"
            label = f"{step} ✅"
        else:
            style = "color: #999; font-size: 1.1rem;"
            label = step
        step_html += f'<span style="{style}">{label}</span>'
    step_html += '</div>'

    st.markdown(step_html, unsafe_allow_html=True)


def show_upload_page():
    """上傳頁面"""
    # Compact header
    st.markdown(
        """
        <h1 style="color: #2C5F7F; border-bottom: 3px solid #2C5F7F; padding-bottom: 8px; margin-bottom: 5px;">
            📋 家具報價單系統
        </h1>
        <p style="color: #666; margin: 0 0 10px 0;">上傳 BOQ PDF 檔案，系統自動解析並產出 Excel 報價單</p>
        """,
        unsafe_allow_html=True,
    )

    show_step_indicator()

    # File uploader section - compact but prominent
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #f0f7fa 0%, #e3f0f5 100%);
                    border: 3px dashed #2C5F7F; border-radius: 16px;
                    padding: 1.2rem; margin: 0.8rem 0; text-align: center;">
            <span style="font-size: 2rem;">📁</span>
            <span style="color: #2C5F7F; font-size: 1.4rem; font-weight: bold; margin-left: 0.5rem;">上傳 PDF 檔案</span>
            <p style="color: #666; font-size: 0.95rem; margin: 0.5rem 0 0 0;">
                支援拖放上傳，可一次選擇多個檔案 &nbsp;|&nbsp; 📌 最多 5 個，每個最大 50MB
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "選擇 PDF 檔案",
        type=["pdf"],
        accept_multiple_files=True,
        key="file_uploader",
        help="支援 BOQ 數量總表與明細規格表，系統自動偵測並合併",
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.markdown("---")
        # File list with better styling
        st.markdown(
            f"""
            <div style="background: #e8f5e9; border-radius: 12px; padding: 1rem; margin: 1rem 0;">
                <p style="color: #2e7d32; font-weight: 600; margin: 0; font-size: 1.1rem;">
                    ✅ 已選擇 {len(uploaded_files)} 個檔案
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Display file list in columns for better layout
        for file in uploaded_files:
            file_size_mb = file.size / (1024 * 1024)
            st.markdown(
                f"""
                <div style="background: #f5f5f5; border-radius: 8px; padding: 0.75rem 1rem;
                            margin: 0.5rem 0; display: flex; align-items: center;
                            border-left: 4px solid #2C5F7F;">
                    <span style="font-size: 1.2rem; margin-right: 0.75rem;">📄</span>
                    <span style="flex: 1; font-weight: 500;">{file.name}</span>
                    <span style="color: #666; font-size: 0.9rem;">{file_size_mb:.2f} MB</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

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
                    st.session_state.current_task_ids = [t.get("task_id") for t in parse_tasks]
                    st.session_state.current_task_id = parse_tasks[0].get("task_id")  # 向後相容
                    st.session_state.step = "processing"

                    st.success("✅ 上傳成功！正在解析...")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 錯誤：{str(e)}")
    else:
        # Empty state - no additional hint needed as the box above is clear
        pass


def show_processing_page():
    """處理頁面 - 顯示即時進度（支援多任務）"""
    st.title("📋 家具報價單系統")
    st.markdown("---")

    show_step_indicator()
    st.markdown("---")

    st.subheader("🔄 正在處理您的檔案...")

    client = get_api_client()
    task_ids = st.session_state.get("current_task_ids", [])

    # 向後相容：如果沒有 current_task_ids，使用 current_task_id
    if not task_ids and st.session_state.current_task_id:
        task_ids = [st.session_state.current_task_id]

    if not task_ids:
        st.error("❌ 錯誤：無效的任務 ID")
        if st.button("返回上傳"):
            st.session_state.step = "upload"
            st.rerun()
        return

    # 顯示任務數量
    st.caption(f"📄 共 {len(task_ids)} 個檔案正在處理")

    # Progress display for each task
    task_containers = {}
    for i, task_id in enumerate(task_ids):
        task_containers[task_id] = {
            "status": st.empty(),
            "progress": st.progress(0),
        }

    error_text = st.empty()

    try:
        import time
        max_wait = 300  # 5 minutes
        elapsed = 0

        while elapsed < max_wait:
            all_done = True
            any_success = False
            all_failed = True
            failed_messages = []

            for task_id in task_ids:
                # Get task status
                task_response = client.get_task_status(task_id)

                if not task_response.get("success"):
                    task_containers[task_id]["status"].warning(f"⚠️ 無法取得任務狀態")
                    all_done = False
                    all_failed = False
                    continue

                task_data = task_response.get("data", {})
                task_status = task_data.get("status")
                progress = task_data.get("progress", 0)
                message = task_data.get("message", "")

                # Update UI for this task
                task_containers[task_id]["progress"].progress(min(progress / 100, 0.99))

                if task_status == "completed":
                    task_containers[task_id]["status"].success(f"✅ {message or '完成'}")
                    task_containers[task_id]["progress"].progress(1.0)
                    any_success = True
                    all_failed = False
                elif task_status == "failed":
                    error_msg = task_data.get("message") or task_data.get("error") or "未知錯誤"
                    task_containers[task_id]["status"].error(f"❌ {error_msg}")
                    failed_messages.append(error_msg)
                else:
                    task_containers[task_id]["status"].info(f"⏳ {message or '處理中...'} ({progress}%)")
                    all_done = False
                    all_failed = False

            # 決定下一步
            if all_done:
                if any_success:
                    # 至少有一個成功，可以繼續
                    st.success("✅ 處理完成！")
                    if failed_messages:
                        st.warning(f"⚠️ 部分檔案處理失敗：{len(failed_messages)} 個")
                    st.session_state.step = "download"
                    time.sleep(1)
                    st.rerun()
                    return
                elif all_failed:
                    # 全部失敗
                    error_text.error("❌ 所有檔案處理失敗")
                    for msg in failed_messages[:3]:  # 最多顯示 3 個錯誤
                        st.error(f"• {msg}")
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

    # 如果已經有報價單，直接跳到匯出（避免重複建立）
    if st.session_state.quotation_id:
        quotation_id = st.session_state.quotation_id
        st.success(f"✅ 報價單已建立 (ID: {quotation_id})")
    else:
        try:
            # Create quotation with cross-document merge
            # 使用跨表合併 API，自動處理數量總表與明細規格表的合併
            with st.spinner("正在建立報價單（跨表合併中）..."):
                # 多檔案時使用跨表合併
                if len(document_ids) > 1:
                    quotation_response = client.create_merged_quotation(document_ids)
                else:
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

        except Exception as e:
            st.error(f"❌ 錯誤：{str(e)}")
            if st.button("返回上傳"):
                st.session_state.step = "upload"
                st.rerun()
            return

    st.markdown("---")

    # Export to Excel
    st.subheader("📥 匯出 Excel")

    # 確保有 quotation_id
    quotation_id = st.session_state.quotation_id

    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("點擊按鈕產生並下載 Excel 報價單")

    with col2:
        if st.button("產出 Excel", type="primary", use_container_width=True):
            with st.spinner("正在產生 Excel..."):
                try:
                    excel_content = client.get_quotation_excel(
                        quotation_id,
                        include_photos=True,
                        photo_height_cm=3.0,
                    )

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
            st.session_state.current_task_ids = []
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
