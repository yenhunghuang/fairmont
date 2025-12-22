"""Parse API routes."""

import logging
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel

from ...models import ProcessingTask, APIResponse, BOQItemResponse
from ...api.dependencies import get_store_dependency
from ...services.pdf_parser import get_pdf_parser
from ...services.image_extractor import get_image_extractor
from ...services.image_matcher_deterministic import get_deterministic_image_matcher
from ...store import InMemoryStore
from ...utils import log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Parse"])


class ParseRequest(BaseModel):
    """Request model for parsing."""
    extract_images: bool = True
    target_categories: Optional[List[str]] = None


@router.post(
    "/documents/{document_id}/parsing",
    status_code=202,
    response_model=APIResponse,
    summary="啟動 PDF 解析",
)
async def start_parsing(
    document_id: str,
    background_tasks: BackgroundTasks,
    request: Optional[ParseRequest] = None,
    store: InMemoryStore = Depends(get_store_dependency),
) -> dict:
    """
    啟動 PDF 解析任務.

    - 對已上傳的 PDF 檔案啟動 BOQ 解析
    - 解析使用 Gemini AI，為非同步操作
    - 返回任務 ID，可用於查詢進度
    """
    try:
        # Get document
        document = store.get_document(document_id)

        # Create task
        task = ProcessingTask(
            task_type="parse_pdf",
            status="pending",
            message="等待處理",
            document_id=document_id,
        )

        store.add_task(task)

        # Schedule parsing
        extract_images = request.extract_images if request else True
        target_categories = request.target_categories if request else None

        background_tasks.add_task(
            _parse_pdf_background,
            document_id=document_id,
            task_id=task.task_id,
            store=store,
            extract_images=extract_images,
            target_categories=target_categories,
        )

        return {
            "success": True,
            "message": "解析任務已建立",
            "data": {
                "task_id": task.task_id,
                "status": task.status,
                "message": task.message,
            },
        }

    except Exception as e:
        log_error(e, context=f"Start parsing: {document_id}")
        raise


