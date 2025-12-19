"""Export API routes."""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...models import Quotation, BOQItem, ProcessingTask, APIResponse
from ...api.dependencies import StoreDep, FileManagerDep
from ...services.excel_generator import get_excel_generator
from ...store import InMemoryStore
from ...utils import log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Export"])


class CreateQuotationRequest(BaseModel):
    """Request model for creating quotation."""
    document_ids: List[str]
    title: Optional[str] = None


class ExportExcelRequest(BaseModel):
    """Request model for Excel export."""
    include_photos: bool = True
    photo_height_cm: float = 3.0


class UpdateItemsRequest(BaseModel):
    """Request model for updating quotation items."""
    updates: List[dict]


@router.post(
    "/quotation",
    status_code=201,
    response_model=APIResponse,
    summary="建立報價單",
)
async def create_quotation(
    request: CreateQuotationRequest,
    store: StoreDep = Depends(),
) -> dict:
    """
    從已解析的文件建立報價單.

    - **document_ids**: 來源文件 ID 列表
    - **title**: 報價單標題（可選）
    """
    try:
        # Validate documents exist
        documents = []
        all_items = []

        for doc_id in request.document_ids:
            doc = store.get_document(doc_id)
            documents.append(doc)

            # Get items from document
            items = store.get_items_by_document(doc_id)
            all_items.extend(items)

        # Merge items from multiple documents
        # Renumber sequentially
        for idx, item in enumerate(all_items, 1):
            item.no = idx

        # Create quotation
        quotation = Quotation(
            title=request.title or f"RFQ-{Quotation().id[:8].upper()}",
            source_document_ids=request.document_ids,
            items=all_items,
        )

        # Update statistics
        quotation.update_statistics()

        # Store quotation
        store.add_quotation(quotation)

        return {
            "success": True,
            "message": f"報價單已建立：{len(all_items)} 個項目",
            "data": quotation.model_dump(),
        }

    except Exception as e:
        log_error(e, context="Create quotation")
        raise


@router.get(
    "/quotation/{quotation_id}",
    response_model=APIResponse,
    summary="取得報價單",
)
async def get_quotation(
    quotation_id: str,
    store: StoreDep = Depends(),
) -> dict:
    """取得報價單詳細資訊."""
    try:
        quotation = store.get_quotation(quotation_id)

        return {
            "success": True,
            "message": "成功取得報價單",
            "data": quotation.model_dump(),
        }

    except Exception as e:
        log_error(e, context=f"Get quotation: {quotation_id}")
        raise


@router.get(
    "/quotation/{quotation_id}/items",
    response_model=APIResponse,
    summary="取得報價單項目列表",
)
async def get_quotation_items(
    quotation_id: str,
    store: StoreDep = Depends(),
) -> dict:
    """取得報價單中的所有項目."""
    try:
        quotation = store.get_quotation(quotation_id)

        return {
            "success": True,
            "message": f"成功取得 {len(quotation.items)} 個項目",
            "data": {
                "items": [item.model_dump() for item in quotation.items],
                "total": len(quotation.items),
            },
        }

    except Exception as e:
        log_error(e, context=f"Get quotation items: {quotation_id}")
        raise


@router.patch(
    "/quotation/{quotation_id}/items",
    response_model=APIResponse,
    summary="更新報價單項目",
)
async def update_quotation_items(
    quotation_id: str,
    request: UpdateItemsRequest,
    store: StoreDep = Depends(),
) -> dict:
    """
    批次更新報價單中的項目資料.

    - 可更新數量、描述、材料規格等欄位
    """
    try:
        quotation = store.get_quotation(quotation_id)

        # Update items
        for update_data in request.updates:
            item_id = update_data.get("id")
            if not item_id:
                continue

            # Find item in quotation
            item = next((i for i in quotation.items if i.id == item_id), None)
            if not item:
                continue

            # Update fields
            if "qty" in update_data:
                item.qty = update_data["qty"]
            if "description" in update_data:
                item.description = update_data["description"]
            if "materials_specs" in update_data:
                item.materials_specs = update_data["materials_specs"]
            if "dimension" in update_data:
                item.dimension = update_data["dimension"]
            if "location" in update_data:
                item.location = update_data["location"]
            if "note" in update_data:
                item.note = update_data["note"]

            # Update item in store
            store.update_boq_item(item)

        # Update quotation statistics
        quotation.update_statistics()
        store.update_quotation(quotation)

        return {
            "success": True,
            "message": f"成功更新 {len(request.updates)} 個項目",
            "data": quotation.model_dump(),
        }

    except Exception as e:
        log_error(e, context=f"Update quotation items: {quotation_id}")
        raise


