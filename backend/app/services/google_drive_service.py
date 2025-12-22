"""Google Drive service for uploading images with public sharing.

Handles image uploads to Google Drive with public link permissions
for use with Google Sheets IMAGE() function.
"""

import logging
import base64
import time
from pathlib import Path
from typing import Optional
from io import BytesIO

from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

from ..config import settings
from ..utils import ErrorCode, raise_error

logger = logging.getLogger(__name__)

# Google API scopes required
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",  # Create and manage files
]


class GoogleDriveService:
    """Service for uploading images to Google Drive with public sharing."""

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds

    def __init__(self):
        """Initialize Google Drive service with Service Account credentials."""
        self._service: Optional[Resource] = None

    def _get_service(self) -> Resource:
        """Get or create Drive API service instance."""
        if self._service is None:
            self._service = self._authenticate()
        return self._service

    def _authenticate(self) -> Resource:
        """Authenticate using Service Account JSON."""
        try:
            creds_path = settings.google_credentials_path_resolved
            if not creds_path or not creds_path.exists():
                raise_error(
                    ErrorCode.GOOGLE_AUTH_FAILED,
                    "找不到 Google 服務帳號憑證檔案",
                    status_code=500,
                )

            credentials = service_account.Credentials.from_service_account_file(
                str(creds_path),
                scopes=SCOPES,
            )

            service = build("drive", "v3", credentials=credentials)
            logger.info("Google Drive API authenticated successfully")
            return service

        except Exception as e:
            if "GOOGLE_AUTH_FAILED" in str(e):
                raise
            logger.error(f"Google Drive authentication failed: {e}")
            raise_error(
                ErrorCode.GOOGLE_AUTH_FAILED,
                f"Google Drive API 認證失敗：{str(e)}",
                status_code=500,
            )

    def _execute_with_retry(self, request):
        """Execute API request with exponential backoff."""
        for attempt in range(self.MAX_RETRIES):
            try:
                return request.execute()
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {delay}s before retry")
                    time.sleep(delay)
                elif e.resp.status == 403:  # Quota exceeded
                    raise_error(
                        ErrorCode.GOOGLE_QUOTA_EXCEEDED,
                        "Google API 配額已用盡，請稍後重試",
                        status_code=503,
                    )
                else:
                    raise
        raise_error(
            ErrorCode.GOOGLE_API_ERROR,
            "Google Drive API 請求失敗",
            status_code=500,
        )

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """
        Create folder for quotation images.

        Args:
            folder_name: Name of the folder to create
            parent_id: Optional parent folder ID

        Returns:
            Folder ID
        """
        try:
            service = self._get_service()

            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }

            if parent_id:
                file_metadata["parents"] = [parent_id]
            elif settings.google_drive_folder_id:
                file_metadata["parents"] = [settings.google_drive_folder_id]

            folder = self._execute_with_retry(
                service.files().create(
                    body=file_metadata,
                    fields="id",
                )
            )

            folder_id = folder.get("id")
            logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")

            # Set folder to public view
            self.set_public_access(folder_id)

            return folder_id

        except Exception as e:
            if any(code in str(e) for code in ["GOOGLE_AUTH_FAILED", "GOOGLE_QUOTA_EXCEEDED", "GOOGLE_API_ERROR"]):
                raise
            logger.error(f"Failed to create folder: {e}")
            raise_error(
                ErrorCode.GOOGLE_API_ERROR,
                f"建立 Google Drive 資料夾失敗：{str(e)}",
                status_code=500,
            )

    def upload_image(
        self,
        image_data: bytes,
        filename: str,
        folder_id: str,
        mime_type: str = "image/png",
    ) -> Optional[str]:
        """
        Upload image to Google Drive and return public URL.

        Args:
            image_data: Image bytes
            filename: Name for the file
            folder_id: Folder ID to upload to
            mime_type: MIME type of the image

        Returns:
            Public URL for IMAGE() function, or None on failure
        """
        try:
            service = self._get_service()

            file_metadata = {
                "name": filename,
                "parents": [folder_id],
            }

            media = MediaIoBaseUpload(
                BytesIO(image_data),
                mimetype=mime_type,
                resumable=True,
            )

            file = self._execute_with_retry(
                service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id",
                )
            )

            file_id = file.get("id")
            logger.info(f"Uploaded image '{filename}' with ID: {file_id}")

            # Set public access
            self.set_public_access(file_id)

            # Return direct view URL for IMAGE() function
            return self.get_image_url(file_id)

        except Exception as e:
            if any(code in str(e) for code in ["GOOGLE_AUTH_FAILED", "GOOGLE_QUOTA_EXCEEDED", "GOOGLE_API_ERROR"]):
                raise
            logger.warning(f"Failed to upload image '{filename}': {e}")
            return None  # Continue without image rather than failing

    def upload_base64_image(
        self,
        base64_data: str,
        filename: str,
        folder_id: str,
    ) -> Optional[str]:
        """
        Upload Base64 encoded image to Google Drive.

        Args:
            base64_data: Base64 encoded image data (may include data URI prefix)
            filename: Name for the file
            folder_id: Folder ID to upload to

        Returns:
            Public URL for IMAGE() function, or None on failure
        """
        try:
            # Remove data URI prefix if present
            if base64_data.startswith("data:"):
                header, base64_data = base64_data.split(",", 1)
                # Extract MIME type from header
                if "png" in header.lower():
                    mime_type = "image/png"
                elif "jpg" in header.lower() or "jpeg" in header.lower():
                    mime_type = "image/jpeg"
                elif "gif" in header.lower():
                    mime_type = "image/gif"
                else:
                    mime_type = "image/png"
            else:
                mime_type = "image/png"

            # Decode Base64 to bytes
            image_bytes = base64.b64decode(base64_data)

            return self.upload_image(image_bytes, filename, folder_id, mime_type)

        except Exception as e:
            logger.warning(f"Failed to decode/upload Base64 image '{filename}': {e}")
            return None

    def set_public_access(self, file_id: str) -> None:
        """
        Set 'anyone with link' viewer permission.

        Args:
            file_id: Google Drive file/folder ID
        """
        try:
            service = self._get_service()

            permission = {
                "type": "anyone",
                "role": "reader",
            }

            self._execute_with_retry(
                service.permissions().create(
                    fileId=file_id,
                    body=permission,
                    fields="id",
                )
            )

            logger.debug(f"Set public access for file: {file_id}")

        except Exception as e:
            logger.warning(f"Failed to set public access for {file_id}: {e}")
            # Don't raise - image can still work if permission fails

    def get_image_url(self, file_id: str) -> str:
        """
        Get direct image URL for Google Sheets IMAGE() function.

        Args:
            file_id: Google Drive file ID

        Returns:
            Direct view URL
        """
        # This URL format works with Google Sheets IMAGE() function
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    def delete_folder(self, folder_id: str) -> bool:
        """
        Delete folder and its contents (cleanup).

        Args:
            folder_id: Folder ID to delete

        Returns:
            True if successful
        """
        try:
            service = self._get_service()

            self._execute_with_retry(
                service.files().delete(fileId=folder_id)
            )

            logger.info(f"Deleted folder: {folder_id}")
            return True

        except Exception as e:
            logger.warning(f"Failed to delete folder {folder_id}: {e}")
            return False


# Global service instance
_service_instance: Optional[GoogleDriveService] = None


def get_google_drive_service() -> GoogleDriveService:
    """Get or create Google Drive service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = GoogleDriveService()
    return _service_instance
