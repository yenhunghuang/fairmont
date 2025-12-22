"""Google Sheets export API routes."""

import logging
from typing import Literal
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...models import ProcessingTask, APIResponse
from ...api.dependencies import get_store_dependency
from ...services.google_sheets_generator import get_google_sheets_generator
from ...store import InMemoryStore
from ...config import settings
from ...utils import log_error, ErrorCode, raise_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Google Sheets Export"])


class ExportSheetsRequest(BaseModel):
    """Request model for Google Sheets export."""

    include_photos: bool = True
    share_mode: Literal["view", "edit"] = "view"


class GoogleSheetsResponse(BaseModel):
    """Response model for Google Sheets result."""

    spreadsheet_id: str
    spreadsheet_url: str
    shareable_link: str
    image_count: int = 0


@router.post(
    "/quotations/{quotation_id}/sheets",
    status_code=202,
    response_model=APIResponse,
    summary="匯出至 Google Sheets",
)
async def export_to_google_sheets(
    quotation_id: str,
    request: ExportSheetsRequest,
    background_tasks: BackgroundTasks,
    store: InMemoryStore = Depends(get_store_dependency),
) -> JSONResponse:
    """
    匯出報價單至 Google Sheets（背景任務）.

    - **include_photos**: 是否上傳圖片至 Google Drive
    - **share_mode**: "view" 僅檢視 / "edit" 可編輯

    回傳 202 Accepted，客戶端應輪詢 `/tasks/{task_id}` 取得結果。
    完成後，task.result 包含 spreadsheet_url 和 shareable_link。
    """
    try:
        # Check if Google Sheets is available
        if not settings.google_sheets_available:
            raise_error(
                ErrorCode.GOOGLE_SHEETS_DISABLED,
                "Google Sheets 整合未啟用，請設定 GOOGLE_CREDENTIALS_PATH 和 GOOGLE_SHEETS_ENABLED",
                status_code=503,
            )

        # Get quotation
        quotation = store.get_quotation(quotation_id)

        # If already generating, return 202 with existing task info
        if quotation.sheets_status == "generating":
            return JSONResponse(
                status_code=202,
                content={
                    "success": False,
                    "message": "Google Sheets 正在產出中，請稍後重試",
                    "data": {
                        "status": "generating",
                        "quotation_id": quotation_id,
                    },
                },
            )

        # If already completed, return the existing link
        if quotation.sheets_status == "completed" and quotation.sheets_shareable_link:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Google Sheets 已產生",
                    "data": {
                        "spreadsheet_id": quotation.sheets_spreadsheet_id,
                        "spreadsheet_url": quotation.sheets_url,
                        "shareable_link": quotation.sheets_shareable_link,
                        "status": "completed",
                    },
                },
            )

        # Create task
        task = ProcessingTask(
            task_type="generate_sheets",
            status="pending",
            message="等待產出 Google Sheets",
            quotation_id=quotation_id,
        )

        store.add_task(task)

        # Schedule export
        background_tasks.add_task(
            _export_sheets_background,
            quotation_id=quotation_id,
            task_id=task.task_id,
            store=store,
            include_photos=request.include_photos,
            share_mode=request.share_mode,
        )

        # Update quotation status
        quotation.sheets_status = "generating"
        store.update_quotation(quotation)

        return JSONResponse(
            status_code=202,
            content={
                "success": False,
                "message": "Google Sheets 產出已啟動",
                "data": {
                    "task_id": task.task_id,
                    "status": "generating",
                    "quotation_id": quotation_id,
                },
            },
        )

    except Exception as e:
        log_error(e, context=f"Export to Google Sheets: {quotation_id}")
        raise


