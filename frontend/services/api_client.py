"""API client for communicating with FastAPI backend."""

import httpx
import logging
import time
from typing import Dict, Any, List
from pathlib import Path


logger = logging.getLogger(__name__)


class APIClient:
    """Synchronous client for interacting with the backend API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize API client.

        Args:
            base_url: Backend API base URL
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=300)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def health_check(self) -> Dict[str, Any]:
        """
        Check backend health.

        Returns:
            Health check response

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    def upload_files(
        self,
        files: List[tuple[str, bytes]] | List[Path],
        extract_images: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload PDF files with automatic parsing.

        後端 API 已整合自動解析功能，上傳後會自動啟動解析任務。
        返回結果包含 documents 和 parse_tasks。

        Args:
            files: List of (filename, content) tuples or file paths to upload
            extract_images: Whether to extract images during parsing

        Returns:
            Upload response with document IDs and parse task IDs:
            {
                "success": True,
                "data": {
                    "documents": [...],
                    "parse_tasks": [
                        {"document_id": "...", "task_id": "...", "status": "..."}
                    ]
                }
            }

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            file_list = []

            for item in files:
                if isinstance(item, Path):
                    # Handle Path objects
                    with open(item, "rb") as f:
                        content = f.read()
                    file_list.append(("files", (item.name, content, "application/pdf")))
                else:
                    # Handle (filename, content) tuples
                    filename, content = item
                    file_list.append(("files", (filename, content, "application/pdf")))

            response = self.client.post(
                f"{self.base_url}/api/documents",
                files=file_list,
                params={"extract_images": extract_images},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get processing task status.

        Args:
            task_id: Task ID to check

        Returns:
            Task status information

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/api/tasks/{task_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            raise

    def wait_for_completion(
        self, task_id: str, max_wait: int = 300, poll_interval: int = 2
    ) -> Dict[str, Any]:
        """
        Wait for task to complete.

        Args:
            task_id: Task ID to wait for
            max_wait: Maximum wait time in seconds
            poll_interval: Poll interval in seconds

        Returns:
            Final task status

        Raises:
            TimeoutError: If task takes too long
            httpx.HTTPError: If request fails
        """
        elapsed = 0
        while elapsed < max_wait:
            try:
                status = self.get_task_status(task_id)
                if status.get("data", {}).get("status") in ["completed", "failed"]:
                    return status
                time.sleep(poll_interval)
                elapsed += poll_interval
            except Exception as e:
                logger.error(f"Error while waiting for task: {e}")
                raise

        raise TimeoutError(f"Task {task_id} did not complete within {max_wait} seconds")

    def list_documents(self) -> Dict[str, Any]:
        """
        List all uploaded documents.

        Returns:
            List of documents

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/api/documents")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get document details.

        Args:
            document_id: Document ID

        Returns:
            Document details

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/api/documents/{document_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            raise

    def parse_document(
        self, document_id: str, extract_images: bool = True
    ) -> Dict[str, Any]:
        """
        Start parsing a document.

        Args:
            document_id: Document ID to parse
            extract_images: Whether to extract images

        Returns:
            Task information with task_id

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.post(
                f"{self.base_url}/api/documents/{document_id}/parsing",
                json={"extract_images": extract_images},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to start parsing: {e}")
            raise

    def get_parse_result(self, document_id: str) -> Dict[str, Any]:
        """
        Get parsing result for a document.

        Args:
            document_id: Document ID

        Returns:
            Parse result with BOQ items

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(
                f"{self.base_url}/api/documents/{document_id}/parse-result"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get parse result: {e}")
            raise

    def create_quotation(self, document_ids: List[str]) -> Dict[str, Any]:
        """
        Create quotation from documents.

        Args:
            document_ids: List of document IDs to include

        Returns:
            Created quotation information

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.post(
                f"{self.base_url}/api/quotations",
                json={"document_ids": document_ids},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create quotation: {e}")
            raise

    def get_quotation_excel(
        self,
        quotation_id: str,
        include_photos: bool = True,
        photo_height_cm: float = 3.0,
        max_wait: int = 300,
        poll_interval: int = 2,
    ) -> bytes:
        """
        Get quotation Excel file with automatic polling.

        This method handles both immediate download (if Excel is ready) and
        automatic polling (if Excel generation is in progress).

        Args:
            quotation_id: Quotation ID to export
            include_photos: Whether to include photos in Excel
            photo_height_cm: Photo height in centimeters
            max_wait: Maximum wait time in seconds for generation
            poll_interval: Poll interval in seconds when waiting

        Returns:
            Excel file content as bytes

        Raises:
            TimeoutError: If generation takes too long
            httpx.HTTPError: If request fails
        """
        try:
            params = {
                "include_photos": include_photos,
                "photo_height_cm": photo_height_cm,
            }

            elapsed = 0
            while elapsed < max_wait:
                response = self.client.get(
                    f"{self.base_url}/api/quotations/{quotation_id}/excel",
                    params=params,
                )

                # If ready, return the Excel file
                if response.status_code == 200:
                    return response.content

                # If still generating, wait and retry
                if response.status_code == 202:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    continue

                # Other status codes
                response.raise_for_status()

            raise TimeoutError(
                f"Excel generation for quotation {quotation_id} did not complete within {max_wait} seconds"
            )

        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Failed to get quotation Excel: {e}")
            raise

    def list_tasks(
        self, limit: int = 20, status: str | None = None
    ) -> Dict[str, Any]:
        """
        List processing tasks.

        Args:
            limit: Maximum number of tasks to return
            status: Filter by task status (pending, processing, completed, failed)

        Returns:
            List of tasks with metadata

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            params = {"limit": limit}
            if status is not None:
                params["status"] = status

            response = self.client.get(
                f"{self.base_url}/api/tasks",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            raise

    def check_sheets_status(self) -> Dict[str, Any]:
        """
        Check Google Sheets integration status.

        Returns:
            Status information including enabled and available flags

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(f"{self.base_url}/api/v1/sheets/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to check Sheets status: {e}")
            raise

    def export_to_google_sheets(
        self,
        quotation_id: str,
        include_photos: bool = True,
        share_mode: str = "view",
        max_wait: int = 300,
        poll_interval: int = 3,
    ) -> Dict[str, Any]:
        """
        Export quotation to Google Sheets with automatic polling.

        Args:
            quotation_id: Quotation ID to export
            include_photos: Whether to upload photos to Google Drive
            share_mode: "view" for read-only, "edit" for editable
            max_wait: Maximum wait time in seconds
            poll_interval: Poll interval in seconds

        Returns:
            Result with spreadsheet_url and shareable_link

        Raises:
            TimeoutError: If generation takes too long
            httpx.HTTPError: If request fails
        """
        try:
            # Start export
            response = self.client.post(
                f"{self.base_url}/api/v1/quotations/{quotation_id}/sheets",
                json={
                    "include_photos": include_photos,
                    "share_mode": share_mode,
                },
            )

            # If already completed (200), return directly
            if response.status_code == 200:
                return response.json()

            # If accepted (202), poll for completion
            if response.status_code == 202:
                data = response.json().get("data", {})
                task_id = data.get("task_id")

                if task_id:
                    # Wait for task completion
                    result = self.wait_for_completion(task_id, max_wait, poll_interval)
                    return result
                else:
                    # No task ID, poll the sheets endpoint
                    return self._poll_sheets_completion(
                        quotation_id, max_wait, poll_interval
                    )

            response.raise_for_status()
            return response.json()

        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Failed to export to Google Sheets: {e}")
            raise

    def _poll_sheets_completion(
        self,
        quotation_id: str,
        max_wait: int = 300,
        poll_interval: int = 3,
    ) -> Dict[str, Any]:
        """
        Poll for Google Sheets completion.

        Args:
            quotation_id: Quotation ID
            max_wait: Maximum wait time in seconds
            poll_interval: Poll interval in seconds

        Returns:
            Sheets result

        Raises:
            TimeoutError: If takes too long
        """
        elapsed = 0
        while elapsed < max_wait:
            response = self.client.get(
                f"{self.base_url}/api/v1/quotations/{quotation_id}/sheets"
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("data", {}).get("status") == "completed":
                    return result

            time.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(
            f"Google Sheets generation for quotation {quotation_id} "
            f"did not complete within {max_wait} seconds"
        )

    def get_google_sheets_link(self, quotation_id: str) -> Dict[str, Any]:
        """
        Get existing Google Sheets link for quotation.

        Args:
            quotation_id: Quotation ID

        Returns:
            Sheets link information

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.get(
                f"{self.base_url}/api/v1/quotations/{quotation_id}/sheets"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get Google Sheets link: {e}")
            raise
