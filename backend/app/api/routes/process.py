"""Process API route - 單一整合端點.

提供簡化的 API 給前端：上傳 PDF → 返回 ProcessResponse（含 project_name + 17 欄 items）。
整合現有的 PDF 解析、數量總表解析、跨表合併、面料排序功能。
使用 skills yaml 配置來支援完整功能。

SSE 串流版本 (/process/stream) 提供即時進度更新。
"""

import asyncio
import logging
import uuid
from typing import AsyncGenerator, List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, Query
from fastapi.responses import StreamingResponse

from ...models import FairmontItemResponse, ProcessResponse, SourceDocument
from ...models.progress import (
    ProcessingStage,
    ProgressUpdate,
    ProgressDetail,
    ProgressCallback,
)
from ...utils.sse import format_progress_event, format_result_event, format_error_event
from ...api.dependencies import (
    get_store_dependency,
    get_file_manager,
    validate_pdf_files,
    verify_api_key,
)
from ...services.pdf_parser import get_pdf_parser
from ...services.image_extractor import get_image_extractor
from ...services.image_matcher_deterministic import get_deterministic_image_matcher
from ...services.document_role_detector import get_document_role_detector_service
from ...services.quantity_parser import get_quantity_parser_service
from ...services.merge_service import get_merge_service
from ...store import InMemoryStore
from ...utils import FileManager, log_error
from ...utils.document_type import detect_document_type_from_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Process"])


