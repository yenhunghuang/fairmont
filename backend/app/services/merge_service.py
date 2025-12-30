"""跨表合併服務.

將數量總表與多份明細規格表進行合併，產出統一的 BOQ 項目列表。
支援從 MergeRulesSkill 載入合併規則配置。
"""

import logging
import re
import time
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
from datetime import datetime

from ..models.boq_item import BOQItem
from ..models.quantity_summary import QuantitySummaryItem
from ..models.merge_report import MergeReport, MergeResult, MergeStatus, FormatWarning
from ..models.source_document import SourceDocument
from .item_normalizer import get_item_normalizer_service
from .image_selector import get_image_selector_service

if TYPE_CHECKING:
    from .skill_loader import SkillLoaderService, MergeRulesSkill, VendorSkill

logger = logging.getLogger(__name__)


# ============================================================
# Fallback 預設值（當 Skill 載入失敗時使用）
# ============================================================

DEFAULT_MERGEABLE_FIELDS = [
    "description",
    "dimension",
    "uom",
    "unit_cbm",
    "note",
    "location",
    "materials_specs",
    "brand",
]

DEFAULT_ERROR_MULTIPLE_QTY = "上傳多份數量總表，請僅保留一份"
DEFAULT_ERROR_NO_DETAIL = "未上傳明細規格表，無法進行合併"