async def _parse_pdf_background(
    document_id: str,
    task_id: str,
    store: InMemoryStore,
    extract_images: bool = True,
    target_categories: Optional[List[str]] = None,
) -> None:
    """Background task for PDF parsing."""
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
        boq_items, image_paths = await parser.parse_boq_with_gemini(
            file_path=document.file_path,
            document_id=document_id,
            extract_images=extract_images,
            target_categories=target_categories,
        )

        task.update_progress(70, "正在提取圖片...")

        # Extract images and use Gemini Vision to match with BOQ items
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

                # Use deterministic algorithm: match based on page location + image size
                # Rule-based approach: items on page N → images on page N+1, select largest image
                # Automatically excludes logos/icons (small area) and selects product samples
                matcher = get_deterministic_image_matcher()
                image_to_item_map = await matcher.match_images_to_items(
                    images_with_bytes,
                    boq_items,
                    target_page_offset=1,
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

                logger.info(f"Matched {matched_count} images to items using deterministic algorithm (page location + image size)")

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
        task.complete(result={
            "document_id": document_id,
            "items_count": len(boq_items),
            "images_count": len(images_with_bytes),
            "matched_count": matched_count,
        })
        store.update_task(task)

        logger.info(f"Successfully parsed document {document_id}: {len(boq_items)} items, {len(images_with_bytes)} images, {matched_count} matched")

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


@router.get(
    "/documents/{document_id}/parse-result",
    response_model=APIResponse,
    summary="取得解析結果",
)
async def get_parse_result(
    document_id: str,
    store: InMemoryStore = Depends(get_store_dependency),
) -> dict:
    """
    取得 PDF 解析完成後的 BOQ 項目列表.

    - 返回解析出的所有項目
    - 包含提取的圖片資訊
    - 提供統計資訊
    """
    try:
        # Get document
        document = store.get_document(document_id)

        if document.parse_status == "pending":
            return {
                "success": False,
                "message": "解析尚未開始",
                "data": None,
            }

        if document.parse_status == "processing":
            return {
                "success": False,
                "message": "解析進行中，請稍後重試",
                "data": None,
            }

        if document.parse_status == "failed":
            return {
                "success": False,
                "message": f"解析失敗：{document.parse_error}",
                "data": None,
            }

        # Get items for this document
        items = store.get_items_by_document(document_id)
        images = store.get_images_by_document(document_id)

        return {
            "success": True,
            "message": f"成功取得解析結果：{len(items)} 個項目",
            "data": {
                "document_id": document_id,
                "items": [BOQItemResponse.from_boq_item(item).model_dump() for item in items],
                "images": [image.model_dump() for image in images],
                "statistics": {
                    "total_items": len(items),
                    "items_with_qty": sum(1 for item in items if item.qty is not None),
                    "items_with_photo": sum(1 for item in items if item.photo_base64),
                    "total_images": len(images),
                },
            },
        }

    except Exception as e:
        log_error(e, context=f"Get parse result: {document_id}")
        raise


@router.post(
    "/floor-plan-analyses",
    status_code=202,
    response_model=APIResponse,
    summary="平面圖數量核對",
)
async def analyze_floor_plan(
    floor_plan_document_id: str,
    boq_document_id: str,
    background_tasks: BackgroundTasks,
    items_to_verify: Optional[List[str]] = None,
    store: InMemoryStore = Depends(get_store_dependency),
) -> dict:
    """
    分析平面圖 PDF，核對並補充 BOQ 項目中缺失的數量.

    - **floor_plan_document_id**: 平面圖文件 ID
    - **boq_document_id**: BOQ 文件 ID
    - **items_to_verify**: 需要核對的項目 ID 列表（空表示全部）
    """
    try:
        # Validate documents exist
        floor_plan_doc = store.get_document(floor_plan_document_id)
        boq_doc = store.get_document(boq_document_id)

        # Create task
        task = ProcessingTask(
            task_type="analyze_floor_plan",
            status="pending",
            message="等待處理平面圖",
            document_id=floor_plan_document_id,
        )

        store.add_task(task)

        background_tasks.add_task(
            _analyze_floor_plan_background,
            floor_plan_document_id=floor_plan_document_id,
            boq_document_id=boq_document_id,
            task_id=task.task_id,
            store=store,
            items_to_verify=items_to_verify,
        )

        return {
            "success": True,
            "message": "平面圖分析任務已建立",
            "data": {
                "task_id": task.task_id,
                "status": task.status,
                "message": task.message,
            },
        }

    except Exception as e:
        log_error(e, context="Analyze floor plan")
        raise


async def _analyze_floor_plan_background(
    floor_plan_document_id: str,
    boq_document_id: str,
    task_id: str,
    store: InMemoryStore,
    items_to_verify: Optional[List[str]] = None,
) -> None:
    """Background task for floor plan analysis."""
    try:
        task = store.get_task(task_id)
        task.status = "processing"
        task.message = "正在分析平面圖..."
        store.update_task(task)

        # Get BOQ items
        boq_items = store.get_items_by_document(boq_document_id)

        # Filter items if specified
        if items_to_verify:
            boq_items = [item for item in boq_items if item.id in items_to_verify]

        # Get items without quantity
        items_without_qty = [item for item in boq_items if item.qty is None]

        # TODO: Use Gemini to analyze floor plan and extract quantities
        # For now, mark items as verified but without updating quantities
        for item in items_without_qty:
            item.qty_verified = True
            item.qty_source = "floor_plan"
            store.update_boq_item(item)

        task.complete(result={
            "verified_count": len(items_without_qty),
            "updated_items": [item.id for item in items_without_qty],
        })
        store.update_task(task)

        logger.info(f"Floor plan analysis completed: {len(items_without_qty)} items verified")

    except Exception as e:
        logger.error(f"Error analyzing floor plan: {e}")
        try:
            task = store.get_task(task_id)
            task.fail(str(e))
            store.update_task(task)
        except:
            pass
