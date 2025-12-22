"""BOQ Item data model.

完全比照惠而蒙格式 Excel 範本 15 欄:
A: NO., B: Item no., C: Description, D: Photo, E: Dimension WxDxH (mm),
F: Qty, G: UOM, H: Unit Rate (留空), I: Amount (留空), J: Unit CBM,
K: Total CBM (公式), L: Note, M: Location, N: Materials Used / Specs, O: Brand
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
import uuid


class BOQItem(BaseModel):
    """BOQ 項目資料模型（完全比照惠而蒙格式 15 欄）."""

    # 主鍵（系統產生，內部使用）
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="唯一識別碼 (UUID)")

    # Excel 欄位（完全比照範本 15 欄）
    no: int = Field(..., ge=1, description="A: 序號 (NO.)")
    item_no: str = Field(..., description="B: 項目編號 (Item no.)")
    description: str = Field(..., description="C: 描述 (Description)")
    photo_base64: Optional[str] = Field(None, description="D: 圖片 Base64 編碼 (Photo)")
    dimension: Optional[str] = Field(None, description="E: 尺寸規格 WxDxH mm (Dimension)")
    qty: Optional[float] = Field(None, ge=0, description="F: 數量 (Qty)")
    uom: Optional[str] = Field(None, description="G: 單位 (UOM)，如：ea, m, set")
    # H: Unit Rate - 不儲存，留空由使用者填寫
    # I: Amount - 不儲存，留空由使用者填寫
    unit_cbm: Optional[float] = Field(None, ge=0, description="J: 單位材積 (Unit CBM)")
    # K: Total CBM - 公式計算 =F*J
    note: Optional[str] = Field(None, description="L: 備註 (Note)")
    location: Optional[str] = Field(None, description="M: 位置/區域 (Location)")
    materials_specs: Optional[str] = Field(None, description="N: 材料/規格 (Materials Used / Specs)")
    brand: Optional[str] = Field(None, description="O: 品牌 (Brand)")

    # 內部追蹤欄位（不輸出到 Excel）
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")

    # 可選的內部追蹤欄位（用於平面圖核對功能 US3）
    source_type: Literal["boq", "floor_plan", "manual"] = Field(
        "boq", description="資料來源類型（內部使用）"
    )
    qty_verified: bool = Field(False, description="數量是否已核對（內部使用）")
    qty_source: Optional[Literal["boq", "floor_plan"]] = Field(
        None, description="數量資料來源（內部使用）"
    )

    # 時間戳記（內部使用）
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

    @field_validator("unit_cbm")
    @classmethod
    def validate_unit_cbm(cls, v: Optional[float]) -> Optional[float]:
        """驗證單位材積為正數."""
        if v is not None and v < 0:
            raise ValueError("單位材積不可為負數")
        return v

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "no": 1,
                "item_no": "DLX-100",
                "description": "King Bed",
                "photo_base64": "data:image/png;base64,iVBORw0KGgo...",
                "dimension": "1930 x 2130 x 290 H",
                "qty": 239.0,
                "uom": "ea",
                "unit_cbm": 1.74,
                "note": "Bed bases only, mattress by owner",
                "location": "King DLX (A/B), King STD",
                "materials_specs": "Vinyl: DLX-500 Taupe",
                "brand": "Fairmont",
                "source_document_id": "doc-123",
                "source_page": 1,
            }
        }
