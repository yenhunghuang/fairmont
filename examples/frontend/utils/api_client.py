"""
API 客戶端工具 - 用於 Streamlit 呼叫 FastAPI 後端

提供：
1. 統一的 API 呼叫介面
2. 錯誤處理
3. 重試機制
4. 超時控制
"""

import requests
import streamlit as st
from typing import Optional, Dict, Any
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIClient:
    """FastAPI 後端 API 客戶端"""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        初始化 API 客戶端

        Args:
            base_url: FastAPI 後端的基礎 URL
            timeout: 請求超時時間（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """建立具有重試機制的 Session"""
        session = requests.Session()

        # 設定重試策略
        retry_strategy = Retry(
            total=3,  # 最多重試 3 次
            backoff_factor=1,  # 重試間隔倍數
            status_forcelist=[429, 500, 502, 503, 504],  # 這些狀態碼會觸發重試
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """處理 API 回應"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # 嘗試從回應中取得錯誤訊息
            try:
                error_data = response.json()
                error_msg = error_data.get('message', str(e))
            except:
                error_msg = str(e)
            raise APIError(f"API 錯誤: {error_msg}", status_code=response.status_code)
        except requests.exceptions.JSONDecodeError:
            raise APIError("無法解析 API 回應")
        except Exception as e:
            raise APIError(f"請求失敗: {str(e)}")

    def health_check(self) -> bool:
        """檢查後端服務是否正常運行"""
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            return response.status_code == 200
        except:
            return False

    def upload_file(self, file_data, filename: str) -> Dict[str, Any]:
        """
        上傳檔案到後端

        Args:
            file_data: 檔案資料（bytes 或 file-like object）
            filename: 檔案名稱

        Returns:
            包含 task_id 的回應
        """
        try:
            files = {'file': (filename, file_data)}
            response = self.session.post(
                f"{self.base_url}/api/upload",
                files=files,
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            raise APIError(f"檔案上傳失敗: {str(e)}")

    def create_process_task(self, data: str, delay: int = 5) -> Dict[str, Any]:
        """
        建立處理任務

        Args:
            data: 要處理的資料
            delay: 處理延遲時間（秒）

        Returns:
            包含 task_id 的回應
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/process",
                json={"data": data, "delay": delay},
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            raise APIError(f"任務建立失敗: {str(e)}")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        取得任務狀態

        Args:
            task_id: 任務 ID

        Returns:
            任務狀態資料
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/task/{task_id}",
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            raise APIError(f"無法取得任務狀態: {str(e)}")

    def list_tasks(self, limit: int = 10) -> list:
        """
        列出所有任務

        Args:
            limit: 最多顯示筆數

        Returns:
            任務列表
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/tasks",
                params={"limit": limit},
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            raise APIError(f"無法取得任務列表: {str(e)}")

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """
        刪除任務

        Args:
            task_id: 任務 ID

        Returns:
            刪除確認訊息
        """
        try:
            response = self.session.delete(
                f"{self.base_url}/api/task/{task_id}",
                timeout=self.timeout
            )
            return self._handle_response(response)
        except Exception as e:
            raise APIError(f"無法刪除任務: {str(e)}")

    def wait_for_task(
        self,
        task_id: str,
        progress_callback=None,
        poll_interval: float = 0.5,
        max_wait: int = 300
    ) -> Dict[str, Any]:
        """
        等待任務完成（適用於同步場景）

        Args:
            task_id: 任務 ID
            progress_callback: 進度回調函數，接收 (progress, message) 參數
            poll_interval: 輪詢間隔（秒）
            max_wait: 最長等待時間（秒）

        Returns:
            完成的任務狀態
        """
        start_time = time.time()

        while True:
            # 檢查超時
            if time.time() - start_time > max_wait:
                raise APIError("任務處理超時")

            # 取得任務狀態
            status = self.get_task_status(task_id)

            # 呼叫進度回調
            if progress_callback:
                progress_callback(status.get('progress', 0), status.get('message', ''))

            # 檢查任務是否完成
            if status['status'] == 'completed':
                return status
            elif status['status'] == 'failed':
                error_msg = status.get('error', '未知錯誤')
                raise APIError(f"任務執行失敗: {error_msg}")

            # 等待後再次輪詢
            time.sleep(poll_interval)


class APIError(Exception):
    """API 錯誤例外"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ==================== Streamlit 專用輔助函數 ====================

@st.cache_resource
def get_api_client(base_url: str = "http://localhost:8000") -> APIClient:
    """
    取得 API 客戶端（使用 Streamlit 快取）

    這樣可以在整個 Streamlit 應用程式中重複使用同一個 Session
    """
    return APIClient(base_url)


def display_task_progress(api_client: APIClient, task_id: str, container=None):
    """
    在 Streamlit 中顯示任務進度

    Args:
        api_client: API 客戶端
        task_id: 任務 ID
        container: Streamlit 容器（可選）

    Returns:
        完成的任務狀態
    """
    if container is None:
        container = st

    progress_bar = container.progress(0)
    status_text = container.empty()

    try:
        def update_progress(progress: int, message: str):
            progress_bar.progress(progress / 100)
            status_text.text(message)

        result = api_client.wait_for_task(task_id, progress_callback=update_progress)

        progress_bar.progress(100)
        status_text.success("處理完成！")

        return result

    except APIError as e:
        status_text.error(f"錯誤: {e.message}")
        raise
    finally:
        time.sleep(0.5)  # 讓使用者看到完成狀態


def check_backend_connection(api_client: APIClient) -> bool:
    """
    檢查後端連線並在 Streamlit 中顯示狀態

    Returns:
        True 如果連線成功，否則 False
    """
    if api_client.health_check():
        st.success("後端服務連線正常")
        return True
    else:
        st.error("無法連接到後端服務，請確認 FastAPI 伺服器是否正在運行")
        st.info(f"後端 URL: {api_client.base_url}")
        return False
