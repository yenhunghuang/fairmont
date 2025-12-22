"""Streamlit main application."""

import streamlit as st
import os


# Page configuration
st.set_page_config(
    page_title="家具報價單系統",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables."""
    if "api_client" not in st.session_state:
        from services.api_client import APIClient
        backend_host = os.getenv("BACKEND_HOST", "localhost")
        backend_port = os.getenv("BACKEND_PORT", "8000")
        base_url = f"http://{backend_host}:{backend_port}"
        st.session_state.api_client = APIClient(base_url=base_url)

    if "uploaded_documents" not in st.session_state:
        st.session_state.uploaded_documents = []

    if "quotation_id" not in st.session_state:
        st.session_state.quotation_id = None


def get_api_client():
    """Get API client from session state with fallback initialization."""
    if "api_client" not in st.session_state:
        init_session_state()
    return st.session_state.api_client


# Initialize session state at module level (before any page code runs)
init_session_state()


def main():
    """Main application entry point."""

    # Sidebar navigation
    st.sidebar.title("家具報價單系統")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "選擇功能",
        ["上傳 PDF", "預覽報價單"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        "📋 家具報價單自動化系統\n\n"
        "上傳 BOQ PDF 檔案，系統會自動解析並產出惠而蒙格式的 Excel 報價單。"
    )

    # Page routing
    if page == "上傳 PDF":
        from pages.upload import main as upload_main
        upload_main()
    elif page == "預覽報價單":
        from pages.preview import main as preview_main
        preview_main()




if __name__ == "__main__":
    main()
