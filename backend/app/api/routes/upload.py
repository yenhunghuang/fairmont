"""Upload API routes."""

import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends
from datetime import datetime
import uuid

from ...models import SourceDocument, APIResponse
from ...api.dependencies import StoreDep, FileManagerDep, FileValidatorDep, validate_pdf_files
from ...services.pdf_parser import get_pdf_parser
from ...store import InMemoryStore
from ...utils import log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Upload"])


@router.post(
    "/upload",
    response_model=APIResponse,
    status_code=200,
    summary="上傳 PDF 檔案",
)
async def upload_files(
    files: List[UploadFile] = File(...),
    store: StoreDep = Depends(),
    file_manager: FileManagerDep = Depends(),
    validator: FileValidatorDep = Depends(),
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    上傳單一或多個 PDF 檔案.

    - **files**: PDF 檔案列表（最多 5 個，單檔最大 50MB）
    - 系統會建立 SourceDocument 記錄
    - 檔案自動解析任務將在背景執行
    """
    try:
        # Validate files
        validated_files = await validate_pdf_files(files)

        documents = []

        for filename, content in validated_files:
            try:
                # Save file
                file_path = file_manager.save_upload_file(content, filename)

                # Create document record
                doc = SourceDocument(
                    filename=filename,
                    file_path=file_path,
                    file_size=len(content),
                    document_type="unknown",  # Will be detected during parsing
                    parse_status="pending",
                )

                # Store document
                store.add_document(doc)
                documents.append(doc.model_dump())

                # Validate PDF structure
                parser = get_pdf_parser()
                try:
                    page_count, _ = parser.validate_pdf(file_path)
                    doc.total_pages = page_count
                    store.update_document(doc)
                except Exception as e:
                    doc.parse_status = "failed"
                    doc.parse_error = str(e)
                    store.update_document(doc)
                    log_error(e, context="PDF validation during upload")

            except Exception as e:
                logger.error(f"Failed to upload {filename}: {e}")
                log_error(e, context=f"File upload: {filename}")

        return {
            "success": True,
            "message": f"成功上傳 {len(documents)} 個檔案",
            "data": {"documents": documents},
        }

    except Exception as e:
        log_error(e, context="File upload")
        raise


@router.get(
    "/documents",
    response_model=APIResponse,
    summary="取得已上傳文件列表",
)
async def list_documents(
    limit: int = 20,
    status: str = None,
    store: StoreDep = Depends(),
) -> dict:
    """
    取得已上傳文件列表.

    - **limit**: 回傳數量限制（最多 100）
    - **status**: 篩選解析狀態（pending/processing/completed/failed）
    """
    try:
        documents = store.list_documents()

        # Filter by status if specified
        if status:
            documents = [doc for doc in documents if doc.parse_status == status]

        # Apply limit
        documents = documents[:limit]

        return {
            "success": True,
            "message": f"取得 {len(documents)} 個文件",
            "data": {
                "documents": [doc.model_dump() for doc in documents],
                "total": len(documents),
            },
        }

    except Exception as e:
        log_error(e, context="List documents")
        raise


@router.get(
    "/documents/{document_id}",
    response_model=APIResponse,
    summary="取得單一文件資訊",
)
async def get_document(
    document_id: str,
    store: StoreDep = Depends(),
) -> dict:
    """取得單一文件的詳細資訊."""
    try:
        document = store.get_document(document_id)
        return {
            "success": True,
            "message": "成功取得文件資訊",
            "data": document.model_dump(),
        }
    except Exception as e:
        log_error(e, context=f"Get document: {document_id}")
        raise


@router.delete(
    "/documents/{document_id}",
    response_model=APIResponse,
    summary="刪除文件",
)
async def delete_document(
    document_id: str,
    store: StoreDep = Depends(),
    file_manager: FileManagerDep = Depends(),
) -> dict:
    """刪除已上傳的文件及其相關資料."""
    try:
        document = store.get_document(document_id)

        # Delete file
        try:
            file_manager.delete_file(document.file_path)
        except Exception as e:
            logger.warning(f"Failed to delete file: {e}")

        # Delete from store
        store.delete_document(document_id)

        return {
            "success": True,
            "message": "文件已刪除",
            "data": None,
        }

    except Exception as e:
        log_error(e, context=f"Delete document: {document_id}")
        raise


@router.get(
    "/images/{image_id}",
    summary="取得提取的圖片",
)
async def get_image(
    image_id: str,
    store: StoreDep = Depends(),
    file_manager: FileManagerDep = Depends(),
):
    """取得已提取的圖片檔案."""
    try:
        image = store.get_image(image_id)

        # Serve image file
        if not file_manager.file_exists(image.file_path):
            return {
                "success": False,
                "message": "圖片檔案不存在",
            }

        # Return file as binary
        with open(image.file_path, "rb") as f:
            return f.read()

    except Exception as e:
        log_error(e, context=f"Get image: {image_id}")
        raise
