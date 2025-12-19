"""
錯誤處理與繁體中文訊息模組

提供：
1. 統一的錯誤處理機制
2. 繁體中文錯誤訊息
3. Streamlit 錯誤顯示
"""

import streamlit as st
import traceback
from typing import Optional, Callable, Any
from functools import wraps
import logging
from datetime import datetime


# ==================== 錯誤訊息對照表 ====================

ERROR_MESSAGES = {
    # 網路相關
    'connection_error': '無法連接到伺服器，請檢查網路連線',
    'timeout_error': '請求超時，請稍後再試',
    'server_error': '伺服器錯誤，請聯繫系統管理員',

    # 檔案相關
    'file_not_found': '找不到指定的檔案',
    'file_too_large': '檔案大小超過限制',
    'invalid_file_format': '不支援的檔案格式',
    'file_upload_error': '檔案上傳失敗',

    # 資料相關
    'invalid_data': '資料格式不正確',
    'missing_required_field': '缺少必填欄位',
    'validation_error': '資料驗證失敗',

    # 認證相關
    'unauthorized': '未授權，請先登入',
    'forbidden': '沒有權限執行此操作',

    # 任務相關
    'task_not_found': '找不到指定的任務',
    'task_failed': '任務執行失敗',
    'task_timeout': '任務執行超時',

    # 通用
    'unknown_error': '發生未知錯誤',
    'operation_failed': '操作失敗',
}


# ==================== 錯誤處理類別 ====================

class AppError(Exception):
    """應用程式基礎錯誤類別"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        self.timestamp = datetime.now().isoformat()
        super().__init__(self.message)

    def __str__(self):
        return self.message

    def to_dict(self):
        """轉換為字典格式"""
        return {
            'message': self.message,
            'error_code': self.error_code,
            'details': self.details,
            'timestamp': self.timestamp,
            'original_error': str(self.original_error) if self.original_error else None
        }


class ValidationError(AppError):
    """資料驗證錯誤"""
    pass


class APIError(AppError):
    """API 相關錯誤"""
    pass


class FileError(AppError):
    """檔案相關錯誤"""
    pass


# ==================== 錯誤處理裝飾器 ====================

def handle_errors(
    error_message: str = "操作失敗",
    show_details: bool = False,
    log_error: bool = True,
    raise_error: bool = False
):
    """
    錯誤處理裝飾器

    Args:
        error_message: 自訂錯誤訊息
        show_details: 是否顯示詳細錯誤資訊
        log_error: 是否記錄錯誤
        raise_error: 是否重新拋出錯誤

    使用範例:
        @handle_errors("檔案上傳失敗", show_details=True)
        def upload_file():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except AppError as e:
                # 應用程式定義的錯誤
                display_error(e.message, details=e.details if show_details else None)
                if log_error:
                    log_exception(e)
                if raise_error:
                    raise
            except Exception as e:
                # 未預期的錯誤
                msg = f"{error_message}: {str(e)}"
                details = {'traceback': traceback.format_exc()} if show_details else None
                display_error(msg, details=details)
                if log_error:
                    log_exception(e)
                if raise_error:
                    raise AppError(msg, original_error=e)
        return wrapper
    return decorator


# ==================== Streamlit 錯誤顯示 ====================

def display_error(
    message: str,
    details: Optional[dict] = None,
    error_code: Optional[str] = None
):
    """
    在 Streamlit 中顯示錯誤訊息

    Args:
        message: 錯誤訊息
        details: 詳細資訊
        error_code: 錯誤代碼
    """
    # 顯示主要錯誤訊息
    st.error(f"❌ {message}")

    # 顯示錯誤代碼
    if error_code:
        st.caption(f"錯誤代碼: {error_code}")

    # 顯示詳細資訊
    if details:
        with st.expander("查看詳細資訊"):
            st.json(details)


def display_warning(message: str):
    """顯示警告訊息"""
    st.warning(f"⚠️ {message}")


def display_info(message: str):
    """顯示資訊訊息"""
    st.info(f"ℹ️ {message}")


def display_success(message: str):
    """顯示成功訊息"""
    st.success(f"✅ {message}")


# ==================== 錯誤記錄 ====================

def setup_logger(name: str = "app") -> logging.Logger:
    """設定 Logger"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 避免重複加入 handler
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def log_exception(error: Exception, extra_info: Optional[dict] = None):
    """記錄例外資訊"""
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }

    if extra_info:
        error_info.update(extra_info)

    logger.error(f"Exception occurred: {error_info}")


# ==================== 輸入驗證 ====================

def validate_required_fields(data: dict, required_fields: list) -> None:
    """
    驗證必填欄位

    Args:
        data: 資料字典
        required_fields: 必填欄位列表

    Raises:
        ValidationError: 如果缺少必填欄位
    """
    missing_fields = [field for field in required_fields if field not in data or not data[field]]

    if missing_fields:
        raise ValidationError(
            message=f"缺少必填欄位: {', '.join(missing_fields)}",
            error_code='missing_required_field',
            details={'missing_fields': missing_fields}
        )


def validate_file_size(file, max_size_mb: int = 10) -> None:
    """
    驗證檔案大小

    Args:
        file: 上傳的檔案
        max_size_mb: 最大檔案大小（MB）

    Raises:
        FileError: 如果檔案過大
    """
    file_size = len(file.getvalue()) if hasattr(file, 'getvalue') else file.size
    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise FileError(
            message=f"檔案大小超過限制（最大 {max_size_mb}MB）",
            error_code='file_too_large',
            details={
                'file_size': file_size,
                'max_size': max_size_bytes
            }
        )


def validate_file_extension(filename: str, allowed_extensions: list) -> None:
    """
    驗證檔案副檔名

    Args:
        filename: 檔案名稱
        allowed_extensions: 允許的副檔名列表（例如: ['.csv', '.xlsx']）

    Raises:
        FileError: 如果副檔名不被允許
    """
    file_ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if file_ext not in allowed_extensions:
        raise FileError(
            message=f"不支援的檔案格式，請使用: {', '.join(allowed_extensions)}",
            error_code='invalid_file_format',
            details={
                'filename': filename,
                'file_extension': file_ext,
                'allowed_extensions': allowed_extensions
            }
        )


# ==================== 錯誤恢復 ====================

def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    error_message: str = "操作失敗"
):
    """
    重試裝飾器

    Args:
        max_attempts: 最大嘗試次數
        delay: 重試間隔（秒）
        error_message: 錯誤訊息

    使用範例:
        @with_retry(max_attempts=3, delay=1.0)
        def api_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import time

            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")

            # 所有嘗試都失敗
            raise AppError(
                message=f"{error_message}（已重試 {max_attempts} 次）",
                original_error=last_error
            )

        return wrapper
    return decorator


# ==================== 實用工具 ====================

def get_error_message(error_code: str, default: str = None) -> str:
    """
    根據錯誤代碼取得繁體中文錯誤訊息

    Args:
        error_code: 錯誤代碼
        default: 預設訊息（如果找不到對應的錯誤代碼）

    Returns:
        錯誤訊息
    """
    return ERROR_MESSAGES.get(error_code, default or ERROR_MESSAGES['unknown_error'])


def format_error_for_display(error: Exception) -> str:
    """
    格式化錯誤訊息供顯示

    Args:
        error: 例外物件

    Returns:
        格式化的錯誤訊息
    """
    if isinstance(error, AppError):
        return error.message
    else:
        return f"{type(error).__name__}: {str(error)}"