@router.get(
    "/quotations/{quotation_id}/sheets",
    response_model=APIResponse,
    summary="取得 Google Sheets 連結",
)
async def get_google_sheets_link(
    quotation_id: str,
    store: InMemoryStore = Depends(get_store_dependency),
) -> dict:
    """
    取得已產生的 Google Sheets 連結.

    如果尚未產生，請先使用 POST 端點觸發產出。
    """
    try:
        quotation = store.get_quotation(quotation_id)

        if quotation.sheets_status == "completed" and quotation.sheets_shareable_link:
            return {
                "success": True,
                "message": "成功取得 Google Sheets 連結",
                "data": {
                    "spreadsheet_id": quotation.sheets_spreadsheet_id,
                    "spreadsheet_url": quotation.sheets_url,
                    "shareable_link": quotation.sheets_shareable_link,
                    "status": "completed",
                },
            }

        if quotation.sheets_status == "generating":
            return JSONResponse(
                status_code=202,
                content={
                    "success": False,
                    "message": "Google Sheets 正在產出中",
                    "data": {
                        "status": "generating",
                        "quotation_id": quotation_id,
                    },
                },
            )

        if quotation.sheets_status == "failed":
            return {
                "success": False,
                "message": f"Google Sheets 產出失敗：{quotation.sheets_error}",
                "data": {
                    "status": "failed",
                    "error": quotation.sheets_error,
                },
            }

        # Not yet generated
        return {
            "success": False,
            "message": "Google Sheets 尚未產生，請使用 POST 端點啟動產出",
            "data": {
                "status": "pending",
            },
        }

    except Exception as e:
        log_error(e, context=f"Get Google Sheets link: {quotation_id}")
        raise


@router.get(
    "/sheets/status",
    response_model=APIResponse,
    summary="檢查 Google Sheets 整合狀態",
)
async def check_sheets_status() -> dict:
    """
    檢查 Google Sheets 整合是否可用.

    回傳 Google Sheets 功能的啟用狀態。
    """
    return {
        "success": True,
        "message": "Google Sheets 狀態已檢查",
        "data": {
            "enabled": settings.google_sheets_enabled,
            "available": settings.google_sheets_available,
            "credentials_configured": bool(settings.google_credentials_path),
        },
    }


async def _export_sheets_background(
    quotation_id: str,
    task_id: str,
    store: InMemoryStore,
    include_photos: bool = True,
    share_mode: Literal["view", "edit"] = "view",
) -> None:
    """Background task for Google Sheets export."""
    try:
        task = store.get_task(task_id)
        task.status = "processing"
        task.message = "正在產出 Google Sheets..."
        task.update_progress(10, "正在產出 Google Sheets...")
        store.update_task(task)

        # Get quotation
        quotation = store.get_quotation(quotation_id)

        task.update_progress(20, "正在建立試算表...")

        # Generate Google Sheets
        generator = get_google_sheets_generator()
        result = generator.create_quotation_sheet(
            quotation,
            include_photos=include_photos,
            share_mode=share_mode,
        )

        task.update_progress(90, "正在設定分享權限...")

        # Update quotation with Sheets info
        quotation.sheets_status = "completed"
        quotation.sheets_spreadsheet_id = result.spreadsheet_id
        quotation.sheets_url = result.spreadsheet_url
        quotation.sheets_shareable_link = result.shareable_link
        quotation.sheets_drive_folder_id = result.drive_folder_id
        store.update_quotation(quotation)

        # Complete task
        task.complete(
            result={
                "quotation_id": quotation_id,
                "spreadsheet_id": result.spreadsheet_id,
                "spreadsheet_url": result.spreadsheet_url,
                "shareable_link": result.shareable_link,
                "image_count": result.image_count,
            }
        )
        store.update_task(task)

        logger.info(
            f"Successfully exported quotation {quotation_id} to Google Sheets: {result.spreadsheet_url}"
        )

    except Exception as e:
        logger.error(f"Error exporting Google Sheets for {quotation_id}: {e}")
        log_error(e, context=f"Export Google Sheets: {quotation_id}")

        try:
            task = store.get_task(task_id)
            task.fail(str(e))
            store.update_task(task)

            quotation = store.get_quotation(quotation_id)
            quotation.sheets_status = "failed"
            quotation.sheets_error = str(e)
            store.update_quotation(quotation)
        except Exception:
            pass
