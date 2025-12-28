"""跨表合併服務.

將數量總表與多份明細規格表進行合併，產出統一的 BOQ 項目列表。
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..models.boq_item import BOQItem
from ..models.quantity_summary import QuantitySummaryItem
from ..models.merge_report import MergeReport, MergeResult, MergeStatus, FormatWarning
from ..models.source_document import SourceDocument
from .item_normalizer import get_item_normalizer_service
from .image_selector import get_image_selector_service

logger = logging.getLogger(__name__)


# 可合併的欄位清單（除圖片外）
MERGEABLE_FIELDS = [
    "description",
    "dimension",
    "uom",
    "unit_cbm",
    "note",
    "location",
    "materials_specs",
    "brand",
]


class MergeService:
    """跨表合併服務."""

    # 單例模式
    _instance: Optional["MergeService"] = None

    def __new__(cls) -> "MergeService":
        """確保單例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化服務."""
        if self._initialized:
            return
        self._initialized = True
        self.item_normalizer = get_item_normalizer_service()
        self.image_selector = get_image_selector_service()

    def merge_documents(
        self,
        quantity_summary_items: List[QuantitySummaryItem],
        detail_boq_items: List[List[BOQItem]],
        quantity_summary_doc: Optional[SourceDocument],
        detail_spec_docs: List[SourceDocument],
        quotation_id: str,
    ) -> Tuple[List[BOQItem], MergeReport]:
        """
        執行跨表合併.

        Args:
            quantity_summary_items: 數量總表項目列表
            detail_boq_items: 明細規格表 BOQ 項目列表（按上傳順序）
            quantity_summary_doc: 數量總表文件
            detail_spec_docs: 明細規格表文件列表
            quotation_id: 報價單 ID

        Returns:
            (合併後的 BOQItem 列表, MergeReport)
        """
        start_time = time.time()
        logger.info(
            f"Starting merge: {len(quantity_summary_items)} qty items, "
            f"{len(detail_boq_items)} detail docs"
        )

        # 建立合併報告
        report = MergeReport(
            quotation_id=quotation_id,
            quantity_summary_doc_id=(
                quantity_summary_doc.id if quantity_summary_doc else None
            ),
            quantity_summary_filename=(
                quantity_summary_doc.filename if quantity_summary_doc else None
            ),
            detail_spec_doc_ids=[doc.id for doc in detail_spec_docs],
            detail_spec_filenames=[doc.filename for doc in detail_spec_docs],
        )

        # 建立數量總表索引 (normalized item_no -> qty)
        qty_index: Dict[str, Tuple[float, str, QuantitySummaryItem]] = {}
        for item in quantity_summary_items:
            normalized = self.item_normalizer.normalize(item.item_no_raw)
            qty_index[normalized] = (
                item.total_qty,
                item.item_no_raw,
                item,
            )

        # 檢查格式差異（重新迭代）
        for item in quantity_summary_items:
            normalized = self.item_normalizer.normalize(item.item_no_raw)
            if self.item_normalizer.is_format_different(
                item.item_no_raw, normalized
            ):
                report.add_format_warning(
                    original=item.item_no_raw,
                    normalized=normalized,
                    source_file=(
                        quantity_summary_doc.filename
                        if quantity_summary_doc
                        else "unknown"
                    ),
                )

        # 建立明細項目索引 (normalized item_no -> [items from different docs])
        detail_index: Dict[str, List[Tuple[BOQItem, SourceDocument]]] = {}
        for doc_idx, items in enumerate(detail_boq_items):
            doc = detail_spec_docs[doc_idx] if doc_idx < len(detail_spec_docs) else None
            for item in items:
                normalized = self.item_normalizer.normalize(item.item_no)
                if normalized not in detail_index:
                    detail_index[normalized] = []
                detail_index[normalized].append((item, doc))

        # 檢查格式差異（重新迭代）
        for doc_idx, items in enumerate(detail_boq_items):
            doc = detail_spec_docs[doc_idx] if doc_idx < len(detail_spec_docs) else None
            for item in items:
                normalized = self.item_normalizer.normalize(item.item_no)
                if doc and self.item_normalizer.is_format_different(
                    item.item_no, normalized
                ):
                    report.add_format_warning(
                        original=item.item_no,
                        normalized=normalized,
                        source_file=doc.filename,
                    )

        # 合併項目
        merged_items: List[BOQItem] = []
        processed_normalized_ids: set = set()

        # 先處理明細規格表中的項目
        for normalized_id, item_list in detail_index.items():
            processed_normalized_ids.add(normalized_id)

            # 合併同一 item_no 的多份明細
            merged_item = self._merge_detail_items(item_list)

            # 檢查是否有數量總表對應
            if normalized_id in qty_index:
                qty, original_item_no, qty_item = qty_index[normalized_id]
                merged_item.qty = qty
                merged_item.qty_source = "quantity_summary"
                merged_item.qty_verified = True
                merged_item.qty_from_summary = True
                merged_item.merge_status = "matched"

                # 建立合併結果
                merge_result = MergeResult(
                    item_no_normalized=normalized_id,
                    original_item_nos=[original_item_no]
                    + [item.item_no for item, _ in item_list],
                    status=MergeStatus.MATCHED,
                    quantity_source=(
                        quantity_summary_doc.id if quantity_summary_doc else None
                    ),
                    detail_sources=[doc.id for _, doc in item_list if doc],
                )
            else:
                merged_item.merge_status = "unmatched"
                merge_result = MergeResult(
                    item_no_normalized=normalized_id,
                    original_item_nos=[item.item_no for item, _ in item_list],
                    status=MergeStatus.UNMATCHED,
                    detail_sources=[doc.id for _, doc in item_list if doc],
                )

            merged_item.item_no_normalized = normalized_id
            merged_items.append(merged_item)
            report.merge_results.append(merge_result)

        # 處理僅在數量總表的項目
        for normalized_id, (qty, original_item_no, qty_item) in qty_index.items():
            if normalized_id not in processed_normalized_ids:
                # 建立合併結果（僅數量總表）
                merge_result = MergeResult(
                    item_no_normalized=normalized_id,
                    original_item_nos=[original_item_no],
                    status=MergeStatus.QUANTITY_ONLY,
                    quantity_source=(
                        quantity_summary_doc.id if quantity_summary_doc else None
                    ),
                )
                report.merge_results.append(merge_result)
                report.add_warning(
                    f"Item No. '{original_item_no}' 僅在數量總表中，無對應明細規格"
                )

        # 重新編號
        for idx, item in enumerate(merged_items, start=1):
            item.no = idx

        # 更新統計
        report.update_statistics()
        report.processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Merge completed: {len(merged_items)} items, "
            f"matched={report.matched_items}, "
            f"unmatched={report.unmatched_items}, "
            f"qty_only={report.quantity_only_items}, "
            f"time={report.processing_time_ms}ms"
        )

        return merged_items, report

    def _merge_detail_items(
        self, item_list: List[Tuple[BOQItem, SourceDocument]]
    ) -> BOQItem:
        """
        合併來自不同明細規格表的同一項目.

        規則：
        1. 先上傳的 PDF 非空欄位優先
        2. 若先上傳為空、後上傳有值，則取後上傳值
        3. 圖片選擇解析度較高者

        Args:
            item_list: [(BOQItem, SourceDocument), ...] 按上傳順序排列

        Returns:
            合併後的 BOQItem
        """
        if not item_list:
            raise ValueError("item_list cannot be empty")

        # 按 upload_order 排序（已假設輸入已排序，但保險起見）
        sorted_items = sorted(
            item_list,
            key=lambda x: x[1].upload_order if x[1] else 0,
        )

        # 以第一個項目為基礎
        base_item, base_doc = sorted_items[0]
        merged = base_item.model_copy(deep=True)
        merged.source_files = [base_doc.id] if base_doc else []

        # 收集所有圖片用於選擇最高解析度
        images_for_selection: List[Tuple[str, str]] = []
        if merged.photo_base64:
            images_for_selection.append(
                (base_doc.id if base_doc else "unknown", merged.photo_base64)
            )

        # 合併後續項目
        for item, doc in sorted_items[1:]:
            if doc:
                merged.source_files.append(doc.id)

            # 合併可合併欄位
            for field in MERGEABLE_FIELDS:
                merged_value = getattr(merged, field)
                item_value = getattr(item, field)

                # 若基礎為空且當前有值，則採用當前值
                if merged_value is None and item_value is not None:
                    setattr(merged, field, item_value)

            # 收集圖片
            if item.photo_base64:
                images_for_selection.append(
                    (doc.id if doc else "unknown", item.photo_base64)
                )

        # 選擇最高解析度圖片
        if images_for_selection:
            best_image = self.image_selector.select_highest_resolution(
                images_for_selection
            )
            if best_image:
                merged.photo_base64 = best_image.base64_data
                merged.image_selected_from = best_image.source_id

        return merged

    def validate_merge_request(
        self, documents: List[SourceDocument]
    ) -> Tuple[bool, Optional[str], Optional[SourceDocument], List[SourceDocument]]:
        """
        驗證合併請求.

        Args:
            documents: 文件列表

        Returns:
            (是否有效, 錯誤訊息, 數量總表文件, 明細規格表文件列表)
        """
        quantity_summary_docs = [
            d for d in documents if d.document_role == "quantity_summary"
        ]
        detail_spec_docs = [d for d in documents if d.document_role == "detail_spec"]

        # 檢查是否有多份數量總表
        if len(quantity_summary_docs) > 1:
            return (
                False,
                "上傳多份數量總表，請僅保留一份",
                None,
                [],
            )

        # 檢查是否有明細規格表
        if not detail_spec_docs:
            return (
                False,
                "未上傳明細規格表，無法進行合併",
                None,
                [],
            )

        # 按 upload_order 排序明細規格表
        detail_spec_docs_sorted = sorted(
            detail_spec_docs, key=lambda d: d.upload_order
        )

        qty_summary_doc = quantity_summary_docs[0] if quantity_summary_docs else None

        return True, None, qty_summary_doc, detail_spec_docs_sorted


# 工廠函式
def get_merge_service() -> MergeService:
    """
    取得 MergeService 單例實例.

    Returns:
        MergeService 實例
    """
    return MergeService()