@router.post(
    "/export/{quotation_id}/excel",
    status_code=202,
    response_model=APIResponse,
    summary="產出 Excel 報價單",
)
async def export_excel(
    quotation_id: str,
    request: Optional[ExportExcelRequest] = None,
    store: StoreDep = Depends(),
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    將報價單匯出為惠而蒙格式 Excel 檔案.

    - 為非同步操作
    - 完成後可下載檔案
    """
    try:
        # Get quotation
        quotation = store.get_quotation(quotation_id)

        # Create task
        task = ProcessingTask(
            task_type="generate_excel",
            status="pending",
            message="等待產出 Excel",
            quotation_id=quotation_id,
        )

        store.add_task(task)

        # Schedule export
        include_photos = request.include_photos if request else True
        photo_height_cm = request.photo_height_cm if request else 3.0

        if background_tasks:
            background_tasks.add_task(
                _export_excel_background,
                quotation_id=quotation_id,
                task_id=task.task_id,
                store=store,
                include_photos=include_photos,
                photo_height_cm=photo_height_cm,
            )

        return {
            "success": True,
            "message": "Excel 匯出任務已建立",
            "data": {
                "task_id": task.task_id,
                "status": task.status,
                "message": task.message,
            },
        }

    except Exception as e:
        log_error(e, context=f"Export Excel: {quotation_id}")
        raise


async def _export_excel_background(
    quotation_id: str,
    task_id: str,
    store: InMemoryStore,
    include_photos: bool = True,
    photo_height_cm: float = 3.0,
) -> None:
    """Background task for Excel export."""
    try:
        task = store.get_task(task_id)
        task.status = "processing"
        task.message = "正在產出 Excel..."
        task.update_progress(20, "正在產出 Excel...")
        store.update_task(task)

        # Get quotation
        quotation = store.get_quotation(quotation_id)

        # Generate Excel
        generator = get_excel_generator()
        excel_path = generator.create_quotation_excel(
            quotation,
            include_photos=include_photos,
            photo_height_cm=photo_height_cm,
        )

        task.update_progress(90, "正在驗證檔案...")

        # Validate
        generator.validate_excel_file(excel_path)

        # Update quotation
        quotation.export_status = "completed"
        quotation.export_path = excel_path
        store.update_quotation(quotation)

        # Complete task
        task.complete(result={
            "quotation_id": quotation_id,
            "file_path": excel_path,
            "file_size": len(open(excel_path, "rb").read()),
        })
        store.update_task(task)

        logger.info(f"Successfully exported quotation {quotation_id} to {excel_path}")

    except Exception as e:
        logger.error(f"Error exporting Excel for {quotation_id}: {e}")
        log_error(e, context=f"Export Excel: {quotation_id}")

        try:
            task = store.get_task(task_id)
            task.fail(str(e))
            store.update_task(task)

            quotation = store.get_quotation(quotation_id)
            quotation.export_status = "failed"
            quotation.export_error = str(e)
            store.update_quotation(quotation)
        except:
            pass


@router.get(
    "/export/{quotation_id}/download",
    summary="下載 Excel 檔案",
)
async def download_excel(
    quotation_id: str,
    store: StoreDep = Depends(),
):
    """下載已產出的 Excel 報價單檔案."""
    try:
        quotation = store.get_quotation(quotation_id)

        if quotation.export_status != "completed" or not quotation.export_path:
            return {
                "success": False,
                "message": "Excel 檔案尚未產出，請先執行匯出",
            }

        # Return file
        return FileResponse(
            path=quotation.export_path,
            filename=f"quotation_{quotation.title}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        log_error(e, context=f"Download Excel: {quotation_id}")
        raise
