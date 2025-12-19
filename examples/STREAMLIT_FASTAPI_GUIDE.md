# Streamlit 與 FastAPI 整合最佳實踐指南

完整的 Streamlit 前端與 FastAPI 後端整合範例，涵蓋檔案上傳、長時間任務處理、進度追蹤、多頁面架構、Session State 管理與錯誤處理。

**建立日期**：2025-12-19
**適用版本**：Python 3.11+, Streamlit 1.31+, FastAPI 0.109+

---

## 目錄

1. [專案概述](#專案概述)
2. [目錄結構](#目錄結構)
3. [快速開始](#快速開始)
4. [核心功能詳解](#核心功能詳解)
5. [最佳實踐](#最佳實踐)
6. [常見問題](#常見問題)
7. [進階應用](#進階應用)

---

## 專案概述

本範例展示了如何建立一個生產級的 Streamlit + FastAPI 應用程式，包含：

### 後端（FastAPI）
- RESTful API 設計
- 檔案上傳處理
- 背景任務執行（Background Tasks）
- 任務狀態追蹤
- 統一的錯誤處理
- CORS 設定

### 前端（Streamlit）
- 多頁面應用程式架構
- API 客戶端封裝
- 檔案上傳與進度顯示
- 長時間任務處理與即時進度追蹤
- Session State 統一管理
- 繁體中文錯誤訊息

---

## 目錄結構

```
examples/
├── backend/                      # FastAPI 後端
│   ├── main.py                  # 主應用程式
│   ├── .env.example             # 環境變數範例
│   └── uploads/                 # 上傳檔案暫存目錄（自動建立）
│
├── frontend/                     # Streamlit 前端
│   ├── app.py                   # 主應用程式
│   ├── pages/                   # 頁面模組
│   │   ├── __init__.py
│   │   ├── home.py              # 首頁
│   │   ├── file_upload.py       # 檔案上傳頁面
│   │   ├── long_task.py         # 長時間任務頁面
│   │   ├── task_management.py   # 任務管理頁面
│   │   └── settings.py          # 設定頁面
│   │
│   ├── utils/                   # 工具模組
│   │   ├── __init__.py
│   │   ├── api_client.py        # API 客戶端
│   │   ├── session_state.py     # Session State 管理
│   │   └── error_handler.py     # 錯誤處理
│   │
│   └── .streamlit/              # Streamlit 設定
│       └── config.toml          # 應用程式設定
│
├── requirements.txt              # Python 依賴套件
├── run_backend.bat              # 啟動後端（Windows）
├── run_frontend.bat             # 啟動前端（Windows）
└── STREAMLIT_FASTAPI_GUIDE.md   # 本檔案
```

---

## 快速開始

### 1. 安裝依賴套件

```bash
# 建議使用虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安裝依賴
pip install -r requirements.txt
```

### 2. 啟動後端服務

**方法 A：使用批次檔（Windows）**
```bash
run_backend.bat
```

**方法 B：手動啟動**
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

後端會在 `http://localhost:8000` 啟動，可訪問：
- API 文件：http://localhost:8000/docs
- 健康檢查：http://localhost:8000/

### 3. 啟動前端應用程式

**開啟新的終端機**

**方法 A：使用批次檔（Windows）**
```bash
run_frontend.bat
```

**方法 B：手動啟動**
```bash
cd frontend
streamlit run app.py
```

前端會在 `http://localhost:8501` 啟動並自動開啟瀏覽器。

### 4. 開始使用

1. 確認後端連線（點擊側邊欄的「檢查連線」）
2. 從左側選單選擇功能：
   - **檔案上傳**：測試檔案上傳與進度顯示
   - **長時間任務**：測試背景任務處理
   - **任務管理**：查看所有任務狀態
   - **設定**：管理應用程式設定

---

## 核心功能詳解

### 1. Streamlit 呼叫 FastAPI API

#### 後端 API 設計（FastAPI）

```python
# backend/main.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ProcessRequest(BaseModel):
    data: str
    delay: int = 5

@app.post("/api/process")
async def create_process_task(request: ProcessRequest):
    task_id = str(uuid.uuid4())
    # 建立背景任務...
    return {"task_id": task_id, "status": "pending"}
```

#### 前端 API 客戶端（Streamlit）

```python
# frontend/utils/api_client.py
import requests

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = self._create_session()

    def create_process_task(self, data: str, delay: int = 5):
        response = self.session.post(
            f"{self.base_url}/api/process",
            json={"data": data, "delay": delay}
        )
        return response.json()
```

#### 在 Streamlit 中使用

```python
# frontend/pages/long_task.py
from utils.api_client import get_api_client

api_client = get_api_client()

if st.button("建立任務"):
    response = api_client.create_process_task(
        data="測試資料",
        delay=10
    )
    st.success(f"任務已建立：{response['task_id']}")
```

---

### 2. 檔案上傳與進度顯示

#### 後端處理檔案上傳

```python
# backend/main.py
from fastapi import File, UploadFile, BackgroundTasks

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    # 儲存檔案
    task_id = str(uuid.uuid4())
    file_path = f"uploads/{task_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 建立背景任務處理
    background_tasks.add_task(process_file_task, task_id, file_path)

    return {"task_id": task_id, "status": "pending"}
```

#### 前端上傳檔案

```python
# frontend/pages/file_upload.py
import streamlit as st
from utils.api_client import get_api_client

uploaded_file = st.file_uploader("選擇檔案")

if st.button("上傳") and uploaded_file:
    # 上傳檔案
    response = api_client.upload_file(
        uploaded_file.getvalue(),
        uploaded_file.name
    )

    task_id = response['task_id']
    st.success(f"上傳成功！任務 ID: {task_id}")
```

#### 顯示上傳進度

```python
# 使用進度條
progress_bar = st.progress(0)
status_text = st.empty()

while True:
    # 取得任務狀態
    status = api_client.get_task_status(task_id)

    # 更新進度
    progress = status['progress']
    progress_bar.progress(progress / 100)
    status_text.text(status['message'])

    if status['status'] == 'completed':
        break

    time.sleep(0.5)
```

---

### 3. 長時間任務的進度追蹤

#### 後端背景任務處理

```python
# backend/main.py
async def process_long_task(task_id: str, data: str, delay: int):
    """背景任務，更新進度"""
    try:
        # 更新狀態為處理中
        tasks_status[task_id]["status"] = "processing"

        # 分階段處理，更新進度
        stages = [
            (20, "正在初始化..."),
            (40, "正在載入資料..."),
            (60, "正在處理資料..."),
            (80, "正在生成結果..."),
            (100, "處理完成")
        ]

        for progress, message in stages:
            await asyncio.sleep(delay / len(stages))
            tasks_status[task_id]["progress"] = progress
            tasks_status[task_id]["message"] = message

        # 完成
        tasks_status[task_id]["status"] = "completed"
        tasks_status[task_id]["result"] = {
            "processed_data": f"已處理: {data}"
        }

    except Exception as e:
        tasks_status[task_id]["status"] = "failed"
        tasks_status[task_id]["error"] = str(e)
```

#### 前端輪詢進度

```python
# frontend/pages/long_task.py
def display_task_progress(task_id):
    """顯示任務進度"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    while True:
        # 取得最新狀態
        status = api_client.get_task_status(task_id)

        # 更新 UI
        progress_bar.progress(status['progress'] / 100)
        status_text.text(status['message'])

        # 檢查是否完成
        if status['status'] == 'completed':
            st.success("處理完成！")
            st.json(status['result'])
            break
        elif status['status'] == 'failed':
            st.error(f"處理失敗: {status['error']}")
            break

        time.sleep(0.5)  # 輪詢間隔
```

---

### 4. 多頁面應用程式架構

#### 主應用程式

```python
# frontend/app.py
import streamlit as st

st.set_page_config(page_title="應用程式", layout="wide")

# 側邊欄導航
with st.sidebar:
    page = st.radio("選擇頁面", [
        "首頁",
        "檔案上傳",
        "長時間任務",
        "任務管理",
        "設定"
    ])

# 根據選擇載入頁面
if page == "首頁":
    from pages import home
    home.show(api_client, session_state)
elif page == "檔案上傳":
    from pages import file_upload
    file_upload.show(api_client, session_state)
# ... 其他頁面
```

#### 頁面模組結構

```python
# frontend/pages/file_upload.py
def show(api_client, session_state):
    """顯示檔案上傳頁面"""
    st.title("檔案上傳")

    # 頁面內容...
    uploaded_file = st.file_uploader("選擇檔案")

    if st.button("上傳"):
        # 處理上傳...
        pass
```

#### 優點
- 模組化設計，易於維護
- 每個頁面獨立開發
- 共用 API 客戶端和 Session State
- 統一的導航體驗

---

### 5. Session State 管理

#### Session State 管理器

```python
# frontend/utils/session_state.py
import streamlit as st
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class AppSessionState:
    """應用程式 Session State 管理"""

    defaults: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # 初始化預設值
        for key, value in self.defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def get(self, key: str, default=None):
        return st.session_state.get(key, default)

    def set(self, key: str, value):
        st.session_state[key] = value

    def update(self, **kwargs):
        for key, value in kwargs.items():
            st.session_state[key] = value
```

#### 使用範例

```python
# 取得 Session State 管理器
from utils.session_state import get_session_state

session_state = get_session_state()

# 讀取值
user_name = session_state.get('user_name', '訪客')

# 設定值
session_state.set('user_name', '張三')

# 批次更新
session_state.update(
    user_name='張三',
    user_role='admin',
    last_login=datetime.now()
)

# 新增訊息
session_state.add_message("操作成功", 'success')

# 取得訊息
messages = session_state.get_messages()
```

#### 跨頁面資料共享

```python
# 在檔案上傳頁面儲存
session_state.add_uploaded_file(filename, task_id)

# 在任務管理頁面讀取
uploaded_files = session_state.get_uploaded_files()
for file_info in uploaded_files:
    st.write(f"{file_info['filename']} - {file_info['task_id']}")
```

---

### 6. 錯誤處理與繁體中文訊息

#### 自訂錯誤類別

```python
# frontend/utils/error_handler.py
class AppError(Exception):
    """應用程式基礎錯誤"""
    def __init__(self, message: str, error_code=None, details=None):
        self.message = message
        self.error_code = error_code
        self.details = details

class ValidationError(AppError):
    """資料驗證錯誤"""
    pass

class FileError(AppError):
    """檔案相關錯誤"""
    pass
```

#### 錯誤訊息對照表

```python
ERROR_MESSAGES = {
    'connection_error': '無法連接到伺服器，請檢查網路連線',
    'timeout_error': '請求超時，請稍後再試',
    'file_too_large': '檔案大小超過限制',
    'invalid_file_format': '不支援的檔案格式',
    'task_not_found': '找不到指定的任務',
}

def get_error_message(error_code: str) -> str:
    return ERROR_MESSAGES.get(error_code, '發生未知錯誤')
```

#### 統一的錯誤顯示

```python
# frontend/utils/error_handler.py
def display_error(message: str, details=None):
    """在 Streamlit 中顯示錯誤"""
    st.error(f"❌ {message}")

    if details:
        with st.expander("查看詳細資訊"):
            st.json(details)

def display_success(message: str):
    st.success(f"✅ {message}")

def display_warning(message: str):
    st.warning(f"⚠️ {message}")
```

#### 錯誤處理裝飾器

```python
from functools import wraps

def handle_errors(error_message="操作失敗"):
    """錯誤處理裝飾器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AppError as e:
                display_error(e.message, e.details)
            except Exception as e:
                display_error(f"{error_message}: {str(e)}")
        return wrapper
    return decorator

# 使用範例
@handle_errors("檔案上傳失敗")
def upload_file():
    # 上傳邏輯...
    pass
```

#### 輸入驗證

```python
# frontend/utils/error_handler.py
def validate_file_size(file, max_size_mb=10):
    """驗證檔案大小"""
    file_size = len(file.getvalue())
    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise FileError(
            message=f"檔案大小超過限制（最大 {max_size_mb}MB）",
            error_code='file_too_large',
            details={'file_size': file_size}
        )

def validate_file_extension(filename: str, allowed_extensions: list):
    """驗證檔案副檔名"""
    file_ext = '.' + filename.rsplit('.', 1)[-1].lower()

    if file_ext not in allowed_extensions:
        raise FileError(
            message=f"不支援的檔案格式，請使用: {', '.join(allowed_extensions)}",
            error_code='invalid_file_format'
        )

# 使用範例
try:
    validate_file_size(uploaded_file, max_size_mb=10)
    validate_file_extension(uploaded_file.name, ['.csv', '.xlsx'])
except FileError as e:
    display_error(e.message)
```

---

## 最佳實踐

### 1. API 客戶端設計

#### 使用 Session 重複利用連線
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()

    # 設定重試策略
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session
```

#### 使用 Streamlit 快取
```python
@st.cache_resource
def get_api_client(base_url: str):
    """取得 API 客戶端（快取）"""
    return APIClient(base_url)

# 使用
api_client = get_api_client("http://localhost:8000")
```

### 2. 進度追蹤最佳實踐

#### 輪詢策略
```python
# 適應性輪詢間隔
poll_interval = 0.5  # 開始時快速輪詢
max_interval = 5.0   # 最大間隔

while True:
    status = api_client.get_task_status(task_id)

    # 根據進度調整間隔
    if status['progress'] < 50:
        time.sleep(poll_interval)
    else:
        time.sleep(min(poll_interval * 2, max_interval))

    if status['status'] in ['completed', 'failed']:
        break
```

#### 超時處理
```python
import time

start_time = time.time()
max_wait = 300  # 5 分鐘

while True:
    if time.time() - start_time > max_wait:
        st.error("任務處理超時")
        break

    # 檢查狀態...
```

### 3. 效能優化

#### 批次處理
```python
# 分批上傳大量檔案
batch_size = 10
for i in range(0, len(files), batch_size):
    batch = files[i:i + batch_size]
    for file in batch:
        api_client.upload_file(file)

    st.progress((i + batch_size) / len(files))
```

#### 非同步處理（進階）
```python
import asyncio
import aiohttp

async def upload_files_async(files):
    async with aiohttp.ClientSession() as session:
        tasks = [upload_one_file(session, file) for file in files]
        results = await asyncio.gather(*tasks)
    return results
```

### 4. 安全性考量

#### API 金鑰驗證
```python
# 後端
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="無效的 API 金鑰")

@app.post("/api/upload", dependencies=[Depends(verify_api_key)])
async def upload_file(...):
    pass

# 前端
headers = {"X-API-Key": "your-api-key"}
response = requests.post(url, headers=headers)
```

#### 檔案類型驗證
```python
ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.txt', '.json'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def validate_upload(file):
    # 檢查副檔名
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("不支援的檔案類型")

    # 檢查大小
    if len(file.getvalue()) > MAX_FILE_SIZE:
        raise ValueError("檔案過大")
```

---

## 常見問題

### Q1: 如何處理後端服務未啟動的情況？

**解決方案**：在應用程式啟動時檢查連線
```python
# frontend/app.py
from utils.api_client import get_api_client, check_backend_connection

api_client = get_api_client()

if not check_backend_connection(api_client):
    st.error("無法連接到後端服務")
    st.info("請先啟動 FastAPI 伺服器：`python -m uvicorn main:app`")
    st.stop()  # 停止執行
```

### Q2: 如何在多個頁面間共享資料？

**解決方案**：使用 Session State
```python
# 在任意頁面設定
session_state.set('shared_data', {'key': 'value'})

# 在其他頁面讀取
data = session_state.get('shared_data', {})
```

### Q3: 如何處理長時間任務超時？

**解決方案**：實作超時機制和任務取消
```python
# 後端：支援任務取消
tasks_cancelable = {}

@app.delete("/api/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    if task_id in tasks_cancelable:
        tasks_cancelable[task_id].cancel()
    return {"message": "任務已取消"}

# 前端：提供取消按鈕
if st.button("取消任務"):
    api_client.cancel_task(task_id)
    st.warning("任務已取消")
```

### Q4: 檔案上傳失敗如何重試？

**解決方案**：使用重試裝飾器
```python
from utils.error_handler import with_retry

@with_retry(max_attempts=3, delay=1.0)
def upload_file_with_retry(file):
    return api_client.upload_file(file.getvalue(), file.name)

# 使用
try:
    response = upload_file_with_retry(uploaded_file)
except Exception as e:
    st.error(f"上傳失敗（已重試 3 次）: {str(e)}")
```

### Q5: 如何在生產環境部署？

**建議步驟**：

1. **環境變數設定**
```bash
# .env
API_BASE_URL=https://api.yourdomain.com
SECRET_KEY=your-production-secret-key
```

2. **使用 HTTPS**
```python
# 前端
api_client = get_api_client("https://api.yourdomain.com")

# 後端 CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True
)
```

3. **使用生產級 WSGI 伺服器**
```bash
# 安裝 gunicorn
pip install gunicorn

# 啟動
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

4. **Streamlit 部署**
```bash
# Streamlit Cloud 或 Docker
docker build -t streamlit-app .
docker run -p 8501:8501 streamlit-app
```

---

## 進階應用

### 1. WebSocket 即時通訊

對於需要更即時的進度更新，可使用 WebSocket：

#### 後端（FastAPI）
```python
from fastapi import WebSocket

@app.websocket("/ws/task/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()

    while True:
        # 取得任務狀態
        status = tasks_status.get(task_id, {})

        # 發送狀態
        await websocket.send_json(status)

        if status.get('status') in ['completed', 'failed']:
            break

        await asyncio.sleep(0.5)

    await websocket.close()
```

#### 前端（Streamlit）
注意：Streamlit 原生不支援 WebSocket，建議繼續使用輪詢或使用自訂元件。

### 2. 使用 Redis 儲存任務狀態

生產環境建議使用 Redis 替代記憶體字典：

```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def save_task_status(task_id: str, status: dict):
    redis_client.setex(
        f"task:{task_id}",
        3600,  # 1 小時過期
        json.dumps(status)
    )

def get_task_status(task_id: str) -> dict:
    data = redis_client.get(f"task:{task_id}")
    return json.loads(data) if data else None
```

### 3. 任務佇列（Celery）

處理大量任務時使用 Celery：

```python
from celery import Celery

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task(bind=True)
def process_file_task(self, file_path: str):
    # 更新進度
    self.update_state(
        state='PROGRESS',
        meta={'current': 50, 'total': 100}
    )

    # 處理檔案...

    return {'status': 'completed'}

# FastAPI 端點
@app.post("/api/upload")
async def upload_file(file: UploadFile):
    # 儲存檔案...

    # 建立 Celery 任務
    task = process_file_task.delay(file_path)

    return {"task_id": task.id}
```

### 4. 檔案串流上傳

處理大檔案時使用串流上傳：

```python
# 後端
@app.post("/api/upload/stream")
async def upload_stream(request: Request):
    async with aiofiles.open('output.bin', 'wb') as f:
        async for chunk in request.stream():
            await f.write(chunk)

    return {"message": "上傳完成"}

# 前端
def upload_large_file(file_path: str):
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{api_client.base_url}/api/upload/stream",
            data=f,
            headers={'Content-Type': 'application/octet-stream'}
        )
    return response.json()
```

---

## 參考資源

### 官方文件
- [Streamlit 文件](https://docs.streamlit.io/)
- [FastAPI 文件](https://fastapi.tiangolo.com/)
- [Pydantic 文件](https://docs.pydantic.dev/)

### 相關專案
- [Streamlit Components](https://streamlit.io/components)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

### 範例檔案
- `backend/main.py` - 完整的後端 API 實作
- `frontend/app.py` - 多頁面應用程式主檔案
- `frontend/utils/api_client.py` - API 客戶端封裝
- `frontend/utils/session_state.py` - Session State 管理
- `frontend/utils/error_handler.py` - 錯誤處理工具

---

## 授權與維護

**專案**：Fairmont Quotation System
**模組**：Streamlit-FastAPI 整合範例
**建立日期**：2025-12-19
**維護者**：開發團隊
**授權**：內部使用

---

**問題回報**：請在專案中建立 Issue
**貢獻**：歡迎提交 Pull Request
