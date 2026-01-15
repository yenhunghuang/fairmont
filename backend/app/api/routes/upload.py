"""Upload API routes with auto-parsing."""

import logging

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile
from fastapi.responses import FileResponse

from ...api.dependencies import (
    FileManagerDep,
    FileValidatorDep,
    StoreDep,
    validate_pdf_files,
)
from ...models import APIResponse, ProcessingTask, SourceDocument
from ...services.document_role_detector import get_document_role_detector_service
from ...services.parsing_service import parse_pdf_background
from ...services.pdf_parser import get_pdf_parser
from ...utils import log_error, raise_error, ErrorCode, APIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Upload"])


@router.post(
    "/documents",
    response_model=APIResponse,
    status_code=201,
    summary="上傳 PDF 檔案並自動解析",
)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    extract_images: bool = Query(True, description="是否提取圖片"),
    *,
    store: StoreDep,
    file_manager: FileManagerDep,
    validator: FileValidatorDep,
) -> dict:
    """
    上傳單一或多個 PDF 檔案，並自動啟動解析.

    - **files**: PDF 檔案列表（最多 5 個，單檔最大 50MB）
    - **extract_images**: 是否提取圖片（預設為 True）
    - 系統會建立 SourceDocument 記錄並自動啟動解析任務
    - 返回 documents 和 parse_tasks，前端可直接輪詢 task_id
    """
    try:
        # Validate files
        validated_files = await validate_pdf_files(files)

        documents = []
        parse_tasks = []

        # Get document role detector service
        role_detector = get_document_role_detector_service()

        for upload_order, (filename, content) in enumerate(validated_files):
            try:
                # Save file
                file_path = file_manager.save_upload_file(content, filename)

                # Detect document role from filename
                document_role, role_detected_by = role_detector.detect_role(filename)

                # Create document record
                doc = SourceDocument(
                    filename=filename,
                    file_path=file_path,
                    file_size=len(content),
                    document_type="unknown",  # Will be detected during parsing
                    parse_status="pending",
                    document_role=document_role,
                    upload_order=upload_order,
                    role_detected_by=role_detected_by,
                )

                # Store document
                store.add_document(doc)

                # Validate PDF structure
                parser = get_pdf_parser()
                try:
                    page_count, _ = parser.validate_pdf(file_path)
                    doc.total_pages = page_count
                    store.update_document(doc)

                    # 數量總表跳過 BOQ 解析（會在合併時由 quantity_parser 處理）
                    if document_role == "quantity_summary":
                        doc.parse_status = "completed"
                        doc.parse_message = "數量總表，跳過 BOQ 解析"
                        store.update_document(doc)
                        logger.info(f"Skipping BOQ parsing for quantity summary: {filename}")

                        # 建立一個已完成的假任務供前端追蹤
                        task = ProcessingTask(
                            task_type="parse_pdf",
                            status="completed",
                            message="數量總表已就緒",
                            document_id=doc.id,
                            progress=100,
                        )
                        store.add_task(task)

                        parse_tasks.append({
                            "document_id": doc.id,
                            "task_id": task.task_id,
                            "status": task.status,
                        })
                        # 數量總表也要加入 documents 列表！
                        documents.append(doc.model_dump())
                        continue

                    # 自動建立並啟動解析任務（僅限明細規格表）
                    task = ProcessingTask(
                        task_type="parse_pdf",
                        status="pending",
                        message="等待處理",
                        document_id=doc.id,
                    )
                    store.add_task(task)

                    # 排程背景解析任務
                    background_tasks.add_task(
                        parse_pdf_background,
                        document_id=doc.id,
                        task_id=task.task_id,
                        store=store,
                        extract_images=extract_images,
                    )

                    parse_tasks.append({
                        "document_id": doc.id,
                        "task_id": task.task_id,
                        "status": task.status,
                    })

                except Exception as e:
                    doc.parse_status = "failed"
                    doc.parse_error = str(e)
                    store.update_document(doc)
                    log_error(e, context="PDF validation during upload")

                documents.append(doc.model_dump())

            except Exception as e:
                logger.error(f"Failed to upload {filename}: {e}")
                log_error(e, context=f"File upload: {filename}")

        return {
            "success": True,
            "message": f"成功上傳 {len(documents)} 個檔案，已自動啟動解析",
            "data": {
                "documents": documents,
                "parse_tasks": parse_tasks,
            },
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
    status: str | None = None,
    *,
    store: StoreDep,
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
    *,
    store: StoreDep,
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
    *,
    store: StoreDep,
    file_manager: FileManagerDep,
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
    responses={
        200: {
            "content": {"image/*": {}},
            "description": "圖片檔案",
        },
        404: {
            "description": "找不到圖片",
        },
    },
)
async def get_image(
    image_id: str,
    *,
    store: StoreDep,
    file_manager: FileManagerDep,
):
    """取得已提取的圖片檔案."""
    try:
        image = store.get_image(image_id)

        # Check if file exists
        if not file_manager.file_exists(image.file_path):
            raise_error(ErrorCode.FILE_NOT_FOUND, "圖片檔案不存在", status_code=404)

        # Determine media type from image format
        media_type_map = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }
        media_type = media_type_map.get(image.format.lower(), f"image/{image.format}")

        # Return file with proper headers
        return FileResponse(
            path=image.file_path,
            media_type=media_type,
            filename=image.filename,
        )

    except APIError:
        raise
    except Exception as e:
        log_error(e, context=f"Get image: {image_id}")
        raise
