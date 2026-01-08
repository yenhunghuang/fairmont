"""Process API route - 單一整合端點.

提供簡化的 API 給前端：上傳 PDF → 返回 ProcessResponse（含 project_name + 17 欄 items）。
整合現有的 PDF 解析、數量總表解析、跨表合併、面料排序功能。
使用 skills yaml 配置來支援完整功能。
"""

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, Query

from ...models import FairmontItemResponse, ProcessResponse, SourceDocument
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Process"])


def _detect_document_type_from_filename(filename: str) -> str:
    """從檔名偵測文件類型（用於圖片匹配）."""
    filename_lower = filename.lower()

    if any(kw in filename_lower for kw in ["casegoods", "seating", "lighting"]):
        return "furniture_specification"
    elif any(kw in filename_lower for kw in ["fabric", "leather", "vinyl"]):
        return "fabric_specification"
    elif any(kw in filename_lower for kw in ["qty", "overall", "summary", "quantity"]):
        return "quantity_summary"

    return "furniture_specification"


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

            # 偵測文件角色
            document_role, role_detected_by = role_detector.detect_role(filename)

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
                    document_type = _detect_document_type_from_filename(doc.filename)
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
