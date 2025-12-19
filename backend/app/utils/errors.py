"""Error handling utilities."""

from enum import Enum
from typing import Optional, Any, Dict
import logging


logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Error code enumeration (繁體中文 messages)."""

    # File errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_SIZE_EXCEEDED = "FILE_SIZE_EXCEEDED"
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_UPLOAD_FAILED = "FILE_UPLOAD_FAILED"
    FILE_DELETION_FAILED = "FILE_DELETION_FAILED"

    # PDF errors
    PDF_PARSING_FAILED = "PDF_PARSING_FAILED"
    PDF_CORRUPTED = "PDF_CORRUPTED"
    PDF_PASSWORD_PROTECTED = "PDF_PASSWORD_PROTECTED"
    PDF_EXTRACT_FAILED = "PDF_EXTRACT_FAILED"

    # Gemini API errors
    GEMINI_API_ERROR = "GEMINI_API_ERROR"
    GEMINI_RATE_LIMIT = "GEMINI_RATE_LIMIT"
    GEMINI_QUOTA_EXCEEDED = "GEMINI_QUOTA_EXCEEDED"

    # Data validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # Resource errors
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    QUOTATION_NOT_FOUND = "QUOTATION_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"

    # Processing errors
    PROCESSING_FAILED = "PROCESSING_FAILED"
    EXPORT_FAILED = "EXPORT_FAILED"
    MERGE_FAILED = "MERGE_FAILED"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


ERROR_MESSAGES: Dict[ErrorCode, str] = {
    # File errors
    ErrorCode.FILE_NOT_FOUND: "找不到檔案",
    ErrorCode.FILE_SIZE_EXCEEDED: "檔案大小超過限制（最大 50MB）",
    ErrorCode.INVALID_FILE_FORMAT: "無效的檔案格式，請上傳 PDF 檔案",
    ErrorCode.FILE_UPLOAD_FAILED: "檔案上傳失敗，請重試",
    ErrorCode.FILE_DELETION_FAILED: "檔案刪除失敗",

    # PDF errors
    ErrorCode.PDF_PARSING_FAILED: "PDF 解析失敗",
    ErrorCode.PDF_CORRUPTED: "PDF 檔案損毀，無法解析",
    ErrorCode.PDF_PASSWORD_PROTECTED: "PDF 檔案受密碼保護，無法解析",
    ErrorCode.PDF_EXTRACT_FAILED: "PDF 內容提取失敗",

    # Gemini API errors
    ErrorCode.GEMINI_API_ERROR: "Gemini API 呼叫失敗",
    ErrorCode.GEMINI_RATE_LIMIT: "Gemini API 速率限制，請稍後重試",
    ErrorCode.GEMINI_QUOTA_EXCEEDED: "Gemini API 配額已用盡",

    # Data validation errors
    ErrorCode.VALIDATION_ERROR: "資料驗證失敗",
    ErrorCode.INVALID_REQUEST: "無效的請求",
    ErrorCode.MISSING_REQUIRED_FIELD: "缺少必要欄位",

    # Resource errors
    ErrorCode.NOT_FOUND: "資源不存在",
    ErrorCode.RESOURCE_NOT_FOUND: "找不到請求的資源",
    ErrorCode.DOCUMENT_NOT_FOUND: "找不到文件",
    ErrorCode.QUOTATION_NOT_FOUND: "找不到報價單",
    ErrorCode.TASK_NOT_FOUND: "找不到處理任務",

    # Processing errors
    ErrorCode.PROCESSING_FAILED: "處理失敗",
    ErrorCode.EXPORT_FAILED: "匯出失敗",
    ErrorCode.MERGE_FAILED: "合併失敗",

    # Server errors
    ErrorCode.INTERNAL_ERROR: "伺服器內部錯誤",
    ErrorCode.SERVICE_UNAVAILABLE: "服務暫時不可用，請稍後重試",
}


class APIError(Exception):
    """Custom API error exception."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        status_code: int = 400,
        details: Optional[Any] = None,
    ):
        """
        Initialize APIError.

        Args:
            error_code: Error code from ErrorCode enum
            message: Custom error message (overrides default)
            status_code: HTTP status code
            details: Additional error details
        """
        self.error_code = error_code
        self.message = message or ERROR_MESSAGES.get(error_code, "發生錯誤")
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation."""
        return self.message


def raise_error(
    error_code: ErrorCode,
    message: Optional[str] = None,
    status_code: int = 400,
    details: Optional[Any] = None,
) -> None:
    """
    Raise an API error.

    Args:
        error_code: Error code from ErrorCode enum
        message: Custom error message (overrides default)
        status_code: HTTP status code
        details: Additional error details

    Raises:
        APIError: Always raises APIError with provided parameters
    """
    raise APIError(
        error_code=error_code,
        message=message,
        status_code=status_code,
        details=details,
    )


def log_error(error: Exception, context: str = "") -> None:
    """
    Log an error with context.

    Args:
        error: Exception to log
        context: Context description
    """
    if isinstance(error, APIError):
        logger.error(
            f"APIError [{context}]: {error.error_code} - {error.message}",
            extra={"details": error.details},
        )
    else:
        logger.error(f"Error [{context}]: {str(error)}", exc_info=True)
