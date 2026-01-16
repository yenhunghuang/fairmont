"""File management utilities."""

from pathlib import Path
from typing import Optional
import logging

from .errors import ErrorCode, raise_error


logger = logging.getLogger(__name__)


class FileManager:
    """Manages temporary file storage and cleanup."""

    def __init__(self, temp_dir: Path, images_dir: Path):
        """
        Initialize FileManager.

        Args:
            temp_dir: Path to temporary files directory
            images_dir: Path to extracted images directory
        """
        self.temp_dir = Path(temp_dir)
        self.images_dir = Path(images_dir)

        # Create directories if they don't exist
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def save_upload_file(self, file_content: bytes, filename: str) -> str:
        """
        Save uploaded file to temp directory.

        Args:
            file_content: File content as bytes
            filename: Original filename

        Returns:
            Path to saved file

        Raises:
            APIError: If file save fails
        """
        try:
            file_path = self.temp_dir / filename
            file_path.write_bytes(file_content)
            logger.info(f"File saved: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise_error(
                ErrorCode.FILE_UPLOAD_FAILED,
                f"檔案保存失敗：{str(e)}",
            )

    def save_extracted_image(
        self,
        image_content: bytes,
        filename: str,
        document_id: Optional[str] = None,
    ) -> str:
        """
        Save extracted image to images directory.

        Args:
            image_content: Image content as bytes
            filename: Image filename
            document_id: Optional document ID to create subdirectory

        Returns:
            Path to saved image

        Raises:
            APIError: If image save fails
        """
        try:
            # Create subdirectory for document if document_id provided
            if document_id:
                target_dir = self.images_dir / document_id
                target_dir.mkdir(parents=True, exist_ok=True)
            else:
                target_dir = self.images_dir

            image_path = target_dir / filename
            image_path.write_bytes(image_content)
            logger.info(f"Image saved: {image_path}")
            return str(image_path)
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            raise_error(
                ErrorCode.FILE_UPLOAD_FAILED,
                f"圖片保存失敗：{str(e)}",
            )

    def delete_file(self, file_path: str) -> None:
        """
        Delete a file.

        Args:
            file_path: Path to file to delete

        Raises:
            APIError: If file deletion fails
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"File deleted: {file_path}")
            else:
                logger.warning(f"File not found for deletion: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise_error(
                ErrorCode.FILE_DELETION_FAILED,
                f"檔案刪除失敗：{str(e)}",
            )

    def cleanup_temp_files(self, days: int = 7) -> int:
        """
        Clean up temporary files older than specified days.

        Args:
            days: Number of days (delete files older than this)

        Returns:
            Number of files deleted
        """
        import time
        deleted_count = 0
        cutoff_time = time.time() - (days * 86400)

        try:
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Cleaned up old temp file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

        return deleted_count

    def get_file_size(self, file_path: str) -> int:
        """
        Get file size in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size in bytes

        Raises:
            APIError: If file not found
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise_error(ErrorCode.FILE_NOT_FOUND, "檔案不存在")
            return path.stat().st_size
        except Exception as e:
            if isinstance(e, Exception) and "找不到" in str(e):
                raise
            logger.error(f"Failed to get file size: {e}")
            raise_error(ErrorCode.FILE_NOT_FOUND, "無法取得檔案資訊")

    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists.

        Args:
            file_path: Path to file

        Returns:
            True if file exists, False otherwise
        """
        return Path(file_path).exists()
