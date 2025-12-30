"""Quantity Summary data models.

數量總表項目模型，用於表示從數量總表 PDF 解析出的數量資料。
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class QuantitySummaryItem(BaseModel):
    """數量總表項目 - 僅包含 Item No 與數量."""

    # 項目識別
    item_no_raw: str = Field(..., description="原始 Item No.（從 PDF 解析）")
    item_no_normalized: str = Field(
        default="", description="標準化後的 Item No."
    )

    # 數量資訊
    total_qty: float = Field(..., ge=0, description="總數量")
    uom: Optional[str] = Field(None, description="單位")

    # 來源追蹤
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")

    @field_validator("item_no_raw")
    @classmethod
    def validate_item_no_raw(cls, v: str) -> str:
        """驗證原始 Item No. 不為空."""
        if not v or not v.strip():
            raise ValueError("Item No. 不可為空")
        return v.strip()

    @field_validator("total_qty")
    @classmethod
    def validate_total_qty(cls, v: float) -> float:
        """驗證數量為非負數."""
        if v < 0:
            raise ValueError("數量不可為負數")
        return v

    def model_post_init(self, __context) -> None:
        """初始化後自動標準化 Item No."""
        if not self.item_no_normalized:
            self.item_no_normalized = self.normalize_item_no(self.item_no_raw)

    @staticmethod
    def normalize_item_no(item_no: str) -> str:
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
            >>> QuantitySummaryItem.normalize_item_no("DLX-100")
            'DLX-100'
            >>> QuantitySummaryItem.normalize_item_no("dlx.100")
            'DLX-100'
            >>> QuantitySummaryItem.normalize_item_no("DLX 100")
            'DLX100'
            >>> QuantitySummaryItem.normalize_item_no("  STD_200  ")
            'STD-200'
        """
        if not item_no:
            return ""
        # 1. 移除前後空白
        normalized = item_no.strip()
        # 2. 統一大寫
        normalized = normalized.upper()
        # 3. 移除內部空格
        normalized = re.sub(r"\s+", "", normalized)
        # 4. 統一分隔符號 (. _ 和 - 視為相同，統一為 -)
        normalized = re.sub(r"[.\-_]+", "-", normalized)
        return normalized

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "item_no_raw": "DLX-100",
                "item_no_normalized": "DLX-100",
                "total_qty": 239.0,
                "uom": "ea",
                "source_document_id": "doc-123",
                "source_page": 1,
            }
        }
