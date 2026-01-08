"""Progress display component."""

import streamlit as st
import time
from typing import Optional


def display_progress(
    progress: int,
    message: str,
    status: str = "processing",
) -> None:
    """
    Display progress bar with message.

    Args:
        progress: Progress percentage (0-100)
        message: Progress message
        status: Status type (pending, processing, completed, failed)
    """
    # Status colors
    status_colors = {
        "pending": "🔵",
        "processing": "🟡",
        "completed": "🟢",
        "failed": "🔴",
    }

    icon = status_colors.get(status, "🔵")

    st.write(f"{icon} {message}")
    st.progress(progress / 100)


def display_task_status(task: dict) -> None:
    """
    Display detailed task status.

    Args:
        task: Task dictionary with status information
    """
    st.subheader("⏳ 任務狀態")

    task_id = task.get("task_id") or task.get("id", "")
    status = task.get("status", "pending")
    progress = task.get("progress", 0)
    message = task.get("message", "")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("任務 ID", task_id[:12] + "...")

    with col2:
        status_display = {
            "pending": "⏳ 等待中",
            "processing": "🔄 處理中",
            "completed": "✅ 完成",
            "failed": "❌ 失敗",
        }
        st.metric("狀態", status_display.get(status, status))

    with col3:
        st.metric("進度", f"{progress}%")

    # Display progress bar
    st.progress(progress / 100)
    st.info(f"📝 {message}")

    # Display error if failed
    if status == "failed" and task.get("error"):
        st.error(f"❌ 錯誤：{task['error']}")


def wait_for_task_completion(
    client,
    task_id: str,
    max_wait: int = 300,
    poll_interval: int = 2,
    placeholder=None,
) -> Optional[dict]:
    """
    Wait for task completion with progress display.

    Args:
        client: API client
        task_id: Task ID to wait for
        max_wait: Maximum wait time in seconds
        poll_interval: Poll interval in seconds
        placeholder: Streamlit placeholder for updates

    Returns:
        Final task status or None if timeout
    """
    import asyncio

    elapsed = 0
    last_progress = 0

    while elapsed < max_wait:
        try:
            # Get task status
            async def check_status():
                return await client.get_task_status(task_id)

            status_response = asyncio.run(check_status())
            task = status_response.get("data", {})

            # Update progress
            if placeholder:
                with placeholder.container():
                    display_task_status(task)

            # Check if completed
            if task.get("status") in ["completed", "failed"]:
                return task

            # Wait before next poll
            time.sleep(poll_interval)
            elapsed += poll_interval

        except Exception as e:
            st.error(f"無法取得任務狀態：{e}")
            return None

    st.error(f"⏱️ 任務超時（超過 {max_wait} 秒）")
    return None


def display_completion_status(task: dict) -> None:
    """
    Display task completion status.

    Args:
        task: Completed task dictionary
    """
    st.subheader("✨ 處理完成")

    if task.get("status") == "completed":
        st.success("✅ 任務成功完成！")

        if task.get("result"):
            st.write("**結果摘要：**")
            result = task["result"]

            if isinstance(result, dict):
                for key, value in result.items():
                    st.write(f"- {key}: {value}")

    elif task.get("status") == "failed":
        st.error("❌ 任務處理失敗")
        if task.get("error"):
            st.error(f"**錯誤信息：** {task['error']}")
