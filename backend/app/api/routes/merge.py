"""Merge API routes for cross-document merging.

跨表合併 API 端點，支援多 PDF 合併產出報價單。
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ...models import (
    APIResponse,
    Quotation,
    ProcessingTask,
    MergeReport,
)
from ...api.dependencies import StoreDep
from ...services.merge_service import get_merge_service
from ...store import InMemoryStore
from ...services.quantity_parser import get_quantity_parser_service
from ...utils import ErrorCode, raise_error, log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Merge"])


# ============================================================================
# Request/Response Models
# ============================================================================


class MergeRequest(BaseModel):
    """跨表合併請求."""

    document_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="要合併的文件 ID 列表",
    )
    title: Optional[str] = Field(None, description="報價單標題")


class MergeReportResponse(BaseModel):
    """合併報告回應 DTO."""

    id: str
    quotation_id: str
    quantity_summary_filename: Optional[str]
    detail_spec_filenames: List[str]
    total_items: int
    matched_items: int
    unmatched_items: int
    quantity_only_items: int
    match_rate: float
    warnings: List[str]
    processing_time_ms: int

    @classmethod
    def from_merge_report(cls, report: MergeReport) -> "MergeReportResponse":
        """從 MergeReport 建立 DTO."""
        return cls(
            id=report.id,
            quotation_id=report.quotation_id,
            quantity_summary_filename=report.quantity_summary_filename,
            detail_spec_filenames=report.detail_spec_filenames,
            total_items=report.total_items,
            matched_items=report.matched_items,
            unmatched_items=report.unmatched_items,
            quantity_only_items=report.quantity_only_items,
            match_rate=report.get_match_rate(),
            warnings=report.warnings,
            processing_time_ms=report.processing_time_ms,
        )


# ============================================================================
# API Routes
# ============================================================================


@router.post(
    "/quotations/merge",
    response_model=APIResponse,
    status_code=202,
    summary="建立跨表合併報價單",
)
async def create_merged_quotation(
    request: MergeRequest,
    background_tasks: BackgroundTasks,
    *,
    store: StoreDep,
) -> dict:
    """
    從多個文件建立跨表合併報價單.

    - **document_ids**: 要合併的文件 ID 列表（需包含已解析完成的 PDF）
    - **title**: 報價單標題（選填）

    系統會自動識別數量總表與明細規格表，執行跨表合併，產出單一報價單。
    """
    try:
        # 取得所有文件
        documents = []
        for doc_id in request.document_ids:
            try:
                doc = store.get_document(doc_id)
                documents.append(doc)
            except Exception:
                raise_error(
                    ErrorCode.DOCUMENT_NOT_FOUND,
                    f"文件 {doc_id} 不存在",
                    status_code=404,
                )

        # 驗證合併請求（先識別文件角色）
        merge_service = get_merge_service()
        is_valid, error_msg, qty_doc, detail_docs = merge_service.validate_merge_request(
            documents
        )

        if not is_valid:
            raise_error(ErrorCode.MERGE_FAILED, error_msg, status_code=400)

        # 驗證明細規格表是否已解析完成
        # 注意：數量總表不需要經過 pdf_parser 解析，會在合併時由 quantity_parser 處理
        for doc in detail_docs:
            if doc.parse_status != "completed":
                raise_error(
                    ErrorCode.PROCESSING_FAILED,
                    f"明細規格表 {doc.filename} 尚未解析完成",
                    status_code=400,
                )

        # 建立報價單
        quotation = Quotation(
            title=request.title or "跨表合併報價單",
            source_document_ids=request.document_ids,
        )
        store.add_quotation(quotation)

        # 建立合併任務
        task = ProcessingTask(
            task_type="merge_documents",
            status="pending",
            message="等待處理",
            quotation_id=quotation.id,
        )
        store.add_task(task)

        # 排程背景合併任務
        background_tasks.add_task(
            _merge_documents_background,
            quotation_id=quotation.id,
            task_id=task.task_id,
            qty_doc_id=qty_doc.id if qty_doc else None,
            detail_doc_ids=[d.id for d in detail_docs],
            store=store,
        )

        return {
            "success": True,
            "message": "已開始跨表合併處理",
            "data": {
                "quotation_id": quotation.id,
                "task_id": task.task_id,
                "status": task.status,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, context="Create merged quotation")
        raise


async def _merge_documents_background(
    quotation_id: str,
    task_id: str,
    qty_doc_id: Optional[str],
    detail_doc_ids: List[str],
    store: InMemoryStore,
) -> None:
    """背景任務：執行跨表合併."""
    try:
        # 取得任務並更新狀態
        task = store.get_task(task_id)
        task.status = "processing"
        task.message = "正在準備合併..."
        task.update_progress(10, "正在準備合併...")
        store.update_task(task)

        # 取得數量總表
        qty_items = []
        qty_doc = None
        if qty_doc_id:
            qty_doc = store.get_document(qty_doc_id)
            task.update_progress(20, "正在解析數量總表...")
            store.update_task(task)

            # 解析數量總表（使用 habitus vendor skill）
            qty_parser = get_quantity_parser_service(vendor_id="habitus")
            qty_items = await qty_parser.parse_quantity_summary(
                qty_doc.file_path, qty_doc.id
            )

        # 取得明細規格表 BOQ 項目
        detail_docs = []
        detail_boq_items = []
        for doc_id in detail_doc_ids:
            doc = store.get_document(doc_id)
            detail_docs.append(doc)

            # 取得該文件的 BOQ 項目
            items = store.get_items_by_document(doc_id)
            detail_boq_items.append(items)

        task.update_progress(50, "正在執行跨表合併...")
        store.update_task(task)

        # 執行合併
        merge_service = get_merge_service()
        merged_items, report = merge_service.merge_documents(
            quantity_summary_items=qty_items,
            detail_boq_items=detail_boq_items,
            quantity_summary_doc=qty_doc,
            detail_spec_docs=detail_docs,
            quotation_id=quotation_id,
        )

        task.update_progress(80, "正在儲存結果...")
        store.update_task(task)

        # 儲存合併報告
        store.add_merge_report(report)

        # 更新報價單
        quotation = store.get_quotation(quotation_id)
        quotation.items = merged_items

        # 設定 project_name（優先從明細規格表取得）
        for doc in detail_docs:
            if doc.project_name:
                quotation.project_name = doc.project_name
                break
        # 若明細表沒有，嘗試從數量總表取得
        if not quotation.project_name and qty_doc and qty_doc.project_name:
            quotation.project_name = qty_doc.project_name

        quotation.update_statistics()
        store.update_quotation(quotation)

        # 完成任務
        task.complete(
            result={
                "quotation_id": quotation_id,
                "merge_report_id": report.id,
                "items_count": len(merged_items),
                "matched_count": report.matched_items,
                "unmatched_count": report.unmatched_items,
                "match_rate": report.get_match_rate(),
            }
        )
        store.update_task(task)

        logger.info(
            f"Merge completed: quotation={quotation_id}, "
            f"items={len(merged_items)}, matched={report.matched_items}"
        )

    except Exception as e:
        logger.error(f"Error merging documents: {e}")
        log_error(e, context=f"Merge documents: {quotation_id}")

        try:
            task = store.get_task(task_id)
            task.fail(str(e))
            store.update_task(task)
        except Exception as inner_e:
            logger.error(f"Failed to update task status: {inner_e}")


@router.get(
    "/quotations/{quotation_id}/merge-report",
    response_model=APIResponse,
    summary="取得合併報告",
)
async def get_merge_report(
    quotation_id: str,
    *,
    store: StoreDep,
) -> dict:
    """
    取得報價單的跨表合併報告.

    返回合併統計、配對率、未匹配項目、格式警告等資訊。
    """
    try:
        # 確認報價單存在
        store.get_quotation(quotation_id)

        # 取得合併報告
        report = store.get_merge_report_by_quotation(quotation_id)
        if not report:
            raise_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                "此報價單沒有合併報告",
                status_code=404,
            )

        return {
            "success": True,
            "message": "成功取得合併報告",
            "data": MergeReportResponse.from_merge_report(report).model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, context=f"Get merge report: {quotation_id}")
        raise
