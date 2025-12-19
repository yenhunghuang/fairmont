"""Task status API routes."""

import logging
from fastapi import APIRouter, Depends

from ...models import APIResponse
from ...api.dependencies import StoreDep
from ...utils import log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Task"])


@router.get(
    "/task/{task_id}",
    response_model=APIResponse,
    summary="取得任務狀態",
)
async def get_task_status(
    task_id: str,
    store: StoreDep = Depends(),
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
