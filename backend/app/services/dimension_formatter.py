"""Dimension 格式化服務.

根據項目類型（面料/家具）格式化 Dimension 欄位顯示。
"""

import logging
import re
from typing import Optional, Tuple, List

from ..models.boq_item import BOQItem

logger = logging.getLogger(__name__)


# 面料相關關鍵字
FABRIC_KEYWORDS = [
    "fabric",
    "leather",
    "textile",
    "upholstery",
    "面料",
    "皮革",
    "布料",
]

# 圓形家具關鍵字（在 dimension 中）
CIRCULAR_KEYWORDS = ["dia", "dia.", "diameter", "ø", "Ø"]


class DimensionFormatterService:
    """Dimension 格式化服務."""

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

        根據以下條件判斷：
        1. source_document_id 對應的檔案名稱含 fabric/leather
        2. description 含面料關鍵字
        3. category 為 fabric/leather 類型

        Args:
            item: BOQItem 項目

        Returns:
            是否為面料
        """
        # 檢查 description
        if item.description:
            desc_lower = item.description.lower()
            for keyword in FABRIC_KEYWORDS:
                if keyword.lower() in desc_lower:
                    return True

        # 檢查 category（如果有）
        if hasattr(item, "category") and item.category:
            cat_lower = item.category.lower()
            if "fabric" in cat_lower or "leather" in cat_lower:
                return True

        # 檢查 materials_specs（通常面料會有材質說明）
        if item.materials_specs:
            specs_lower = item.materials_specs.lower()
            for keyword in FABRIC_KEYWORDS:
                if keyword.lower() in specs_lower:
                    return True

        return False

    def _format_fabric_dimension(self, item: BOQItem) -> str:
        """
        格式化面料的 Dimension.

        規則：
        - 描述含 "repeat" → "pattern"
        - 描述不含 "repeat" → "plain"

        Args:
            item: BOQItem 項目

        Returns:
            "pattern" 或 "plain"
        """
        desc = (item.description or "").lower()
        materials = (item.materials_specs or "").lower()

        # 檢查 description 和 materials_specs 是否含 repeat
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
        for keyword in CIRCULAR_KEYWORDS:
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

        # 格式化輸出
        parts = []
        if dim1:
            parts.append(str(dim1))
        if dim2:
            parts.append(str(dim2))
        if dim3:
            parts.append(str(dim3))

        if len(parts) >= 3:
            return f"{parts[0]} × {parts[1]} × {parts[2]}"
        elif len(parts) == 2:
            return f"{parts[0]} × {parts[1]}"
        elif len(parts) == 1:
            return parts[0]
        else:
            # 無法解析，返回原始值
            return dimension


# 工廠函式
def get_dimension_formatter_service() -> DimensionFormatterService:
    """
    取得 DimensionFormatterService 單例實例.

    Returns:
        DimensionFormatterService 實例
    """
    return DimensionFormatterService()
