"""Input validation utilities."""

import logging
import os
from typing import Optional

from .errors import ErrorCode, raise_error


logger = logging.getLogger(__name__)


class FileValidator:
    """Validates uploaded files."""

    ALLOWED_EXTENSIONS = {".pdf"}
    ALLOWED_MIME_TYPES = {"application/pdf"}

    def __init__(self, max_file_size_mb: int = 50, max_files: int = 5):
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_files = max_files

    def validate_file(
        self,
        filename: str,
        file_size: int,
        mime_type: Optional[str] = None,
    ) -> bool:
        if not filename:
            raise_error(ErrorCode.INVALID_REQUEST, "檔名不可為空")

        _, ext = os.path.splitext(filename.lower())
        if ext not in self.ALLOWED_EXTENSIONS:
            raise_error(
                ErrorCode.INVALID_FILE_FORMAT,
                f"不支援的檔案格式：{ext}，只接受 PDF 檔案",
            )

        if mime_type and mime_type not in self.ALLOWED_MIME_TYPES:
            raise_error(
                ErrorCode.INVALID_FILE_FORMAT,
                f"無效的 MIME 類型：{mime_type}",
            )

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
        if count <= 0:
            raise_error(ErrorCode.INVALID_REQUEST, "至少需要上傳一個檔案")

        if count > self.max_files:
            raise_error(
                ErrorCode.INVALID_REQUEST,
                f"超過最大檔案數量限制（{count} > {self.max_files}）",
            )

        return True
