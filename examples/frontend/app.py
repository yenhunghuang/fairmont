"""
Streamlit 多頁面應用程式主檔案

展示：
1. 多頁面架構
2. FastAPI 整合
3. Session State 管理
4. 統一的導航與佈局
"""

import streamlit as st
from pathlib import Path
import sys

# 加入 utils 路徑
sys.path.insert(0, str(Path(__file__).parent))

from utils.session_state import get_session_state
from utils.api_client import get_api_client, check_backend_connection
from utils.error_handler import display_error, handle_errors

# ==================== 頁面配置 ====================

st.set_page_config(
    page_title="Streamlit-FastAPI 整合範例",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 初始化 ====================

# Session State
session_state = get_session_state()

# API 客戶端
api_base_url = session_state.get('api_base_url', 'http://localhost:8000')
api_client = get_api_client(api_base_url)

# ==================== 側邊欄 ====================

with st.sidebar:
    st.title("🚀 導航選單")

    # 頁面選擇
    page = st.radio(
        "選擇頁面",
        ["首頁", "檔案上傳", "長時間任務", "任務管理", "設定"],
        key="page_selector"
    )

    st.divider()

    # 後端連線狀態
    st.subheader("後端狀態")
    if st.button("檢查連線", use_container_width=True):
        check_backend_connection(api_client)

    st.caption(f"後端 URL: {api_base_url}")

    st.divider()

    # Session 資訊
    with st.expander("Session 資訊"):
        st.json({
            "啟動時間": session_state.get('session_start_time'),
            "最後活動": session_state.get('last_activity_time'),
            "已上傳檔案數": len(session_state.get('uploaded_files', [])),
        })

    # 清除按鈕
    if st.button("清除 Session", use_container_width=True):
        session_state.reset_to_defaults()
        st.rerun()

# ==================== 主要內容區域 ====================

# 根據選擇的頁面顯示內容
if page == "首頁":
    from pages import home
    home.show(api_client, session_state)

elif page == "檔案上傳":
    from pages import file_upload
    file_upload.show(api_client, session_state)

elif page == "長時間任務":
    from pages import long_task
    long_task.show(api_client, session_state)

elif page == "任務管理":
    from pages import task_management
    task_management.show(api_client, session_state)

elif page == "設定":
    from pages import settings
    settings.show(api_client, session_state)

# ==================== 頁尾 ====================

st.divider()
st.caption("Streamlit-FastAPI 整合最佳實踐範例 | 2025")
