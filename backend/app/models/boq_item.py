"""BOQ Item data model."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
import uuid


class BOQItem(BaseModel):
    """BOQ 項目資料模型."""

    # 主鍵（系統產生）
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="唯一識別碼 (UUID)")

    # 核心欄位（惠而蒙格式 10 欄，排除價格/金額欄位）
    no: int = Field(..., ge=1, description="序號 (NO.)")
    item_no: str = Field(..., description="項目編號 (Item No.)")
    description: str = Field(..., description="描述 (Description)")
    photo_path: Optional[str] = Field(None, description="圖片檔案路徑 (Photo)")
    dimension: Optional[str] = Field(None, description="尺寸規格 WxDxH mm (Dimension)")
    qty: Optional[float] = Field(None, ge=0, description="數量 (Qty)")
    uom: Optional[str] = Field(None, description="單位 (UOM)，如：ea, m, set")
    note: Optional[str] = Field(None, description="備註 (Note)")
    location: Optional[str] = Field(None, description="位置/區域 (Location)")
    materials_specs: Optional[str] = Field(None, description="材料/規格 (Materials Used / Specs)")

    # 來源追蹤
    source_type: Literal["boq", "floor_plan", "manual"] = Field(
        "boq", description="資料來源類型"
    )
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")
    source_location: Optional[str] = Field(None, description="原始 PDF 中的位置描述")

    # 驗證狀態
    qty_verified: bool = Field(False, description="數量是否已核對")
    qty_source: Optional[Literal["boq", "floor_plan"]] = Field(
        None, description="數量資料來源"
    )

    # 時間戳記
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("item_no")
    @classmethod
    def validate_item_no(cls, v: str) -> str:
        """驗證項次編號不為空."""
        if not v or not v.strip():
            raise ValueError("項次編號不可為空")
        return v.strip()

    @field_validator("qty")
    @classmethod
    def validate_qty(cls, v: Optional[float]) -> Optional[float]:
        """驗證數量為正數."""
        if v is not None and v < 0:
            raise ValueError("數量不可為負數")
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "no": 1,
                "item_no": "FUR-001",
                "description": "會議桌",
                "photo_path": "/path/to/image.jpg",
                "dimension": "1200x600x750",
                "qty": 5.0,
                "uom": "ea",
                "note": "黑色烤漆",
                "location": "會議室",
                "materials_specs": "密集板 + 木皮",
                "source_type": "boq",
                "source_document_id": "doc-123",
                "source_page": 1,
            }
        }