class MergeService:
    """跨表合併服務.

    支援從 MergeRulesSkill 載入合併規則配置，使用 Constructor Injection。
    """

    def __init__(
        self,
        skill_loader: Optional["SkillLoaderService"] = None,
        vendor_id: str = "habitus",
    ):
        """初始化服務.

        Args:
            skill_loader: SkillLoaderService 實例，None 時使用全域單例
            vendor_id: 供應商 ID（用於載入面料偵測規則）
        """
        self._skill_loader = skill_loader
        self._vendor_id = vendor_id
        self._merge_rules: Optional["MergeRulesSkill"] = None
        self._vendor_skill: Optional["VendorSkill"] = None
        self._rules_loaded = False
        self._vendor_loaded = False
        self.item_normalizer = get_item_normalizer_service()
        self.image_selector = get_image_selector_service()

    def _ensure_skill_loaded(self) -> None:
        """確保 MergeRulesSkill 已載入（懶載入）."""
        if self._rules_loaded:
            return

        if self._skill_loader is None:
            from .skill_loader import get_skill_loader
            self._skill_loader = get_skill_loader()

        self._merge_rules = self._skill_loader.load_merge_rules_or_default("merge-rules")
        self._rules_loaded = True

    def _ensure_vendor_loaded(self) -> None:
        """確保 VendorSkill 已載入（懶載入）."""
        if self._vendor_loaded:
            return

        if self._skill_loader is None:
            from .skill_loader import get_skill_loader
            self._skill_loader = get_skill_loader()

        self._vendor_skill = self._skill_loader.load_vendor_or_default(self._vendor_id)
        self._vendor_loaded = True

    @property
    def mergeable_fields(self) -> list[str]:
        """取得可合併欄位列表."""
        self._ensure_skill_loaded()
        if self._merge_rules:
            fields = self._merge_rules.mergeable_fields
            if fields:
                return fields
        return DEFAULT_MERGEABLE_FIELDS

    def _get_error_message_multiple_qty(self) -> str:
        """取得多份數量總表錯誤訊息."""
        self._ensure_skill_loaded()
        if self._merge_rules:
            return self._merge_rules.constraints.error_message_multiple_qty
        return DEFAULT_ERROR_MULTIPLE_QTY

    def _get_error_message_no_detail(self) -> str:
        """取得無明細規格表錯誤訊息."""
        self._ensure_skill_loaded()
        if self._merge_rules:
            return self._merge_rules.constraints.error_message_no_detail
        return DEFAULT_ERROR_NO_DETAIL

    def _get_field_strategy(self, field: str) -> dict:
        """取得欄位合併策略.

        Args:
            field: 欄位名稱

        Returns:
            策略配置（包含 mode, separator 等）
        """
        self._ensure_skill_loaded()
        default_strategy = {"mode": "fill_empty", "separator": ""}

        if not self._merge_rules:
            return default_strategy

        strategies = self._merge_rules.field_merge.strategies
        if not strategies:
            return default_strategy

        # 嘗試取得欄位特定策略
        strategy = None
        if field in strategies:
            strategy = strategies[field]
        elif "default" in strategies:
            strategy = strategies["default"]

        if strategy is None:
            return default_strategy

        # 轉換 FieldMergeStrategy 為 dict
        return {
            "mode": strategy.mode,
            "separator": strategy.separator,
        }

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

        # 排序：面料跟隨對應家具
        merged_items = self._sort_items_fabric_follows_furniture(merged_items)

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
        1. fill_empty 模式：先上傳的 PDF 非空欄位優先，空值填補
        2. concatenate 模式：合併所有非空值（用於 location、note）
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

        # 為 concatenate 模式預先收集所有值
        concatenate_values: Dict[str, List[str]] = {}
        for field in self.mergeable_fields:
            strategy = self._get_field_strategy(field)
            if strategy["mode"] == "concatenate":
                concatenate_values[field] = []
                # 收集基礎項目的值
                base_value = getattr(merged, field)
                if base_value:
                    concatenate_values[field].append(str(base_value))

        # 合併後續項目
        for item, doc in sorted_items[1:]:
            if doc:
                merged.source_files.append(doc.id)

            # 合併可合併欄位
            for field in self.mergeable_fields:
                strategy = self._get_field_strategy(field)
                merged_value = getattr(merged, field)
                item_value = getattr(item, field)

                if strategy["mode"] == "concatenate":
                    # 收集非空值（稍後統一合併）
                    if item_value:
                        concatenate_values[field].append(str(item_value))
                else:
                    # fill_empty 模式：若基礎為空且當前有值，則採用當前值
                    if merged_value is None and item_value is not None:
                        setattr(merged, field, item_value)

            # 收集圖片
            if item.photo_base64:
                images_for_selection.append(
                    (doc.id if doc else "unknown", item.photo_base64)
                )

        # 應用 concatenate 模式的合併結果
        for field, values in concatenate_values.items():
            if values:
                strategy = self._get_field_strategy(field)
                separator = strategy.get("separator", ", ")
                # 去除重複值，保持順序
                unique_values = list(dict.fromkeys(values))
                setattr(merged, field, separator.join(unique_values))

        # 選擇最高解析度圖片
        if images_for_selection:
            best_image = self.image_selector.select_highest_resolution(
                images_for_selection
            )
            if best_image:
                merged.photo_base64 = best_image.base64_data
                merged.image_selected_from = best_image.source_id

        return merged

    def _get_fabric_detection_pattern(self) -> str:
        """取得面料偵測正規表達式（從 VendorSkill 載入）."""
        self._ensure_vendor_loaded()
        if self._vendor_skill:
            return self._vendor_skill.fabric_detection.pattern
        return r"\s+to\s+([A-Z0-9][A-Z0-9\-\.]+)"

    def _parse_fabric_targets(self, description: Optional[str]) -> List[str]:
        """
        從 description 解析面料對應的所有目標家具 item_no.

        格式範例:
        - "Vinyl to DLX-100" -> ["DLX-100"]
        - "Fabric to DLX-100 and to DLX-200" -> ["DLX-100", "DLX-200"]

        Args:
            description: 項目描述

        Returns:
            目標家具 item_no 列表（已正規化），若非面料則返回空列表
        """
        if not description:
            return []

        pattern = self._get_fabric_detection_pattern()
        matches = re.findall(pattern, description, re.IGNORECASE)
        if matches:
            return [self.item_normalizer.normalize(m) for m in matches]
        return []

    def _sort_items_fabric_follows_furniture(
        self, items: List[BOQItem]
    ) -> List[BOQItem]:
        """
        排序項目：面料跟隨對應家具.

        規則：
        1. 所有家具按 item_no 排序
        2. 面料項目插入到其引用的每個家具之後（面料可重複出現）
        3. 孤立面料（所有目標家具都不存在）放到最後

        Args:
            items: 合併後的 BOQItem 列表

        Returns:
            排序後的 BOQItem 列表（面料可能重複出現）
        """
        if not items:
            return items

        # 建立索引
        fabric_targets: Dict[str, List[str]] = {}  # fabric normalized_id -> [furniture normalized_ids]
        furniture_fabrics: Dict[str, List[BOQItem]] = {}  # furniture normalized_id -> [fabric items]
        all_items_by_id: Dict[str, BOQItem] = {}  # normalized_id -> item

        for item in items:
            normalized_id = item.item_no_normalized or self.item_normalizer.normalize(item.item_no)
            all_items_by_id[normalized_id] = item

            # 檢查是否為面料項目（可能引用多個家具）
            targets = self._parse_fabric_targets(item.description)
            if targets:
                fabric_targets[normalized_id] = targets
                # 將面料加入每個目標家具的列表
                for target in targets:
                    if target not in furniture_fabrics:
                        furniture_fabrics[target] = []
                    furniture_fabrics[target].append(item)

        # 識別家具項目（非面料）
        fabric_items_set = set(fabric_targets.keys())
        furniture_ids: List[str] = [
            nid for nid in all_items_by_id.keys()
            if nid not in fabric_items_set
        ]

        # 所有家具按 item_no 排序
        furniture_ids.sort()

        # 組合結果：家具 + 對應面料（面料可重複出現在多個家具後）
        sorted_items: List[BOQItem] = []

        for furniture_id in furniture_ids:
            # 加入家具
            sorted_items.append(all_items_by_id[furniture_id])

            # 加入該家具對應的面料（按 item_no 排序，允許重複）
            fabrics = furniture_fabrics.get(furniture_id, [])
            if fabrics:
                fabrics_sorted = sorted(
                    fabrics,
                    key=lambda x: x.item_no_normalized or self.item_normalizer.normalize(x.item_no)
                )
                sorted_items.extend(fabrics_sorted)

        # 處理孤立的面料項目（所有目標家具都不存在）
        matched_fabric_ids: set = set()
        for furniture_id in furniture_ids:
            for fabric in furniture_fabrics.get(furniture_id, []):
                fabric_id = fabric.item_no_normalized or self.item_normalizer.normalize(fabric.item_no)
                matched_fabric_ids.add(fabric_id)

        orphan_fabrics = [
            all_items_by_id[fid] for fid in fabric_targets.keys()
            if fid not in matched_fabric_ids
        ]
        orphan_fabrics.sort(
            key=lambda x: x.item_no_normalized or self.item_normalizer.normalize(x.item_no)
        )
        sorted_items.extend(orphan_fabrics)

        logger.debug(
            f"Item sorting: {len(furniture_ids)} furniture, "
            f"{len(orphan_fabrics)} orphan fabrics, "
            f"{len(sorted_items)} total (including duplicates)"
        )

        return sorted_items

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
                self._get_error_message_multiple_qty(),
                None,
                [],
            )

        # 檢查是否有明細規格表
        if not detail_spec_docs:
            return (
                False,
                self._get_error_message_no_detail(),
                None,
                [],
            )

        # 按 upload_order 排序明細規格表
        detail_spec_docs_sorted = sorted(
            detail_spec_docs, key=lambda d: d.upload_order
        )

        qty_summary_doc = quantity_summary_docs[0] if quantity_summary_docs else None

        return True, None, qty_summary_doc, detail_spec_docs_sorted


# ============================================================
# 單例工廠
# ============================================================

_merge_service_instance: Optional[MergeService] = None


def get_merge_service(
    skill_loader: Optional["SkillLoaderService"] = None,
) -> MergeService:
    """
    取得 MergeService 單例實例.

    Args:
        skill_loader: 可選的 SkillLoaderService 實例

    Returns:
        MergeService 實例
    """
    global _merge_service_instance
    if _merge_service_instance is None:
        _merge_service_instance = MergeService(skill_loader)
    return _merge_service_instance
