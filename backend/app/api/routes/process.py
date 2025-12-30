"""Process API route - 單一整合端點.

提供簡化的 API 給前端：上傳 PDF → 直接返回 15 欄 JSON。
整合現有的 PDF 解析、圖片提取、圖片匹配功能。
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, Query
from pydantic import BaseModel, Field

from ...models import APIResponse, BOQItemResponse, SourceDocument
from ...api.dependencies import (
    get_store_dependency,
    get_file_manager,
    validate_pdf_files,
)
from ...services.pdf_parser import get_pdf_parser
from ...services.image_extractor import get_image_extractor
from ...services.image_matcher_deterministic import get_deterministic_image_matcher
from ...store import InMemoryStore
from ...utils import FileManager, log_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Process"])


class ProcessResponse(BaseModel):
    """處理結果回應."""

    items: List[dict] = Field(..., description="BOQ 項目列表（15 欄）")
    total_items: int = Field(..., description="總項目數")
    statistics: dict = Field(..., description="統計資訊")


@router.post(
    "/process",
    response_model=APIResponse,
    status_code=200,
    summary="上傳 PDF 並直接返回 JSON",
)
async def process_pdfs(
    files: List[UploadFile] = File(..., description="PDF 檔案（最多 5 個，單檔 ≤ 50MB）"),
    title: Optional[str] = Query(None, description="報價單標題"),
    extract_images: bool = Query(True, description="是否提取圖片"),
    store: InMemoryStore = Depends(get_store_dependency),
    file_manager: FileManager = Depends(get_file_manager),
) -> dict:
    """
    上傳 PDF 檔案並直接返回 15 欄 JSON.

    這是一個同步整合端點，將上傳、解析、合併全部在一個請求中完成。

    - **files**: PDF 檔案列表（最多 5 個，單檔最大 50MB）
    - **title**: 報價單標題（可選）
    - **extract_images**: 是否提取圖片（預設為 True）

    **注意**: 此端點為同步操作，處理時間約 10-60 秒（視 PDF 頁數而定）。
    前端應設定 timeout 為 120 秒以上。
    """
    try:
        # 1. 驗證檔案
        validated_files = await validate_pdf_files(files)
        logger.info(f"Validated {len(validated_files)} PDF files")

        # 2. 解析所有 PDF
        all_items = []
        total_images = 0
        matched_images = 0

        for filename, content in validated_files:
            # 儲存檔案
            file_path = file_manager.save_upload_file(content, filename)

            # 建立文件記錄
            doc = SourceDocument(
                filename=filename,
                file_path=file_path,
                file_size=len(content),
                document_type="unknown",
                parse_status="processing",
            )
            store.add_document(doc)

            # 驗證 PDF
            parser = get_pdf_parser()
            page_count, _ = parser.validate_pdf(file_path)
            doc.total_pages = page_count

            # 解析 PDF（同步等待）
            logger.info(f"Parsing PDF: {filename} ({page_count} pages)")
            boq_items, image_paths = await parser.parse_boq_with_gemini(
                file_path=file_path,
                document_id=doc.id,
                extract_images=extract_images,
            )

            # 圖片提取和匹配
            if extract_images and boq_items:
                extractor = get_image_extractor()
                images_with_bytes = extractor.extract_images_with_bytes(file_path, doc.id)
                total_images += len(images_with_bytes)

                if images_with_bytes:
                    # 使用確定性演算法匹配圖片
                    matcher = get_deterministic_image_matcher()
                    image_to_item_map = await matcher.match_images_to_items(
                        images_with_bytes,
                        boq_items,
                        target_page_offset=1,  # 預設偏移
                    )

                    # 套用匹配結果
                    for img_idx, item_id in image_to_item_map.items():
                        if img_idx < len(images_with_bytes):
                            img_data = images_with_bytes[img_idx]
                            base64_str = extractor._convert_to_base64(img_data["bytes"])

                            item = next((i for i in boq_items if i.id == item_id), None)
                            if item:
                                item.photo_base64 = base64_str
                                matched_images += 1

            # 更新文件狀態
            doc.parse_status = "completed"
            doc.extracted_items_count = len(boq_items)
            store.update_document(doc)

            # 收集項目
            all_items.extend(boq_items)
            logger.info(f"Parsed {len(boq_items)} items from {filename}")

        # 3. 重新編號（合併多份 PDF 時）
        for idx, item in enumerate(all_items, 1):
            item.no = idx

        # 4. 轉換為回應 DTO
        items_response = [
            BOQItemResponse.from_boq_item(item).model_dump()
            for item in all_items
        ]

        # 5. 統計資訊
        statistics = {
            "items_with_qty": sum(1 for item in all_items if item.qty is not None),
            "items_with_photo": sum(1 for item in all_items if item.photo_base64),
            "total_images": total_images,
            "matched_images": matched_images,
            "match_rate": round(matched_images / total_images, 2) if total_images > 0 else 0,
        }

        logger.info(
            f"Process completed: {len(all_items)} items, "
            f"{matched_images}/{total_images} images matched"
        )

        return {
            "success": True,
            "message": f"處理完成：{len(all_items)} 個項目",
            "data": {
                "items": items_response,
                "total_items": len(items_response),
                "statistics": statistics,
            },
        }

    except Exception as e:
        log_error(e, context="Process PDFs")
        raise
