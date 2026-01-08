"""Common utilities for POC - error handling and caching helpers."""

import streamlit as st
import functools
from typing import Callable, Any, Optional
import logging


logger = logging.getLogger(__name__)


def safe_api_call(
    func: Callable,
    error_msg: str = "操作失敗",
    show_details: bool = True,
) -> Any:
    """
    簡單的錯誤包裝器 - POC 級別。

    Args:
        func: 要執行的函數
        error_msg: 錯誤訊息前綴
        show_details: 是否顯示詳細錯誤

    Returns:
        函數結果或 None（出錯時）
    """
    try:
        return func()
    except Exception as e:
        error_detail = str(e) if show_details else ""
        full_msg = f"{error_msg}" + (f"：{error_detail}" if error_detail else "")
        st.error(f"❌ {full_msg}")
        logger.error(f"{error_msg}: {str(e)}", exc_info=True)
        return None


def get_cached_api_client():
    """
    獲取 API 客戶端（使用簡單的 session state 緩存）。

    Returns:
        APIClient 實例
    """
    if "api_client" not in st.session_state:
        from services.api_client import APIClient
        import os

        backend_host = os.getenv("BACKEND_HOST", "localhost")
        backend_port = os.getenv("BACKEND_PORT", "8000")
        base_url = f"http://{backend_host}:{backend_port}"
        st.session_state.api_client = APIClient(base_url=base_url)

    return st.session_state.api_client


def format_error_message(error: Exception, context: str = "") -> str:
    """
    格式化錯誤訊息為用戶友好的形式。

    Args:
        error: 異常物件
        context: 上下文信息

    Returns:
        格式化的錯誤訊息
    """
    error_str = str(error)

    # 常見錯誤模式
    if "404" in error_str or "not found" in error_str.lower():
        return f"找不到資源：{context}" if context else "找不到資源"
    elif "timeout" in error_str.lower():
        return "請求超時，請檢查網路連線"
    elif "connection" in error_str.lower():
        return "無法連接到伺服器，請檢查後端是否運行"
    elif "file too large" in error_str.lower():
        return "檔案過大，請使用小於 50MB 的檔案"
    else:
        return f"{context}：{error_str}" if context else error_str


def display_user_friendly_error(error: Exception, context: str = ""):
    """
    顯示用戶友好的錯誤訊息。

    Args:
        error: 異常物件
        context: 上下文信息
    """
    msg = format_error_message(error, context)
    st.error(f"❌ {msg}")
    logger.error(f"Error in {context}: {str(error)}", exc_info=True)


def display_success_message(message: str, icon: str = "✅"):
    """
    顯示成功訊息。

    Args:
        message: 訊息內容
        icon: 圖標
    """
    st.success(f"{icon} {message}")
