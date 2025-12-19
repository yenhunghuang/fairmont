"""Input validation utilities."""

import logging
from typing import Optional

from .errors import ErrorCode, raise_error


logger = logging.getLogger(__name__)


class FileValidator:
    """Validates uploaded files."""

    ALLOWED_EXTENSIONS = {".pdf"}
    ALLOWED_MIME_TYPES = {"application/pdf"}

    def __init__(self, max_file_size_mb: int = 50, max_files: int = 5):
        """
        Initialize FileValidator.

        Args:
            max_file_size_mb: Maximum file size in MB
            max_files: Maximum number of files allowed
        """
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_files = max_files

    def validate_file(
        self,
        filename: str,
        file_size: int,
        mime_type: Optional[str] = None,
    ) -> bool:
        """
        Validate a single file.

        Args:
            filename: Original filename
            file_size: File size in bytes
            mime_type: MIME type of file

        Returns:
            True if valid

        Raises:
            APIError: If validation fails
        """
        # Check filename
        if not filename:
            raise_error(ErrorCode.INVALID_REQUEST, "檔名不可為空")

        # Check file extension
        import os
        _, ext = os.path.splitext(filename.lower())
        if ext not in self.ALLOWED_EXTENSIONS:
            raise_error(
                ErrorCode.INVALID_FILE_FORMAT,
                f"不支援的檔案格式：{ext}，只接受 PDF 檔案",
            )

        # Check MIME type if provided
        if mime_type and mime_type not in self.ALLOWED_MIME_TYPES:
            raise_error(
                ErrorCode.INVALID_FILE_FORMAT,
                f"無效的 MIME 類型：{mime_type}",
            )

        # Check file size
        if file_size > self.max_file_size_bytes:
            raise_error(
                ErrorCode.FILE_SIZE_EXCEEDED,
                f"檔案大小超過限制（{file_size / (1024*1024):.1f}MB > {self.max_file_size_bytes / (1024*1024):.0f}MB）",
            )

        if file_size == 0:
            raise_error(ErrorCode.INVALID_REQUEST, "檔案為空")

        logger.info(f"File validation passed: {filename} ({file_size} bytes)")
        return True

    def validate_file_count(self, count: int) -> bool:
        """
        Validate number of files.

        Args:
            count: Number of files

        Returns:
            True if valid

        Raises:
            APIError: If validation fails
        """
        if count <= 0:
            raise_error(ErrorCode.INVALID_REQUEST, "至少需要上傳一個檔案")

        if count > self.max_files:
            raise_error(
                ErrorCode.INVALID_REQUEST,
                f"超過最大檔案數量限制（{count} > {self.max_files}）",
            )

        return True


class DataValidator:
    """Validates data models."""

    @staticmethod
    def validate_boq_item(item_no: str, description: str) -> bool:
        """
        Validate BOQ item required fields.

        Args:
            item_no: Item number
            description: Item description

        Returns:
            True if valid

        Raises:
            APIError: If validation fails
        """
        if not item_no or not item_no.strip():
            raise_error(
                ErrorCode.VALIDATION_ERROR,
                "項次編號不可為空",
            )

        if not description or not description.strip():
            raise_error(
                ErrorCode.VALIDATION_ERROR,
                "項目描述不可為空",
            )

        return True

    @staticmethod
    def validate_qty(qty: Optional[float]) -> bool:
        """
        Validate quantity.

        Args:
            qty: Quantity value

        Returns:
            True if valid

        Raises:
            APIError: If validation fails
        """
        if qty is not None:
            if qty < 0:
                raise_error(
                    ErrorCode.VALIDATION_ERROR,
                    "數量不可為負數",
                )

        return True

    @staticmethod
    def validate_document_id(document_id: str) -> bool:
        """
        Validate document ID format.

        Args:
            document_id: Document ID to validate

        Returns:
            True if valid

        Raises:
            APIError: If validation fails
        """
        if not document_id or not document_id.strip():
            raise_error(
                ErrorCode.MISSING_REQUIRED_FIELD,
                "文件 ID 不可為空",
            )

        return True