@router.post(
    "/process",
    response_model=ProcessResponse,
    status_code=200,
    summary="上傳 PDF 並返回 Fairmont 17 欄 JSON（含專案名稱）",
)
async def process_pdfs(
    files: List[UploadFile] = File(..., description="PDF 檔案（最多 5 個，單檔 ≤ 50MB）"),
    extract_images: bool = Query(True, description="是否提取圖片"),
    store: InMemoryStore = Depends(get_store_dependency),
    file_manager: FileManager = Depends(get_file_manager),
    api_key: str = Depends(verify_api_key),  # API Key 認證
) -> ProcessResponse:
    """
    上傳 PDF 檔案並返回 Fairmont 17 欄 JSON（含專案名稱）.

    這是一個同步整合端點，將上傳、解析、合併全部在一個請求中完成。
    支援跨表合併：自動識別數量總表與明細規格表，執行合併與面料排序。

    回傳結構：
    - **project_name**: 專案名稱（從 PDF 的 PROJECT 標題提取）
    - **items**: Fairmont 17 欄項目列表

    欄位說明（共 17 欄）：
    - 前 15 欄（no ~ brand）：對應 Excel 輸出格式
    - **category**: 分類（1=家具, 5=面料）— 用於關聯與排序
    - **affiliate**: 附屬 - 面料來源的家具編號，多個用 ', ' 分隔 — 用於關聯與排序

    - **files**: PDF 檔案列表（最多 5 個，單檔最大 50MB）
    - **extract_images**: 是否提取圖片（預設為 True）

    **注意**: 此端點為同步操作，處理時間約 1-6 分鐘（視 PDF 頁數而定）。
    前端應設定 timeout 為 360 秒（6 分鐘）以上。
    """
    try:
        # 1. 驗證檔案
        validated_files = await validate_pdf_files(files)
        logger.info(f"Validated {len(validated_files)} PDF files")

        # 2. 識別文件角色並儲存
        role_detector = get_document_role_detector_service()
        documents = []
        qty_doc = None
        detail_docs = []

        for upload_order, (filename, content) in enumerate(validated_files):
            file_path = file_manager.save_upload_file(content, filename)

            # 偵測文件角色（優先用檔名，失敗時掃描內容）
            document_role, role_detected_by = role_detector.detect_role_with_content(
                filename=filename,
                file_path=file_path,
            )

            doc = SourceDocument(
                filename=filename,
                file_path=file_path,
                file_size=len(content),
                document_type="unknown",
                parse_status="pending",
                document_role=document_role,
                upload_order=upload_order,
                role_detected_by=role_detected_by,
            )

            # 驗證 PDF 頁數
            parser = get_pdf_parser()
            page_count, _ = parser.validate_pdf(file_path)
            doc.total_pages = page_count

            store.add_document(doc)
            documents.append(doc)

            if document_role == "quantity_summary":
                qty_doc = doc
            else:
                detail_docs.append(doc)

        logger.info(
            f"Document roles: {len(detail_docs)} detail specs, "
            f"{'1 quantity summary' if qty_doc else 'no quantity summary'}"
        )

        # 3. 解析明細規格表（Gemini AI）
        detail_boq_items = []
        total_images = 0
        matched_images = 0
        collected_project_name: Optional[str] = None

        for doc in detail_docs:
            doc.parse_status = "processing"
            store.update_document(doc)

            logger.info(f"Parsing detail spec: {doc.filename} ({doc.total_pages} pages)")

            boq_items, _, project_metadata = await parser.parse_boq_with_gemini(
                file_path=doc.file_path,
                document_id=doc.id,
                extract_images=extract_images,
            )

            # 儲存專案名稱（取第一個找到的）
            if project_metadata:
                doc.project_name = project_metadata.get("project_name")
                if doc.project_name and not collected_project_name:
                    collected_project_name = doc.project_name

            # 圖片提取和匹配
            if extract_images and boq_items:
                extractor = get_image_extractor()
                images_with_bytes = extractor.extract_images_with_bytes(
                    doc.file_path, doc.id
                )
                total_images += len(images_with_bytes)

                if images_with_bytes:
                    document_type = detect_document_type_from_filename(doc.filename)
                    matcher = get_deterministic_image_matcher(vendor_id="habitus")
                    page_offset = matcher.get_page_offset(document_type)

                    image_to_item_map = await matcher.match_images_to_items(
                        images_with_bytes,
                        boq_items,
                        target_page_offset=page_offset,
                    )

                    for img_idx, item_id in image_to_item_map.items():
                        if img_idx < len(images_with_bytes):
                            img_data = images_with_bytes[img_idx]
                            base64_str = extractor._convert_to_base64(img_data["bytes"])

                            item = next((i for i in boq_items if i.id == item_id), None)
                            if item:
                                item.photo_base64 = base64_str
                                matched_images += 1

            doc.parse_status = "completed"
            doc.extracted_items_count = len(boq_items)
            store.update_document(doc)

            detail_boq_items.append(boq_items)
            logger.info(f"Parsed {len(boq_items)} items from {doc.filename}")

        # 4. 解析數量總表（如果有）
        qty_items = []
        if qty_doc:
            logger.info(f"Parsing quantity summary: {qty_doc.filename}")
            qty_parser = get_quantity_parser_service(vendor_id="habitus")
            qty_items = await qty_parser.parse_quantity_summary(
                qty_doc.file_path, qty_doc.id
            )
            logger.info(f"Parsed {len(qty_items)} quantity items")

        # 5. 跨表合併（使用 skills 配置）
        quotation_id = str(uuid.uuid4())
        merge_service = get_merge_service()

        merged_items, merge_report = merge_service.merge_documents(
            quantity_summary_items=qty_items,
            detail_boq_items=detail_boq_items,
            quantity_summary_doc=qty_doc,
            detail_spec_docs=detail_docs,
            quotation_id=quotation_id,
        )

        logger.info(
            f"Merge completed: {len(merged_items)} items, "
            f"matched={merge_report.matched_items}, "
            f"match_rate={merge_report.get_match_rate():.1%}"
        )

        # 6. 轉換為 Fairmont 17 欄 DTO
        items_response = [
            FairmontItemResponse.from_boq_item(item)
            for item in merged_items
        ]

        # 7. 記錄統計資訊（僅供 log，不回傳）
        logger.info(
            f"Process completed: {len(merged_items)} items, "
            f"{matched_images}/{total_images} images matched, "
            f"qty match rate: {merge_report.get_match_rate():.1%}"
        )

        # 返回 ProcessResponse（含 project_name 與 items）
        return ProcessResponse(
            project_name=collected_project_name,
            items=items_response,
        )

    except Exception as e:
        log_error(e, context="Process PDFs")
        raise


