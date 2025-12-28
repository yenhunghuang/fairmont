"""Upload API routes with auto-parsing."""

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ...api.dependencies import (
    get_file_manager,
    get_file_validator,
    get_store_dependency,
    validate_pdf_files,
)
from ...models import APIResponse, ProcessingTask, SourceDocument
from ...services.image_extractor import get_image_extractor
from ...services.image_matcher_deterministic import get_deterministic_image_matcher
from ...services.document_role_detector import get_document_role_detector_service
from ...services.pdf_parser import get_pdf_parser
from ...store import InMemoryStore
from ...utils import FileManager, FileValidator, log_error

logger = logging.getLogger(__name__)

# Gemini API 並發控制：限制同時解析的 PDF 數量，避免 API 限流
_parsing_semaphore = asyncio.Semaphore(2)

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
    store: InMemoryStore = Depends(get_store_dependency),
    file_manager: FileManager = Depends(get_file_manager),
    validator: FileValidator = Depends(get_file_validator),
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
                        _parse_pdf_background,
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


async def _parse_pdf_background(
    document_id: str,
    task_id: str,
    store: InMemoryStore,
    extract_images: bool = True,
    target_categories: list[str] | None = None,
) -> None:
    """背景任務：PDF 解析."""
    async with _parsing_semaphore:
        await _do_parse_pdf(document_id, task_id, store, extract_images, target_categories)


async def _do_parse_pdf(
    document_id: str,
    task_id: str,
    store: InMemoryStore,
    extract_images: bool = True,
    target_categories: list[str] | None = None,
) -> None:
    """實際執行 PDF 解析邏輯."""
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
    "/documents",
    response_model=APIResponse,
    summary="取得已上傳文件列表",
)
async def list_documents(
    limit: int = 20,
    status: str = None,
    store: InMemoryStore = Depends(get_store_dependency),
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
    store: InMemoryStore = Depends(get_store_dependency),
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
    store: InMemoryStore = Depends(get_store_dependency),
    file_manager: FileManager = Depends(get_file_manager),
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
    store: InMemoryStore = Depends(get_store_dependency),
    file_manager: FileManager = Depends(get_file_manager),
):
    """取得已提取的圖片檔案."""
    try:
        image = store.get_image(image_id)

        # Check if file exists
        if not file_manager.file_exists(image.file_path):
            raise HTTPException(
                status_code=404,
                detail="圖片檔案不存在",
            )

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

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, context=f"Get image: {image_id}")
        raise
