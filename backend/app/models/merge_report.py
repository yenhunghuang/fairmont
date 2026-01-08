"""Merge Report data models for cross-document merging.

跨表合併報告模型，用於記錄多 PDF 合併的結果與追蹤資訊。
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from datetime import datetime
from enum import Enum
import uuid


class MergeStatus(str, Enum):
    """合併狀態列舉."""

    MATCHED = "matched"  # 成功配對（數量總表有對應項目）
    UNMATCHED = "unmatched"  # 未配對（僅在明細規格表）
    QUANTITY_ONLY = "quantity_only"  # 僅在數量總表出現


class FormatWarning(BaseModel):
    """Item No. 格式差異警告."""

    original: str = Field(..., description="原始 Item No.")
    normalized: str = Field(..., description="標準化後的 Item No.")
    source_file: str = Field(..., description="來源檔案名稱")


class MergeResult(BaseModel):
    """單一項目的合併結果."""

    # 項目識別
    item_no_normalized: str = Field(..., description="標準化後的 Item No.")
    original_item_nos: List[str] = Field(
        default_factory=list, description="原始 Item No. 列表"
    )

    # 合併狀態
    status: MergeStatus = Field(..., description="合併狀態")

    # 來源追蹤
    quantity_source: Optional[str] = Field(
        None, description="數量來源文件 ID（若數量來自數量總表）"
    )
    detail_sources: List[str] = Field(
        default_factory=list, description="明細來源文件 ID 列表（按上傳順序）"
    )

    # 欄位來源對照（用於 Merge Report 顯示）
    field_sources: Dict[str, str] = Field(
        default_factory=dict, description="欄位 -> 來源文件 ID 對照"
    )

    # 圖片選擇
    selected_image_source: Optional[str] = Field(
        None, description="選用圖片的來源文件 ID"
    )
    image_resolution: Optional[int] = Field(
        None, description="選用圖片的解析度 (width × height)"
    )


class MergeReport(BaseModel):
    """跨表合併報告."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="報告 ID (UUID)"
    )
    quotation_id: str = Field(..., description="關聯報價單 ID")

    # 來源文件
    quantity_summary_doc_id: Optional[str] = Field(
        None, description="數量總表文件 ID"
    )
    quantity_summary_filename: Optional[str] = Field(
        None, description="數量總表檔案名稱"
    )
    detail_spec_doc_ids: List[str] = Field(
        default_factory=list, description="明細規格表文件 ID 列表（按上傳順序）"
    )
    detail_spec_filenames: List[str] = Field(
        default_factory=list, description="明細規格表檔案名稱列表"
    )

    # 合併統計
    total_items: int = Field(0, ge=0, description="合併後總項目數")
    matched_items: int = Field(0, ge=0, description="成功配對項目數")
    unmatched_items: int = Field(0, ge=0, description="未配對項目數（僅在明細表）")
    quantity_only_items: int = Field(0, ge=0, description="僅在數量總表的項目數")

    # 合併詳情
    merge_results: List[MergeResult] = Field(
        default_factory=list, description="各項目合併結果"
    )

    # 警告訊息
    format_warnings: List[FormatWarning] = Field(
        default_factory=list, description="Item No. 格式差異警告"
    )
    warnings: List[str] = Field(default_factory=list, description="其他警告訊息")

    # 時間戳記
    created_at: datetime = Field(default_factory=datetime.now)
    processing_time_ms: int = Field(0, ge=0, description="處理時間（毫秒）")

    def add_warning(self, message: str) -> None:
        """新增警告訊息."""
        self.warnings.append(message)

    def add_format_warning(
        self, original: str, normalized: str, source_file: str
    ) -> None:
        """新增格式差異警告."""
        self.format_warnings.append(
            FormatWarning(
                original=original, normalized=normalized, source_file=source_file
            )
        )

    def get_match_rate(self) -> float:
        """計算配對率百分比."""
        if self.total_items == 0:
            return 0.0
        return (self.matched_items / self.total_items) * 100

    def update_statistics(self) -> None:
        """根據 merge_results 更新統計數據."""
        self.total_items = len(self.merge_results)
        self.matched_items = sum(
            1 for r in self.merge_results if r.status == MergeStatus.MATCHED
        )
        self.unmatched_items = sum(
            1 for r in self.merge_results if r.status == MergeStatus.UNMATCHED
        )
        self.quantity_only_items = sum(
            1 for r in self.merge_results if r.status == MergeStatus.QUANTITY_ONLY
        )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "id": "report-123",
                "quotation_id": "quot-456",
                "quantity_summary_doc_id": "doc-qty",
                "quantity_summary_filename": "Bay Tower - Overall Qty.pdf",
                "detail_spec_doc_ids": ["doc-detail-1", "doc-detail-2"],
                "detail_spec_filenames": ["Casegoods.pdf", "Fabric.pdf"],
                "total_items": 100,
                "matched_items": 85,
                "unmatched_items": 10,
                "quantity_only_items": 5,
            }
        }
