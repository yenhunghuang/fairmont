"""API client for communicating with FastAPI backend."""

import httpx
import json
import logging
import os
import time
from typing import Dict, Any, List, Callable, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class APIClient:
    """Synchronous client for interacting with the backend API."""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None):
        """
        Initialize API client.

        Args:
            base_url: Backend API base URL
            api_key: API key for authentication (optional, reads from env if not provided)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("API_KEY", "")
        self.client = httpx.Client(timeout=600)  # 增加 timeout 以支援長時間處理

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
            response = self.client.get(f"{self.base_url}/api/v1/health")
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
                f"{self.base_url}/api/v1/documents",
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
            response = self.client.get(f"{self.base_url}/api/v1/tasks/{task_id}")
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
            response = self.client.get(f"{self.base_url}/api/v1/documents")
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
            response = self.client.get(f"{self.base_url}/api/v1/documents/{document_id}")
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
                f"{self.base_url}/api/v1/documents/{document_id}/parsing",
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
                f"{self.base_url}/api/v1/documents/{document_id}/parse-result"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get parse result: {e}")
            raise

    def create_quotation(self, document_ids: List[str]) -> Dict[str, Any]:
        """
        Create quotation from documents (simple merge without quantity summary).

        Args:
            document_ids: List of document IDs to include

        Returns:
            Created quotation information

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/quotations",
                json={"document_ids": document_ids},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create quotation: {e}")
            raise

    def create_merged_quotation(
        self,
        document_ids: List[str],
        title: str | None = None,
        max_wait: int = 120,
        poll_interval: int = 2,
    ) -> Dict[str, Any]:
        """
        Create quotation with cross-document merge (uses quantity summary).

        This endpoint automatically:
        - Detects quantity summary vs detail spec documents
        - Merges quantities from summary into detail items
        - Selects highest resolution images

        Args:
            document_ids: List of document IDs to include
            title: Optional quotation title
            max_wait: Maximum wait time for merge completion
            poll_interval: Poll interval in seconds

        Returns:
            Created quotation information with merge report

        Raises:
            httpx.HTTPError: If request fails
            TimeoutError: If merge takes too long
        """
        try:
            # Start merge
            payload = {"document_ids": document_ids}
            if title:
                payload["title"] = title

            response = self.client.post(
                f"{self.base_url}/api/v1/quotations/merge",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            # If merge is async (202), wait for completion
            if response.status_code == 202:
                task_id = result.get("data", {}).get("task_id")
                quotation_id = result.get("data", {}).get("quotation_id")

                if task_id:
                    # Wait for task completion
                    task_result = self.wait_for_completion(task_id, max_wait, poll_interval)
                    task_status = task_result.get("data", {}).get("status")

                    if task_status == "completed":
                        # Return quotation info
                        return {
                            "success": True,
                            "message": "跨表合併完成",
                            "data": {"id": quotation_id},
                        }
                    else:
                        error = task_result.get("data", {}).get("error", "合併失敗")
                        return {
                            "success": False,
                            "message": error,
                            "data": None,
                        }

            return result

        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Failed to create merged quotation: {e}")
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
                    f"{self.base_url}/api/v1/quotations/{quotation_id}/excel",
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
                f"{self.base_url}/api/v1/tasks",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            raise

    def process_files(
        self,
        files: List[tuple[str, bytes]] | List[Path],
        extract_images: bool = True,
    ) -> Dict[str, Any]:
        """
        使用單一 API 端點處理 PDF 檔案並直接返回 17 欄 JSON 結果。

        這是新的整合 API，上傳 PDF 後直接返回解析結果，無需多步驟操作。
        返回結果包含 project_name 與 items 列表。

        每個 item 包含 17 個欄位：
        - 原有 15 欄：no, item_no, description, photo, dimension, qty, uom,
                     unit_rate, amount, unit_cbm, total_cbm, note, location,
                     materials_specs, brand
        - 新增 2 欄：category (1=家具, 5=面料), affiliate (面料來源家具編號)

        Args:
            files: List of (filename, content) tuples or file paths to upload
            extract_images: Whether to extract images during parsing

        Returns:
            處理結果:
            {
                "success": True,
                "data": {
                    "project_name": "SOLAIRE BAY TOWER",
                    "items": [
                        {
                            "no": 1,
                            "item_no": "DLX-101",
                            "description": "King Bed",
                            "category": 1,
                            "affiliate": null,
                            ...
                        },
                        ...
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
                    with open(item, "rb") as f:
                        content = f.read()
                    file_list.append(("files", (item.name, content, "application/pdf")))
                else:
                    filename, content = item
                    file_list.append(("files", (filename, content, "application/pdf")))

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = self.client.post(
                f"{self.base_url}/api/v1/process",
                files=file_list,
                params={"extract_images": extract_images},
                headers=headers,
            )
            response.raise_for_status()

            # API 返回 {project_name, items} 結構
            result = response.json()
            items = result.get("items", [])
            project_name = result.get("project_name")
            return {
                "success": True,
                "data": result,
                "message": f"成功處理 {len(items)} 個項目" + (f" (專案: {project_name})" if project_name else ""),
            }

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_json = e.response.json()
                error_detail = error_json.get("message", str(e))
            except Exception:
                error_detail = str(e)
            logger.error(f"Process files failed: {error_detail}")
            return {
                "success": False,
                "data": None,
                "message": error_detail,
            }
        except Exception as e:
            logger.error(f"Process files failed: {e}")
            return {
                "success": False,
                "data": None,
                "message": str(e),
            }

    def process_files_stream(
        self,
        files: List[tuple[str, bytes]] | List[Path],
        extract_images: bool = True,
        on_progress: Optional[Callable[[dict], None]] = None,
        on_result: Optional[Callable[[dict], None]] = None,
        on_error: Optional[Callable[[dict], None]] = None,
    ) -> Dict[str, Any]:
        """
        使用 SSE 串流方式處理 PDF 檔案，支援即時進度更新。

        這是 process_files 的串流版本，透過回調函數提供即時進度。

        **SSE 事件類型**：
        - `progress`: 進度更新 {stage, progress, message, detail?}
        - `result`: 處理完成 {project_name, items[], statistics}
        - `error`: 錯誤 {code, message, stage?}

        **進度階段 (stage)**:
        - validating (0-5%): 檔案驗證
        - detecting_roles (5-10%): 文件角色偵測
        - parsing_detail_specs (10-70%): 明細規格表解析
        - parsing_quantity_summary (70-85%): 數量總表解析
        - merging (85-95%): 跨表合併
        - converting (95-99%): 格式轉換
        - completed (100%): 完成

        Args:
            files: List of (filename, content) tuples or file paths to upload
            extract_images: Whether to extract images during parsing
            on_progress: 進度回調函數，接收 {stage, progress, message, detail} dict
            on_result: 結果回調函數，接收 {project_name, items, statistics} dict
            on_error: 錯誤回調函數，接收 {code, message, stage} dict

        Returns:
            處理結果（如果成功）或錯誤訊息:
            {
                "success": True/False,
                "data": {project_name, items, statistics} 或 None,
                "message": str
            }

        Example:
            ```python
            def handle_progress(data):
                print(f"{data['progress']}% - {data['message']}")

            def handle_result(data):
                print(f"完成！共 {len(data['items'])} 個項目")

            def handle_error(data):
                print(f"錯誤：{data['message']}")

            result = client.process_files_stream(
                files=[("test.pdf", pdf_content)],
                on_progress=handle_progress,
                on_result=handle_result,
                on_error=handle_error,
            )
            ```
        """
        try:
            file_list = []

            for item in files:
                if isinstance(item, Path):
                    with open(item, "rb") as f:
                        content = f.read()
                    file_list.append(("files", (item.name, content, "application/pdf")))
                else:
                    filename, content = item
                    file_list.append(("files", (filename, content, "application/pdf")))

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # 使用 stream 參數以支援 SSE
            with self.client.stream(
                "POST",
                f"{self.base_url}/api/v1/process/stream",
                files=file_list,
                params={"extract_images": extract_images},
                headers=headers,
            ) as response:
                response.raise_for_status()

                result_data = None
                error_data = None
                event_type = None

                # 解析 SSE 事件
                for line in response.iter_lines():
                    if not line:
                        continue

                    # SSE 格式：event: <type>\ndata: <json>\n\n
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                        continue
                    elif line.startswith("data:") and event_type:
                        data_str = line.split(":", 1)[1].strip()
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in SSE data: {data_str}")
                            continue

                        # 根據事件類型處理
                        if event_type == "progress" and on_progress:
                            on_progress(data)
                        elif event_type == "result":
                            result_data = data
                            if on_result:
                                on_result(data)
                        elif event_type == "error":
                            error_data = data
                            if on_error:
                                on_error(data)

                        # 重置事件類型
                        event_type = None

                # 返回最終結果
                if result_data:
                    return {
                        "success": True,
                        "data": result_data,
                        "message": f"成功處理 {len(result_data.get('items', []))} 個項目",
                    }
                elif error_data:
                    return {
                        "success": False,
                        "data": None,
                        "message": error_data.get("message", "處理失敗"),
                    }
                else:
                    return {
                        "success": False,
                        "data": None,
                        "message": "未收到處理結果",
                    }

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_json = e.response.json()
                error_detail = error_json.get("message", str(e))
            except Exception:
                error_detail = str(e)
            logger.error(f"Process files stream failed: {error_detail}")
            if on_error:
                on_error({"code": "HTTP_ERROR", "message": error_detail})
            return {
                "success": False,
                "data": None,
                "message": error_detail,
            }
        except Exception as e:
            logger.error(f"Process files stream failed: {e}")
            if on_error:
                on_error({"code": "UNKNOWN_ERROR", "message": str(e)})
            return {
                "success": False,
                "data": None,
                "message": str(e),
            }
