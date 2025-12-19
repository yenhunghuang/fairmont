"""API client for communicating with FastAPI backend."""

import httpx
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import asyncio


logger = logging.getLogger(__name__)


class APIClient:
    """Client for interacting with the backend API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize API client.

        Args:
            base_url: Backend API base URL
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=300)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        """
        Check backend health.

        Returns:
            Health check response

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise

    async def upload_files(self, files: List[Path]) -> Dict[str, Any]:
        """
        Upload PDF files.

        Args:
            files: List of file paths to upload

        Returns:
            Upload response with document IDs

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            file_list = []
            for file_path in files:
                with open(file_path, "rb") as f:
                    file_list.append(("files", (file_path.name, f, "application/pdf")))

            response = await self.client.post(
                f"{self.base_url}/api/upload",
                files=file_list,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
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
            response = await self.client.get(f"{self.base_url}/api/task/{task_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            raise

    async def wait_for_completion(
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
                status = await self.get_task_status(task_id)
                if status.get("data", {}).get("status") in ["completed", "failed"]:
                    return status
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            except Exception as e:
                logger.error(f"Error while waiting for task: {e}")
                raise

        raise TimeoutError(f"Task {task_id} did not complete within {max_wait} seconds")

    async def list_documents(self) -> Dict[str, Any]:
        """
        List all uploaded documents.

        Returns:
            List of documents

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/documents")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    async def get_document(self, document_id: str) -> Dict[str, Any]:
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
            response = await self.client.get(f"{self.base_url}/api/documents/{document_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            raise

    async def create_quotation(self, document_ids: List[str]) -> Dict[str, Any]:
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
            response = await self.client.post(
                f"{self.base_url}/api/quotation",
                json={"source_document_ids": document_ids},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create quotation: {e}")
            raise

    async def export_excel(self, quotation_id: str) -> Dict[str, Any]:
        """
        Export quotation to Excel.

        Args:
            quotation_id: Quotation ID to export

        Returns:
            Export status and download URL

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/export/{quotation_id}/excel"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to export Excel: {e}")
            raise

    async def download_excel(self, quotation_id: str) -> bytes:
        """
        Download Excel file.

        Args:
            quotation_id: Quotation ID to download

        Returns:
            Excel file content as bytes

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/api/export/{quotation_id}/download"
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download Excel: {e}")
            raise
