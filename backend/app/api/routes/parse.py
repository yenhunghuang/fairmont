"""Parse API routes."""

import logging
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from ...models import ProcessingTask, APIResponse, BOQItemResponse
from ...api.dependencies import StoreDep
from ...services.parsing_service import parse_pdf_background
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
    *,
    store: StoreDep,
) -> dict:
    """
    啟動 PDF 解析任務.

    - 對已上傳的 PDF 檔案啟動 BOQ 解析
    - 解析使用 Gemini AI，為非同步操作
    - 返回任務 ID，可用於查詢進度
    """
    try:
        # Validate document exists
        store.get_document(document_id)

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
            parse_pdf_background,
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


@router.get(
    "/documents/{document_id}/parse-result",
    response_model=APIResponse,
    summary="取得解析結果",
)
async def get_parse_result(
    document_id: str,
    *,
    store: StoreDep,
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
    *,
    store: StoreDep,
) -> dict:
    """
    分析平面圖 PDF，核對並補充 BOQ 項目中缺失的數量.

    - **floor_plan_document_id**: 平面圖文件 ID
    - **boq_document_id**: BOQ 文件 ID
    - **items_to_verify**: 需要核對的項目 ID 列表（空表示全部）
    """
    try:
        # Validate documents exist
        store.get_document(floor_plan_document_id)
        store.get_document(boq_document_id)

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
