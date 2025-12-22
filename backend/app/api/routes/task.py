"""Task status API routes."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ...models import APIResponse
from ...api.dependencies import get_store_dependency
from ...store import InMemoryStore
from ...utils import log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Task"])


@router.get(
    "/tasks/{task_id}",
    response_model=APIResponse,
    summary="取得任務狀態",
)
async def get_task_status(
    task_id: str,
    store: InMemoryStore = Depends(get_store_dependency),
) -> dict:
    """
    取得後台任務的狀態與進度.

    - **task_id**: 任務 ID
    - 返回任務狀態、進度百分比、訊息
    """
    try:
        task = store.get_task(task_id)

        return {
            "success": True,
            "message": f"任務狀態：{task.status}",
            "data": {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "message": task.message,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "result": task.result,
                "error": task.error,
            },
        }

    except Exception as e:
        log_error(e, context=f"Get task status: {task_id}")
        raise


@router.get(
    "/tasks",
    response_model=APIResponse,
    summary="取得任務列表",
)
async def list_tasks(
    limit: int = Query(20, le=100, description="回傳數量限制"),
    status: Optional[str] = Query(None, regex="^(pending|processing|completed|failed)$", description="篩選狀態"),
    store: InMemoryStore = Depends(get_store_dependency),
) -> dict:
    """
    取得所有任務列表.

    - **limit**: 回傳數量限制（最多 100）
    - **status**: 篩選狀態（pending/processing/completed/failed）
    """
    try:
        tasks = store.list_tasks()

        # Filter by status
        if status:
            tasks = [t for t in tasks if t.status == status]

        # Apply limit
        tasks = tasks[:limit]

        return {
            "success": True,
            "message": f"取得 {len(tasks)} 個任務",
            "data": {
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "task_type": t.task_type,
                        "status": t.status,
                        "progress": t.progress,
                        "message": t.message,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                        "started_at": t.started_at.isoformat() if t.started_at else None,
                        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    }
                    for t in tasks
                ],
                "total": len(tasks),
            },
        }
    except Exception as e:
        log_error(e, context="List tasks")
        raise
