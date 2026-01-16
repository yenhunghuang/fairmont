"""Dimension 格式化服務.

根據項目類型（面料/家具）格式化 Dimension 欄位顯示。
配置從 skills/vendors/habitus.yaml 的 dimension_formatting 區塊載入。
"""

import logging
import re
from typing import Optional, TYPE_CHECKING

from ..models.boq_item import BOQItem

if TYPE_CHECKING:
    from .skill_loader import DimensionFormattingConfig

logger = logging.getLogger(__name__)


class DimensionFormatterService:
    """Dimension 格式化服務.

    配置從 skills/vendors/habitus.yaml 載入，支援懶載入模式。
    """

    # 單例模式
    _instance: Optional["DimensionFormatterService"] = None

    def __new__(cls) -> "DimensionFormatterService":
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
        self._config: Optional["DimensionFormattingConfig"] = None

    def _ensure_config_loaded(self) -> "DimensionFormattingConfig":
        """確保配置已載入（懶載入）."""
        if self._config is None:
            from .skill_loader import get_skill_loader, DimensionFormattingConfig
            loader = get_skill_loader()
            skill = loader.load_vendor_or_default("habitus")
            self._config = skill.dimension_formatting if skill else DimensionFormattingConfig()
        return self._config

    @property
    def fabric_keywords(self) -> list[str]:
        """取得面料關鍵字列表."""
        return self._ensure_config_loaded().fabric_keywords

    @property
    def circular_keywords(self) -> list[str]:
        """取得圓形家具關鍵字列表."""
        return self._ensure_config_loaded().circular_keywords

    @property
    def fabric_format_prefixes(self) -> list[str]:
        """取得面料格式前綴列表."""
        return self._ensure_config_loaded().fabric_format_prefixes

    def format_dimension(self, item: BOQItem) -> str:
        """
        格式化 Dimension 欄位.

        Args:
            item: BOQItem 項目

        Returns:
            格式化後的 dimension 字串
        """
        # 如果沒有 dimension，直接返回空字串
        if not item.dimension:
            # 面料沒有 dimension 時，檢查 description 決定 pattern/plain
            if self.is_fabric(item):
                return self._format_fabric_dimension(item)
            return ""

        # 0. 先檢查 dimension 是否已是完整面料格式（以材料類型開頭）
        dim_lower = item.dimension.lower()
        if any(dim_lower.startswith(prefix) for prefix in self.fabric_format_prefixes):
            # dimension 已是完整面料格式，直接返回
            return item.dimension

        # 1. 判斷是否為面料
        if self.is_fabric(item):
            return self._format_fabric_dimension(item)

        # 2. 判斷是否為圓形家具（dimension 含 Dia）
        if self._is_circular(item.dimension):
            return self._format_circular_dimension(item.dimension)

        # 3. 一般家具：保持原始格式或解析 L×W×H
        return self._format_furniture_dimension(item.dimension)

    def is_fabric(self, item: BOQItem) -> bool:
        """
        判斷項目是否為面料.

        根據以下條件判斷（優先級順序）：
        1. category 為明確的家具類型 → 返回 False（不是面料）
        2. category 為 fabric/leather/vinyl 類型 → 返回 True
        3. description 含面料關鍵字（如 "Fabric to", "Vinyl to"）

        注意：不檢查 materials_specs，因為家具的搭配材料也可能包含 fabric 關鍵字。

        Args:
            item: BOQItem 項目

        Returns:
            是否為面料
        """
        # 1. 優先檢查 category（如果有）
        if hasattr(item, "category") and item.category:
            cat_lower = item.category.lower()
            # 明確的家具類型 → 不是面料
            furniture_categories = ["seating", "casegoods", "lighting", "furniture"]
            if any(fc in cat_lower for fc in furniture_categories):
                return False
            # 明確的面料類型 → 是面料
            if "fabric" in cat_lower or "leather" in cat_lower or "vinyl" in cat_lower:
                return True

        # 2. 檢查 description 是否含面料關鍵字（如 "Fabric to", "Vinyl to"）
        if item.description:
            desc_lower = item.description.lower()
            # 面料的 description 格式通常是 "<類型> to <家具編號>"
            for keyword in self.fabric_keywords:
                keyword_lower = keyword.lower()
                # 檢查是否以面料關鍵字開頭（如 "Fabric to...", "Vinyl to..."）
                if desc_lower.startswith(keyword_lower):
                    return True

        return False

    def _format_fabric_dimension(self, item: BOQItem) -> str:
        """
        格式化面料的 Dimension.

        規則：
        - 如果 item.dimension 已有完整格式（含材料類型），直接返回
        - 否則根據 repeat 判斷返回 "pattern" 或 "plain"

        Args:
            item: BOQItem 項目

        Returns:
            完整的 dimension 字串，如 "Vinyl-Morbern Europe-Prodigy PRO-682-Lt Neutral-137cmW plain"
        """
        # 如果 dimension 已有完整格式（含材料類型-Vendor-Pattern-Color-Width），直接返回
        if item.dimension:
            dim_lower = item.dimension.lower()
            # 檢查是否已是完整格式（以材料類型開頭）
            if any(dim_lower.startswith(prefix) for prefix in self.fabric_format_prefixes):
                return item.dimension

        # Fallback: 只有 "pattern" 或 "plain"
        desc = (item.description or "").lower()
        materials = (item.materials_specs or "").lower()

        if "repeat" in desc or "repeat" in materials:
            return "pattern"

        return "plain"

    def _is_circular(self, dimension: str) -> bool:
        """
        判斷是否為圓形家具.

        Args:
            dimension: dimension 字串

        Returns:
            是否為圓形
        """
        if not dimension:
            return False

        dim_lower = dimension.lower()
        for keyword in self.circular_keywords:
            if keyword in dim_lower:
                return True

        return False

    def _format_circular_dimension(self, dimension: str) -> str:
        """
        格式化圓形家具的 Dimension.

        規則：顯示 "Dia.{直徑} × H{高}"

        Args:
            dimension: 原始 dimension 字串

        Returns:
            格式化後的字串，如 "Dia.600 × H450"
        """
        # 嘗試解析直徑和高度
        # 常見格式：
        # - "Dia.600 x H450"
        # - "Ø600 x 450H"
        # - "Dia 600mm x H 450mm"
        # - "diameter 600 height 450"

        dim_lower = dimension.lower()

        # 提取所有數字
        numbers = re.findall(r"(\d+(?:\.\d+)?)", dimension)

        if not numbers:
            # 無法解析，返回原始值
            return dimension

        # 嘗試識別直徑和高度
        diameter = None
        height = None

        # 模式 1: 明確標記 Dia 和 H
        dia_match = re.search(r"(?:dia\.?|ø|diameter)\s*(\d+(?:\.\d+)?)", dim_lower)
        height_match = re.search(r"(?:h|height)\s*(\d+(?:\.\d+)?)", dim_lower)

        if dia_match:
            diameter = dia_match.group(1)
        if height_match:
            height = height_match.group(1)

        # 模式 2: 如果只找到數字，假設第一個是直徑，第二個是高度
        if not diameter and len(numbers) >= 1:
            diameter = numbers[0]
        if not height and len(numbers) >= 2:
            height = numbers[1]

        # 格式化輸出
        if diameter and height:
            return f"Dia.{diameter} × H{height}"
        elif diameter:
            return f"Dia.{diameter}"
        else:
            return dimension

    def _format_furniture_dimension(self, dimension: str) -> str:
        """
        格式化一般家具的 Dimension.

        規則：解析並格式化為 "{長} × {寬} × {高}"
        取 overall/OA 數值中的最大者

        Args:
            dimension: 原始 dimension 字串

        Returns:
            格式化後的字串，如 "800 × 600 × 450"
        """
        if not dimension:
            return ""

        # 常見格式：
        # - "800 x 600 x 450"
        # - "W800 x D600 x H450"
        # - "800W x 600D x 450H"
        # - "OA: 800 x 600 x 450"
        # - "overall 800x600x450"

        # 移除 OA/overall 前綴
        dim_cleaned = re.sub(r"(?:oa|overall)[:\s]*", "", dimension, flags=re.IGNORECASE)

        # 提取所有數字
        numbers = re.findall(r"(\d+(?:\.\d+)?)", dim_cleaned)

        if not numbers:
            return dimension

        # 嘗試識別三個維度 (W/L × D × H)
        dim1 = None  # 第一維度 (W 或 L)
        dim2 = None  # 第二維度 (D)
        dim3 = None  # 第三維度 (H)

        dim_lower = dim_cleaned.lower()

        # 模式 1: 明確標記 W/D/H 或 L/D/H (標記在數字前)
        # 例如: W1200 x D600 x H750
        w_match = re.search(r"[wl]\s*(\d+(?:\.\d+)?)", dim_lower)
        d_match = re.search(r"d\s*(\d+(?:\.\d+)?)", dim_lower)
        h_match = re.search(r"h\s*(\d+(?:\.\d+)?)", dim_lower)

        if w_match:
            dim1 = w_match.group(1)
        if d_match:
            dim2 = d_match.group(1)
        if h_match:
            dim3 = h_match.group(1)

        # 模式 2: 數字後面跟著 W/D/H (標記在數字後)
        # 例如: 1200W x 600D x 450H
        if not (dim1 and dim2 and dim3):
            wdh_pattern = re.findall(r"(\d+(?:\.\d+)?)\s*([wdhlWDHL])", dim_cleaned)
            for val, label in wdh_pattern:
                label_lower = label.lower()
                if label_lower in ["w", "l"] and not dim1:
                    dim1 = val
                elif label_lower == "d" and not dim2:
                    dim2 = val
                elif label_lower == "h" and not dim3:
                    dim3 = val

        # 模式 3: 純數字格式 "800 x 600 x 450"，假設順序為 W x D x H
        if not (dim1 and dim2 and dim3) and len(numbers) >= 3:
            if not dim1:
                dim1 = numbers[0]
            if not dim2:
                dim2 = numbers[1]
            if not dim3:
                dim3 = numbers[2]

        # 格式化輸出：統一為 W × D × H 格式，不滿三個用 null 填充，不加單位
        w_val = dim1 if dim1 else "null"
        d_val = dim2 if dim2 else "null"
        h_val = dim3 if dim3 else "null"

        # 如果完全無法解析（三個都是 null），返回原始值
        if w_val == "null" and d_val == "null" and h_val == "null":
            return dimension

        return f"{w_val} × {d_val} × {h_val}"


# 工廠函式
def get_dimension_formatter_service() -> DimensionFormatterService:
    """
    取得 DimensionFormatterService 單例實例.

    Returns:
        DimensionFormatterService 實例
    """
    return DimensionFormatterService()
