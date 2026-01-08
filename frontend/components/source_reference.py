"""Source reference component."""

import streamlit as st
from typing import Optional


def display_source_reference(item: dict) -> None:
    """
    Display source reference information for a BOQ item.

    Args:
        item: BOQ item with source information
    """
    source_type = item.get("source_type", "unknown")
    source_page = item.get("source_page")
    source_location = item.get("source_location")
    qty_source = item.get("qty_source")
    qty_verified = item.get("qty_verified", False)

    st.subheader("📍 來源資訊")

    col1, col2 = st.columns(2)

    with col1:
        # Source type
        source_icons = {
            "boq": "📄",
            "floor_plan": "📐",
            "manual": "✏️",
        }
        icon = source_icons.get(source_type, "📄")
        st.write(f"{icon} **來源類型**: {source_type}")

        # Source page
        if source_page:
            st.write(f"**頁碼**: 第 {source_page} 頁")

    with col2:
        # Quantity source
        if qty_verified:
            qty_icons = {
                "boq": "📄",
                "floor_plan": "📐",
            }
            qty_icon = qty_icons.get(qty_source, "❓")
            st.success(f"{qty_icon} 數量來源: {qty_source} ✅")
        else:
            st.warning("⚠️ 數量未驗證")

    # Source location
    if source_location:
        with st.expander("📌 詳細位置"):
            st.write(source_location)


def display_document_info(document: dict) -> None:
    """
    Display source document information.

    Args:
        document: Source document dictionary
    """
    st.subheader("📄 檔案資訊")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("檔案名稱", document.get("filename", ""))

    with col2:
        file_size = document.get("file_size", 0) / (1024 * 1024)
        st.metric("檔案大小", f"{file_size:.2f}MB")

    with col3:
        st.metric("頁數", document.get("total_pages", ""))

    # Parse status
    parse_status = document.get("parse_status", "pending")
    status_display = {
        "pending": "⏳ 待解析",
        "processing": "🔄 解析中",
        "completed": "✅ 已完成",
        "failed": "❌ 失敗",
    }

    st.info(f"**解析狀態**: {status_display.get(parse_status, parse_status)}")

    if parse_status == "completed":
        col1, col2 = st.columns(2)
        with col1:
            st.metric("提取項目數", document.get("extracted_items_count", 0))
        with col2:
            st.metric("提取圖片數", document.get("extracted_images_count", 0))

    if parse_status == "failed":
        error_msg = document.get("parse_error", "未知錯誤")
        st.error(f"❌ {error_msg}")


def display_tracking_history(document: dict) -> None:
    """
    Display document tracking history.

    Args:
        document: Source document dictionary
    """
    st.subheader("📅 處理歷程")

    with st.expander("查看詳細歷程"):
        col1, col2 = st.columns(2)

        with col1:
            if document.get("uploaded_at"):
                st.write(f"**上傳時間**: {document['uploaded_at']}")

        with col2:
            if document.get("processed_at"):
                st.write(f"**完成時間**: {document['processed_at']}")

        # Progress info
        if document.get("parse_progress"):
            st.write(f"**解析進度**: {document['parse_progress']}%")

        if document.get("parse_message"):
            st.write(f"**狀態訊息**: {document['parse_message']}")
