"""面料項目驗證服務.

驗證從 Gemini 解析出的面料項目是否為獨立規格頁，
過濾掉從 FURNITURE COM 區塊錯誤解析出的項目。

核心規則：只有當上傳了面料規格檔案時，才會輸出面料項目（category=5）。
判斷方式（按優先順序）：
1. 文件角色偵測結果（document_role == "fabric_spec"）
2. 檔名包含面料關鍵字（fabric/leather/vinyl）
"""

import logging
from typing import TYPE_CHECKING, List, Optional

from ..models.boq_item import BOQItem

if TYPE_CHECKING:
    from ..models.source_document import SourceDocument

logger = logging.getLogger(__name__)


class FabricValidatorService:
    """面料項目驗證服務.

    主要功能：
    1. 根據上傳檔案類型決定是否輸出面料項目
    2. 驗證面料項目是否來自獨立規格頁（非 FURNITURE COM 引用）

    驗證規則（需全部滿足）：
    1. 必須上傳面料規格檔案（檔名含 fabric/leather/vinyl）
    2. 必須有 location 欄位（從 ITEM: ... @ 提取）
    3. dimension 必須是完整的面料格式（以 Vinyl/Fabric/Leather 開頭）
    4. 必須有 brand 欄位（從 Vendor 提取）
    """

    # 有效的面料 dimension 前綴
    FABRIC_DIMENSION_PREFIXES = ["vinyl", "fabric", "leather", "textile"]

    # 面料規格檔案的檔名關鍵字
    FABRIC_FILE_KEYWORDS = ["fabric", "leather", "vinyl"]

    def has_fabric_file(self, filenames: List[str]) -> bool:
        """
        檢查上傳的檔案中是否包含面料規格檔案（僅檢查檔名）.

        Args:
            filenames: 上傳的檔案名稱列表

        Returns:
            True 如果有面料規格檔案（檔名含 fabric/leather/vinyl）
        """
        for filename in filenames:
            filename_lower = filename.lower()
            if any(kw in filename_lower for kw in self.FABRIC_FILE_KEYWORDS):
                return True
        return False

    def has_fabric_document(self, documents: List["SourceDocument"]) -> bool:
        """
        檢查文件列表中是否包含面料規格檔案（檢查 document_role）.

        優先使用文件角色偵測結果，比單純檢查檔名更準確。

        Args:
            documents: SourceDocument 列表

        Returns:
            True 如果有任何文件的 document_role 為 "fabric_spec"
        """
        for doc in documents:
            if doc.document_role == "fabric_spec":
                logger.debug(f"Found fabric_spec document: {doc.filename}")
                return True
        return False

    def filter_by_documents(
        self,
        items: List[BOQItem],
        documents: List["SourceDocument"],
    ) -> List[BOQItem]:
        """
        根據文件角色過濾面料項目（推薦使用）.

        規則：
        - 如果沒有 fabric_spec 文件，移除所有 category=5 的面料項目
        - 如果有 fabric_spec 文件，使用 validate_fabric_items 進行驗證

        Args:
            items: 從 Gemini 解析出的 BOQItem 列表
            documents: SourceDocument 列表（包含 document_role 資訊）

        Returns:
            過濾後的 BOQItem 列表
        """
        has_fabric = self.has_fabric_document(documents)

        if not has_fabric:
            # 沒有面料規格檔案，移除所有面料項目
            fabric_count = sum(1 for item in items if item.category == 5)
            if fabric_count > 0:
                logger.info(
                    f"No fabric_spec document detected. "
                    f"Removing all {fabric_count} fabric items (category=5)."
                )
            return [item for item in items if item.category != 5]

        # 有面料規格檔案，使用標準驗證
        logger.info("Fabric specification document detected (fabric_spec). Validating fabric items.")
        return self.validate_fabric_items(items)

    def filter_by_uploaded_files(
        self,
        items: List[BOQItem],
        uploaded_filenames: List[str],
    ) -> List[BOQItem]:
        """
        根據上傳的檔案類型過濾面料項目（舊版，僅檢查檔名）.

        注意：建議使用 filter_by_documents() 以獲得更準確的結果。

        規則：
        - 如果沒有上傳面料規格檔案，移除所有 category=5 的面料項目
        - 如果有上傳面料規格檔案，使用 validate_fabric_items 進行驗證

        Args:
            items: 從 Gemini 解析出的 BOQItem 列表
            uploaded_filenames: 上傳的檔案名稱列表

        Returns:
            過濾後的 BOQItem 列表
        """
        has_fabric = self.has_fabric_file(uploaded_filenames)

        if not has_fabric:
            # 沒有上傳面料規格檔案，移除所有面料項目
            fabric_count = sum(1 for item in items if item.category == 5)
            if fabric_count > 0:
                logger.info(
                    f"No fabric specification file uploaded (by filename). "
                    f"Removing all {fabric_count} fabric items (category=5)."
                )
            return [item for item in items if item.category != 5]

        # 有上傳面料規格檔案，使用標準驗證
        logger.info("Fabric specification file detected (by filename). Validating fabric items.")
        return self.validate_fabric_items(items)

    def validate_fabric_items(
        self,
        items: List[BOQItem],
    ) -> List[BOQItem]:
        """
        驗證並過濾面料項目.

        Args:
            items: 從 Gemini 解析出的 BOQItem 列表

        Returns:
            過濾後的 BOQItem 列表（移除無效的面料項目）
        """
        valid_items = []
        filtered_count = 0

        for item in items:
            # 非面料項目直接保留
            if item.category != 5:
                valid_items.append(item)
                continue

            # 驗證面料項目
            if self._is_valid_fabric_item(item):
                valid_items.append(item)
            else:
                filtered_count += 1
                logger.info(
                    f"Filtered invalid fabric item: {item.item_no} "
                    f"(missing required fields for independent fabric spec)"
                )

        if filtered_count > 0:
            logger.info(
                f"Fabric validation: filtered {filtered_count} items "
                f"(likely from FURNITURE COM references)"
            )

        return valid_items

    def _is_valid_fabric_item(self, item: BOQItem) -> bool:
        """
        檢查面料項目是否有效（來自獨立規格頁）.

        驗證條件（需全部滿足）：
        1. location 不為空（從 ITEM: ... @ 提取）
        2. dimension 是完整的面料格式
        3. brand 不為空（從 Vendor 提取）

        Returns:
            True 如果是有效的獨立面料項目
        """
        # 條件 1: 必須有 location（表示有 @ 符號來源）
        if not item.location or not item.location.strip():
            logger.debug(
                f"Fabric item {item.item_no}: missing location "
                "(no @ reference found)"
            )
            return False

        # 條件 2: dimension 必須是完整的面料格式
        if not self._has_valid_fabric_dimension(item.dimension):
            logger.debug(
                f"Fabric item {item.item_no}: invalid dimension format "
                f"(got: {item.dimension})"
            )
            return False

        # 條件 3: 必須有 brand
        if not item.brand or not item.brand.strip():
            logger.debug(
                f"Fabric item {item.item_no}: missing brand "
                "(fabric requires brand from Vendor)"
            )
            return False

        return True

    def _has_valid_fabric_dimension(self, dimension: Optional[str]) -> bool:
        """
        檢查 dimension 是否為有效的面料格式.

        有效格式：<材料類型>-<Vendor>-<Pattern>-<Color>-<Width> plain/pattern
        例如：Vinyl-Morbern Europe-Prodigy PRO 682-Lt Neutral-137cmW plain
        """
        if not dimension:
            return False

        dim_lower = dimension.lower().strip()

        # 檢查是否以面料類型開頭
        if not any(dim_lower.startswith(prefix) for prefix in self.FABRIC_DIMENSION_PREFIXES):
            return False

        # 檢查是否符合完整格式（至少有 4 個 "-" 分隔的部分）
        # 這可以區分 "Vinyl-Morbern-Pattern-Color-Width" 與簡單的 "Vinyl"
        parts = dimension.split("-")
        if len(parts) < 4:
            return False

        return True


# 單例工廠
_fabric_validator_instance: Optional[FabricValidatorService] = None


def get_fabric_validator_service() -> FabricValidatorService:
    """取得 FabricValidatorService 單例實例."""
    global _fabric_validator_instance
    if _fabric_validator_instance is None:
        _fabric_validator_instance = FabricValidatorService()
    return _fabric_validator_instance
