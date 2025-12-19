"""Quotation data model."""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
import uuid

from .boq_item import BOQItem


class Quotation(BaseModel):
    """報價單資料模型."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="唯一識別碼 (UUID)")

    # 基本資訊
    title: Optional[str] = Field(None, description="報價單標題")
    created_at: datetime = Field(default_factory=datetime.now)

    # 來源文件
    source_document_ids: List[str] = Field(
        default_factory=list, description="來源文件 ID 列表"
    )

    # 包含的項目
    items: List[BOQItem] = Field(default_factory=list, description="BOQ 項目列表")

    # 統計資訊
    total_items: int = Field(0, ge=0, description="總項目數")
    items_with_qty: int = Field(0, ge=0, description="有數量的項目數")
    items_with_photo: int = Field(0, ge=0, description="有圖片的項目數")
    items_from_floor_plan: int = Field(0, ge=0, description="從平面圖補充數量的項目數")

    # 匯出狀態
    export_status: Literal["pending", "generating", "completed", "failed"] = Field(
        "pending", description="匯出狀態"
    )
    export_path: Optional[str] = Field(None, description="Excel 檔案路徑")
    export_error: Optional[str] = Field(None, description="匯出錯誤訊息")

    def update_statistics(self) -> None:
        """更新統計資訊."""
        self.total_items = len(self.items)
        self.items_with_qty = sum(1 for item in self.items if item.qty is not None)
        self.items_with_photo = sum(1 for item in self.items if item.photo_path)
        self.items_from_floor_plan = sum(
            1 for item in self.items if item.qty_source == "floor_plan"
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "title": "RFQ-2025-001",
                "source_document_ids": ["doc-123"],
                "items": [],
                "total_items": 0,
            }
        }
