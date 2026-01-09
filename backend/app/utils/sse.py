"""SSE (Server-Sent Events) 格式化工具."""

import json
from typing import Any, Optional

from ..models.progress import ProgressUpdate


def format_sse_event(
    event_type: str,
    data: dict[str, Any],
    event_id: Optional[str] = None,
) -> str:
    """
    格式化 SSE 事件.

    Args:
        event_type: 事件類型 (progress, result, error)
        data: 事件資料
        event_id: 可選的事件 ID

    Returns:
        SSE 格式的字串，以雙換行結尾
    """
    lines = []

    if event_id:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")  # SSE 需要空行結尾

    return "\n".join(lines) + "\n"


def format_progress_event(update: ProgressUpdate) -> str:
    """格式化進度事件."""
    return format_sse_event("progress", update.to_dict())


def format_result_event(
    project_name: Optional[str],
    items: list[dict[str, Any]],
    statistics: dict[str, Any],
) -> str:
    """格式化結果事件."""
    return format_sse_event(
        "result",
        {
            "project_name": project_name,
            "items": items,
            "statistics": statistics,
        },
    )


def format_error_event(
    code: str,
    message: str,
    stage: Optional[str] = None,
) -> str:
    """格式化錯誤事件."""
    data: dict[str, Any] = {"code": code, "message": message}
    if stage:
        data["stage"] = stage
    return format_sse_event("error", data)
