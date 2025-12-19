"""
FastAPI 後端範例 - Streamlit 整合最佳實踐

功能：
1. 檔案上傳處理
2. 長時間任務處理（使用背景任務）
3. 進度追蹤 API
4. 錯誤處理與繁體中文回應
"""

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, List
import asyncio
import uuid
from datetime import datetime
import os
import shutil

app = FastAPI(title="Streamlit-FastAPI 整合範例")

# CORS 設定 - 允許 Streamlit 前端呼叫
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境應該限制特定來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任務狀態儲存（生產環境應使用 Redis 或資料庫）
tasks_status: Dict[str, Dict] = {}

# 上傳檔案暫存目錄
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 資料模型 ====================

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    message: str
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class ProcessRequest(BaseModel):
    data: str
    delay: int = 5  # 模擬處理時間（秒）


# ==================== 背景任務處理 ====================

async def process_long_task(task_id: str, data: str, delay: int):
    """模擬長時間處理任務，並更新進度"""
    try:
        tasks_status[task_id]["status"] = "processing"
        tasks_status[task_id]["message"] = "任務處理中..."

        # 模擬分階段處理，更新進度
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
            tasks_status[task_id]["updated_at"] = datetime.now().isoformat()

        # 任務完成
        tasks_status[task_id]["status"] = "completed"
        tasks_status[task_id]["result"] = {
            "processed_data": f"已處理: {data}",
            "timestamp": datetime.now().isoformat(),
            "items_processed": 100
        }

    except Exception as e:
        tasks_status[task_id]["status"] = "failed"
        tasks_status[task_id]["error"] = f"處理失敗: {str(e)}"
        tasks_status[task_id]["message"] = "任務執行時發生錯誤"


async def process_file_task(task_id: str, file_path: str, filename: str):
    """模擬檔案處理任務"""
    try:
        tasks_status[task_id]["status"] = "processing"
        tasks_status[task_id]["message"] = f"正在處理檔案: {filename}"

        # 模擬檔案處理
        file_size = os.path.getsize(file_path)

        stages = [
            (20, "正在讀取檔案..."),
            (40, "正在驗證格式..."),
            (60, "正在解析內容..."),
            (80, "正在生成報告..."),
            (100, "處理完成")
        ]

        for progress, message in stages:
            await asyncio.sleep(1)  # 模擬處理時間
            tasks_status[task_id]["progress"] = progress
            tasks_status[task_id]["message"] = message
            tasks_status[task_id]["updated_at"] = datetime.now().isoformat()

        # 完成
        tasks_status[task_id]["status"] = "completed"
        tasks_status[task_id]["result"] = {
            "filename": filename,
            "size": file_size,
            "processed_at": datetime.now().isoformat(),
            "summary": {
                "total_lines": 150,
                "valid_records": 145,
                "errors": 5
            }
        }

    except Exception as e:
        tasks_status[task_id]["status"] = "failed"
        tasks_status[task_id]["error"] = f"檔案處理失敗: {str(e)}"


# ==================== API 端點 ====================

@app.get("/")
async def root():
    """健康檢查"""
    return {
        "status": "ok",
        "message": "FastAPI 後端運行中",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/upload", response_model=TaskResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    檔案上傳端點

    - 接收檔案並儲存
    - 建立背景任務處理
    - 返回任務 ID 供前端追蹤進度
    """
    try:
        # 生成唯一任務 ID
        task_id = str(uuid.uuid4())

        # 儲存檔案
        file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 初始化任務狀態
        tasks_status[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "檔案已接收，等待處理",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 新增背景任務
        background_tasks.add_task(process_file_task, task_id, file_path, file.filename)

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message=f"檔案 '{file.filename}' 已上傳，開始處理"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案上傳失敗: {str(e)}")


@app.post("/api/process", response_model=TaskResponse)
async def create_process_task(
    background_tasks: BackgroundTasks,
    request: ProcessRequest
):
    """
    建立長時間處理任務

    - 接收處理請求
    - 建立背景任務
    - 返回任務 ID
    """
    try:
        task_id = str(uuid.uuid4())

        # 初始化任務狀態
        tasks_status[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "任務已建立，等待處理",
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 新增背景任務
        background_tasks.add_task(process_long_task, task_id, request.data, request.delay)

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message="處理任務已建立"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任務建立失敗: {str(e)}")


@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    取得任務狀態

    前端可定期輪詢此端點以獲取最新進度
    """
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail="找不到指定的任務")

    return tasks_status[task_id]


@app.get("/api/tasks", response_model=List[TaskStatus])
async def list_tasks(limit: int = 10):
    """列出所有任務（最多顯示 limit 筆）"""
    tasks = list(tasks_status.values())
    # 按建立時間排序（最新的在前）
    tasks.sort(key=lambda x: x["created_at"], reverse=True)
    return tasks[:limit]


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """刪除任務記錄"""
    if task_id not in tasks_status:
        raise HTTPException(status_code=404, detail="找不到指定的任務")

    del tasks_status[task_id]
    return {"message": "任務已刪除", "task_id": task_id}


# ==================== 錯誤處理 ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """統一的 HTTP 錯誤處理，返回繁體中文訊息"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """處理未預期的錯誤"""
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": f"伺服器內部錯誤: {str(exc)}",
            "status_code": 500,
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
