"""File uploader component."""

import streamlit as st
from typing import List
from pathlib import Path


def file_uploader(max_files: int = 5, max_size_mb: int = 50) -> List[bytes]:
    """
    File uploader component with validation.

    Args:
        max_files: Maximum number of files
        max_size_mb: Maximum file size in MB

    Returns:
        List of file contents
    """
    st.subheader("📁 上傳 PDF 檔案")

    uploaded_files = st.file_uploader(
        "選擇 PDF 檔案",
        type=["pdf"],
        accept_multiple_files=True,
        help=f"最多 {max_files} 個檔案，每個檔案最大 {max_size_mb}MB",
    )

    if not uploaded_files:
        st.info("👇 請選擇要上傳的 PDF 檔案")
        return []

    # Validate files
    max_size_bytes = max_size_mb * 1024 * 1024
    valid_files = []

    for file in uploaded_files:
        # Check file count
        if len(uploaded_files) > max_files:
            st.error(f"❌ 檔案超過限制（最多 {max_files} 個）")
            continue

        # Check file size
        if file.size > max_size_bytes:
            st.error(
                f"❌ {file.name} 大小超過限制（{file.size / (1024*1024):.1f}MB > {max_size_mb}MB）"
            )
            continue

        valid_files.append(file)

    # Display file list
    if valid_files:
        st.success(f"✅ 已選擇 {len(valid_files)} 個檔案")

        with st.expander("📋 檔案列表"):
            for file in valid_files:
                st.write(f"- {file.name} ({file.size / (1024*1024):.1f}MB)")

    return valid_files


def display_upload_status(status: str, message: str = "") -> None:
    """
    Display upload status.

    Args:
        status: Status type (success, error, warning, info)
        message: Status message
    """
    status_icons = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }

    icon = status_icons.get(status, "ℹ️")

    if status == "success":
        st.success(f"{icon} {message}")
    elif status == "error":
        st.error(f"{icon} {message}")
    elif status == "warning":
        st.warning(f"{icon} {message}")
    else:
        st.info(f"{icon} {message}")
