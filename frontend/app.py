"""Streamlit main application."""

import streamlit as st
import asyncio
import os
from pathlib import Path
import logging


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def main():
    """Main application entry point."""
    init_session_state()

    # Sidebar navigation
    st.sidebar.title("家具報價單系統")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "選擇功能",
        ["首頁", "上傳 PDF", "預覽報價單", "匯出 Excel", "驗證材料"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        "📋 家具報價單自動化系統\n\n"
        "上傳 BOQ PDF 檔案，系統會自動解析並產出惠而蒙格式的 Excel 報價單。"
    )

    # Page routing
    if page == "首頁":
        show_home()
    elif page == "上傳 PDF":
        st.write("上傳 PDF 功能準備中...")
    elif page == "預覽報價單":
        st.write("預覽報價單功能準備中...")
    elif page == "匯出 Excel":
        st.write("匯出 Excel 功能準備中...")
    elif page == "驗證材料":
        st.write("驗證材料功能準備中...")


def show_home():
    """Show home page."""
    st.title("🏠 首頁")
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📋 功能介紹")
        st.write(
            """
            ### 家具報價單系統功能

            - **📤 上傳 PDF**: 支援上傳單個或多個 BOQ PDF 檔案
            - **🤖 智慧解析**: 使用 Google Gemini AI 自動解析 PDF 內容
            - **📊 資料提取**: 自動提取家具項目、規格、圖片等資訊
            - **📈 合併處理**: 支援多檔案合併產出單一報價單
            - **📸 平面圖核對**: 從平面圖補充缺失的數量資訊
            - **📥 Excel 匯出**: 產出惠而蒙格式的 Excel 報價單
            """
        )

    with col2:
        st.subheader("🚀 快速開始")
        st.write(
            """
            ### 三步驟快速上手

            1. **上傳檔案**: 進入「上傳 PDF」頁面上傳 BOQ 檔案
            2. **預覽資料**: 系統自動解析並顯示提取的資料
            3. **匯出報價**: 確認無誤後匯出 Excel 報價單

            💡 **提示**: 支援同時上傳多個 PDF 檔案，系統會自動合併處理
            """
        )

    st.markdown("---")

    # System status
    st.subheader("⚙️ 系統狀態")
    try:
        async def check_health():
            try:
                health = await st.session_state.api_client.health_check()
                return health
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return None

        health = asyncio.run(check_health())
        if health and health.get("status") == "healthy":
            st.success("✅ 後端服務正常運作")
            with st.expander("服務詳情"):
                st.json(health)
        else:
            st.error("❌ 後端服務連線失敗")
    except Exception as e:
        st.error(f"❌ 無法連接後端服務: {e}")

    st.markdown("---")

    # Features overview
    st.subheader("📌 支援的功能")
    features = [
        ("📤 **單檔上傳**", "上傳單個 PDF 檔案進行解析"),
        ("📁 **批量上傳**", "同時上傳多個 PDF 檔案（最多 5 個）"),
        ("🔍 **自動解析**", "使用 Gemini AI 自動提取資料"),
        ("🖼️ **圖片提取**", "自動提取 PDF 中的家具照片"),
        ("📐 **平面圖核對**", "從平面圖補充數量資訊"),
        ("📊 **合併處理**", "將多份 BOQ 合併為單一報價單"),
        ("📋 **完整驗證", "提供材料驗證介面確保準確性"),
        ("📥 **Excel 匯出**", "產出惠而蒙格式的 Excel 檔案"),
    ]

    cols = st.columns(2)
    for idx, (title, description) in enumerate(features):
        with cols[idx % 2]:
            st.write(f"{title}\n{description}")


if __name__ == "__main__":
    main()