@router.post(
    "/process/stream",
    status_code=200,
    summary="上傳 PDF 並透過 SSE 串流返回進度與結果",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE 事件串流",
            "content": {"text/event-stream": {}},
        },
    },
)
async def process_pdfs_stream(
    files: List[UploadFile] = File(..., description="PDF 檔案（最多 5 個，單檔 ≤ 50MB）"),
    extract_images: bool = Query(True, description="是否提取圖片"),
    store: InMemoryStore = Depends(get_store_dependency),
    file_manager: FileManager = Depends(get_file_manager),
    api_key: str = Depends(verify_api_key),
) -> StreamingResponse:
    """
    上傳 PDF 檔案並透過 SSE 串流返回進度與結果.

    這是 /process 的串流版本，支援即時進度更新。

    **SSE 事件類型**：
    - `progress`: 進度更新 `{stage, progress, message, detail?}`
    - `result`: 處理完成 `{project_name, items[], statistics}`
    - `error`: 錯誤 `{code, message, stage?}`

    **進度階段 (stage)**:
    - validating (0-5%): 檔案驗證
    - detecting_roles (5-10%): 文件角色偵測
    - parsing_detail_specs (10-70%): 明細規格表解析
    - parsing_quantity_summary (70-85%): 數量總表解析
    - merging (85-95%): 跨表合併
    - converting (95-99%): 格式轉換
    - completed (100%): 完成

    **注意**: Swagger UI 不支援 SSE 串流顯示，請使用 curl 或前端測試：
    ```
    curl -N -H "Authorization: Bearer <API_KEY>" \\
         -F "files=@test.pdf" \\
         http://localhost:8000/api/v1/process/stream
    ```
    """
    # 使用 asyncio.Queue 傳遞進度更新
    progress_queue: asyncio.Queue[Optional[ProgressUpdate]] = asyncio.Queue()

    async def emit_progress(update: ProgressUpdate) -> None:
        """進度回調，將更新放入佇列."""
        await progress_queue.put(update)

    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE 事件生成器."""
        current_stage = ProcessingStage.VALIDATING

        # 啟動處理任務
        process_task = asyncio.create_task(
            _process_with_progress(
                files=files,
                extract_images=extract_images,
                store=store,
                file_manager=file_manager,
                progress_callback=emit_progress,
            )
        )

        result = None
        error = None

        try:
            while True:
                # 同時監聽進度佇列和處理任務
                get_progress_task = asyncio.create_task(progress_queue.get())

                done, pending = await asyncio.wait(
                    [get_progress_task, process_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # 取消未完成的 get_progress_task（如果 process_task 先完成）
                if get_progress_task in pending:
                    get_progress_task.cancel()
                    try:
                        await get_progress_task
                    except asyncio.CancelledError:
                        pass

                # 處理完成的任務
                for task in done:
                    if task is process_task:
                        # 處理任務完成
                        if process_task.exception():
                            error = process_task.exception()
                        else:
                            result = process_task.result()
                    elif task is get_progress_task:
                        # 收到進度更新
                        try:
                            update = task.result()
                            if update:
                                current_stage = update.stage
                                yield format_progress_event(update)
                        except asyncio.CancelledError:
                            pass

                # 如果處理任務完成，跳出迴圈
                if process_task.done():
                    # 先把佇列中剩餘的進度更新發出
                    while not progress_queue.empty():
                        try:
                            update = progress_queue.get_nowait()
                            if update:
                                yield format_progress_event(update)
                        except asyncio.QueueEmpty:
                            break
                    break

        except Exception as e:
            error = e

        # 發送最終事件
        if error:
            error_code = getattr(error, "error_code", "INTERNAL_ERROR")
            yield format_error_event(
                code=str(error_code),
                message=str(error),
                stage=current_stage.value if current_stage else None,
            )
        elif result:
            yield format_result_event(
                project_name=result["project_name"],
                items=result["items"],
                statistics=result["statistics"],
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 緩衝
        },
    )


async def _process_with_progress(
    files: List[UploadFile],
    extract_images: bool,
    store: InMemoryStore,
    file_manager: FileManager,
    progress_callback: ProgressCallback,
) -> dict:
    """
    執行處理流程，並在每個階段發送進度更新.

    Returns:
        包含 project_name, items, statistics 的字典
    """
    # 1. 驗證檔案 (0-5%)
    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.VALIDATING,
            progress=0,
            message="正在驗證檔案...",
        )
    )

    validated_files = await validate_pdf_files(files)

    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.VALIDATING,
            progress=5,
            message=f"已驗證 {len(validated_files)} 個檔案",
        )
    )

    # 2. 識別文件角色 (5-10%)
    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.DETECTING_ROLES,
            progress=5,
            message="正在識別文件角色...",
        )
    )

    role_detector = get_document_role_detector_service()
    documents = []
    qty_doc = None
    detail_docs = []
    parser = get_pdf_parser()

    for upload_order, (filename, content) in enumerate(validated_files):
        file_path = file_manager.save_upload_file(content, filename)

        # 偵測文件角色（優先用檔名，失敗時掃描內容）
        document_role, role_detected_by = role_detector.detect_role_with_content(
            filename=filename,
            file_path=file_path,
        )

        doc = SourceDocument(
            filename=filename,
            file_path=file_path,
            file_size=len(content),
            document_type="unknown",
            parse_status="pending",
            document_role=document_role,
            upload_order=upload_order,
            role_detected_by=role_detected_by,
        )

        page_count, _ = parser.validate_pdf(file_path)
        doc.total_pages = page_count

        store.add_document(doc)
        documents.append(doc)

        if document_role == "quantity_summary":
            qty_doc = doc
        else:
            detail_docs.append(doc)

    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.DETECTING_ROLES,
            progress=10,
            message=f"識別完成：{len(detail_docs)} 份明細規格表"
            + ("，1 份數量總表" if qty_doc else ""),
        )
    )

    # 3. 解析明細規格表 (10-70%)
    detail_boq_items = []
    total_images = 0
    matched_images = 0
    collected_project_name: Optional[str] = None
    total_detail_docs = len(detail_docs)

    for idx, doc in enumerate(detail_docs):
        base_progress = 10 + int((idx / max(total_detail_docs, 1)) * 60)

        await progress_callback(
            ProgressUpdate(
                stage=ProcessingStage.PARSING_DETAIL_SPECS,
                progress=base_progress,
                message=f"正在解析明細規格表 ({idx + 1}/{total_detail_docs})...",
                detail=ProgressDetail(
                    current_file=doc.filename,
                    current_file_index=idx,
                    total_files=total_detail_docs,
                ),
            )
        )

        doc.parse_status = "processing"
        store.update_document(doc)

        boq_items, _, project_metadata = await parser.parse_boq_with_gemini(
            file_path=doc.file_path,
            document_id=doc.id,
            extract_images=extract_images,
        )

        if project_metadata:
            doc.project_name = project_metadata.get("project_name")
            if doc.project_name and not collected_project_name:
                collected_project_name = doc.project_name

        # 圖片提取和匹配
        if extract_images and boq_items:
            extractor = get_image_extractor()
            images_with_bytes = extractor.extract_images_with_bytes(doc.file_path, doc.id)
            total_images += len(images_with_bytes)

            if images_with_bytes:
                document_type = detect_document_type_from_filename(doc.filename)
                matcher = get_deterministic_image_matcher(vendor_id="habitus")
                page_offset = matcher.get_page_offset(document_type)

                image_to_item_map = await matcher.match_images_to_items(
                    images_with_bytes,
                    boq_items,
                    target_page_offset=page_offset,
                )

                for img_idx, item_id in image_to_item_map.items():
                    if img_idx < len(images_with_bytes):
                        img_data = images_with_bytes[img_idx]
                        base64_str = extractor._convert_to_base64(img_data["bytes"])

                        item = next((i for i in boq_items if i.id == item_id), None)
                        if item:
                            item.photo_base64 = base64_str
                            matched_images += 1

        doc.parse_status = "completed"
        doc.extracted_items_count = len(boq_items)
        store.update_document(doc)

        detail_boq_items.append(boq_items)

        await progress_callback(
            ProgressUpdate(
                stage=ProcessingStage.PARSING_DETAIL_SPECS,
                progress=10 + int(((idx + 1) / max(total_detail_docs, 1)) * 60),
                message=f"已解析 {len(boq_items)} 個項目",
                detail=ProgressDetail(
                    current_file=doc.filename,
                    current_file_index=idx,
                    total_files=total_detail_docs,
                    items_parsed=len(boq_items),
                ),
            )
        )

    # 4. 解析數量總表 (70-85%)
    qty_items = []
    if qty_doc:
        await progress_callback(
            ProgressUpdate(
                stage=ProcessingStage.PARSING_QUANTITY_SUMMARY,
                progress=70,
                message="正在解析數量總表...",
                detail=ProgressDetail(current_file=qty_doc.filename),
            )
        )

        qty_parser = get_quantity_parser_service(vendor_id="habitus")
        qty_items = await qty_parser.parse_quantity_summary(qty_doc.file_path, qty_doc.id)

        await progress_callback(
            ProgressUpdate(
                stage=ProcessingStage.PARSING_QUANTITY_SUMMARY,
                progress=85,
                message=f"已解析 {len(qty_items)} 個數量項目",
            )
        )
    else:
        await progress_callback(
            ProgressUpdate(
                stage=ProcessingStage.PARSING_QUANTITY_SUMMARY,
                progress=85,
                message="無數量總表，跳過",
            )
        )

    # 5. 跨表合併 (85-95%)
    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.MERGING,
            progress=85,
            message="正在執行跨表合併...",
        )
    )

    quotation_id = str(uuid.uuid4())
    merge_service = get_merge_service()

    merged_items, merge_report = merge_service.merge_documents(
        quantity_summary_items=qty_items,
        detail_boq_items=detail_boq_items,
        quantity_summary_doc=qty_doc,
        detail_spec_docs=detail_docs,
        quotation_id=quotation_id,
    )

    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.MERGING,
            progress=95,
            message=f"合併完成，配對率 {merge_report.get_match_rate():.1%}",
        )
    )

    # 6. DTO 轉換 (95-99%)
    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.CONVERTING,
            progress=95,
            message="正在轉換輸出格式...",
        )
    )

    items_response = [FairmontItemResponse.from_boq_item(item) for item in merged_items]

    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.CONVERTING,
            progress=99,
            message=f"已轉換 {len(items_response)} 個項目",
        )
    )

    # 7. 完成 (100%)
    await progress_callback(
        ProgressUpdate(
            stage=ProcessingStage.COMPLETED,
            progress=100,
            message="處理完成",
        )
    )

    # 統計資訊
    furniture_count = sum(1 for item in merged_items if item.category == 1)
    fabric_count = sum(1 for item in merged_items if item.category == 5)

    return {
        "project_name": collected_project_name,
        "items": [item.model_dump(mode="json") for item in items_response],
        "statistics": {
            "total_items": len(merged_items),
            "furniture_count": furniture_count,
            "fabric_count": fabric_count,
            "images_matched": matched_images,
            "merge_match_rate": merge_report.get_match_rate(),
        },
    }
