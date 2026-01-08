"""Item No. 標準化服務.

提供 Item No. 標準化功能，用於跨表比對時統一不同格式的項目編號。
"""

import re
from typing import Optional


class ItemNormalizerService:
    """Item No. 標準化服務."""

    # 單例模式
    _instance: Optional["ItemNormalizerService"] = None

    def __new__(cls) -> "ItemNormalizerService":
        """確保單例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def normalize(self, item_no: str) -> str:
        """
        標準化 Item No. 以支援跨表比對.

        規則：
        1. 去除前後空白
        2. 轉為大寫
        3. 移除所有空格
        4. 統一分隔符號為 '-'

        Args:
            item_no: 原始 Item No.

        Returns:
            標準化後的 Item No.

        Examples:
            >>> service = ItemNormalizerService()
            >>> service.normalize("DLX-100")
            'DLX-100'
            >>> service.normalize("dlx.100")
            'DLX-100'
            >>> service.normalize("DLX 100")
            'DLX100'
            >>> service.normalize("  STD_200  ")
            'STD-200'
            >>> service.normalize("ABC--123")
            'ABC-123'
        """
        if not item_no:
            return ""

        # 1. 移除前後空白
        normalized = item_no.strip()

        # 2. 統一大寫
        normalized = normalized.upper()

        # 3. 移除內部空格
        normalized = re.sub(r"\s+", "", normalized)

        # 4. 統一分隔符號 (. _ 和連續 - 視為相同，統一為單個 -)
        normalized = re.sub(r"[.\-_]+", "-", normalized)

        # 5. 移除開頭和結尾的分隔符號
        normalized = normalized.strip("-")

        return normalized

    def are_equivalent(self, item_no_1: str, item_no_2: str) -> bool:
        """
        檢查兩個 Item No. 是否等價（標準化後相同）.

        Args:
            item_no_1: 第一個 Item No.
            item_no_2: 第二個 Item No.

        Returns:
            True 如果等價，否則 False

        Examples:
            >>> service = ItemNormalizerService()
            >>> service.are_equivalent("DLX-100", "dlx.100")
            True
            >>> service.are_equivalent("DLX-100", "DLX-101")
            False
        """
        return self.normalize(item_no_1) == self.normalize(item_no_2)

    def is_format_different(self, item_no_1: str, item_no_2: str) -> bool:
        """
        檢查兩個 Item No. 格式是否不同但等價.

        用於產生格式差異警告。

        Args:
            item_no_1: 第一個 Item No.
            item_no_2: 第二個 Item No.

        Returns:
            True 如果格式不同但等價，否則 False

        Examples:
            >>> service = ItemNormalizerService()
            >>> service.is_format_different("DLX-100", "dlx.100")
            True
            >>> service.is_format_different("DLX-100", "DLX-100")
            False
            >>> service.is_format_different("DLX-100", "DLX-101")
            False
        """
        if not self.are_equivalent(item_no_1, item_no_2):
            return False
        return item_no_1.strip() != item_no_2.strip()


# 工廠函式
def get_item_normalizer_service() -> ItemNormalizerService:
    """
    取得 ItemNormalizerService 單例實例.

    Returns:
        ItemNormalizerService 實例
    """
    return ItemNormalizerService()
