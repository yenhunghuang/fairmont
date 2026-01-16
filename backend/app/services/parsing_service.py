"""PDF Parsing Service - 共用的 PDF 解析背景任務邏輯.

將 upload.py 和 parse.py 中重複的 _parse_pdf_background 邏輯
提取到這個共用服務中。
"""

import asyncio
import logging
from typing import List, Optional
from ..store import InMemoryStore
from ..utils import log_error
from ..utils.document_type import detect_document_type_from_filename
from .pdf_parser import get_pdf_parser
from .image_extractor import get_image_extractor
from .image_matcher_deterministic import get_deterministic_image_matcher

logger = logging.getLogger(__name__)

# Gemini API 並發控制：限制同時解析的 PDF 數量，避免 API 限流
_parsing_semaphore = asyncio.Semaphore(2)


async def parse_pdf_background(
    document_id: str,
    task_id: str,
    store: InMemoryStore,
    extract_images: bool = True,
    target_categories: Optional[List[str]] = None,
) -> None:
    """背景任務：PDF 解析（帶並發控制）.

    Args:
        document_id: 文件 ID
        task_id: 任務 ID
        store: InMemoryStore 實例
        extract_images: 是否提取圖片
        target_categories: 目標類別篩選
    """
    async with _parsing_semaphore:
        await _do_parse_pdf(
            document_id, task_id, store, extract_images, target_categories
        )


async def _do_parse_pdf(
    document_id: str,
    task_id: str,
    store: InMemoryStore,
    extract_images: bool = True,
    target_categories: Optional[List[str]] = None,
) -> None:
    """實際執行 PDF 解析邏輯.

    Args:
        document_id: 文件 ID
        task_id: 任務 ID
        store: InMemoryStore 實例
        extract_images: 是否提取圖片
        target_categories: 目標類別篩選
    """
    try:
        # Get task and update status
        task = store.get_task(task_id)
        task.status = "processing"
        task.message = "正在解析 PDF..."
        task.update_progress(10, "正在解析 PDF...")
        store.update_task(task)

        # Get document
        document = store.get_document(document_id)

        # Parse PDF with Gemini
        parser = get_pdf_parser()
        boq_items, image_paths, project_metadata = await parser.parse_boq_with_gemini(
            file_path=document.file_path,
            document_id=document_id,
            extract_images=extract_images,
            target_categories=target_categories,
        )

        # Store project metadata in document
        if project_metadata:
            document.project_name = project_metadata.get("project_name")

        task.update_progress(70, "正在提取圖片...")

        # Extract images and use deterministic matcher
        extractor = get_image_extractor()
        matched_count = 0
        images_with_bytes = []

        if extract_images:
            # Extract all images (unified matcher handles filtering + matching)
            images_with_bytes = extractor.extract_images_with_bytes(
                document.file_path, document_id
            )

            if images_with_bytes and boq_items:
                task.update_progress(75, "正在匹配圖片到項目...")

                # Detect document type from filename for page offset configuration
                document_type = detect_document_type_from_filename(document.filename)

                # Use deterministic algorithm: match based on page location + image size
                # Rule-based approach: items on page N → images on page N+offset, select largest image
                # Automatically excludes logos/icons (small area) and selects product samples
                matcher = get_deterministic_image_matcher(vendor_id="habitus")
                page_offset = matcher.get_page_offset(document_type)

                logger.info(
                    f"Image matching: document_type={document_type}, page_offset={page_offset}"
                )

                image_to_item_map = await matcher.match_images_to_items(
                    images_with_bytes,
                    boq_items,
                    target_page_offset=page_offset,
                )

                # Apply matches - convert to Base64 and assign to items
                for img_idx, item_id in image_to_item_map.items():
                    if img_idx < len(images_with_bytes):
                        # Convert to Base64
                        img_data = images_with_bytes[img_idx]
                        base64_str = extractor._convert_to_base64(img_data["bytes"])

                        # Find the matching BOQ item
                        item = next((i for i in boq_items if i.id == item_id), None)
                        if item:
                            item.photo_base64 = base64_str
                            matched_count += 1

                logger.info(
                    f"Matched {matched_count} images to items using deterministic algorithm "
                    "(page location + image size)"
                )

        task.update_progress(80, "正在儲存結果...")

        # Store items (now with photo_base64)
        for item in boq_items:
            store.add_boq_item(item)

        # Update document
        document.parse_status = "completed"
        document.parse_message = f"成功解析 {len(boq_items)} 個項目"
        document.extracted_items_count = len(boq_items)
        document.extracted_images_count = len(images_with_bytes)
        store.update_document(document)

        # Complete task
        task.complete(
            result={
                "document_id": document_id,
                "items_count": len(boq_items),
                "images_count": len(images_with_bytes),
                "matched_count": matched_count,
            }
        )
        store.update_task(task)

        logger.info(
            f"Successfully parsed document {document_id}: "
            f"{len(boq_items)} items, {len(images_with_bytes)} images, {matched_count} matched"
        )

    except Exception as e:
        logger.error(f"Error parsing document {document_id}: {e}")
        log_error(e, context=f"Parse PDF: {document_id}")

        try:
            task = store.get_task(task_id)
            task.fail(str(e))
            store.update_task(task)

            document = store.get_document(document_id)
            document.parse_status = "failed"
            document.parse_error = str(e)
            store.update_document(document)
        except Exception as inner_e:
            logger.error(f"Failed to update task status: {inner_e}")
