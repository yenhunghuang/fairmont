"""API Response models."""

from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, List, Any
from datetime import datetime


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="訊息（繁體中文）")
    data: Optional[T] = Field(None, description="回應資料")
    timestamp: datetime = Field(default_factory=datetime.now, description="回應時間")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(False, description="是否成功")
    message: str = Field(..., description="錯誤訊息（繁體中文）")
    error_code: Optional[str] = Field(None, description="錯誤代碼")
    timestamp: datetime = Field(default_factory=datetime.now, description="回應時間")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BOQItemResponse(BaseModel):
    """
    BOQ 項目 API 回應 DTO.

    僅暴露必要欄位給外部 API 消費者，隱藏內部追蹤欄位：
    - source_type, qty_verified, qty_source (內部追蹤)
    - created_at, updated_at (系統時間)
    """

    # 系統識別碼
    id: str = Field(..., description="唯一識別碼 (UUID)")

    # Excel 欄位（完全比照惠而蒙範本 15 欄）
    no: int = Field(..., ge=1, description="A: 序號 (NO.)")
    item_no: str = Field(..., description="B: 項目編號 (Item no.)")
    description: str = Field(..., description="C: 描述 (Description)")
    photo_base64: Optional[str] = Field(None, description="D: 圖片 Base64 編碼 (Photo)")
    dimension: Optional[str] = Field(None, description="E: 尺寸規格 WxDxH mm (Dimension)")
    qty: Optional[float] = Field(None, ge=0, description="F: 數量 (Qty)")
    uom: Optional[str] = Field(None, description="G: 單位 (UOM)，如：ea, m, set")
    unit_cbm: Optional[float] = Field(None, ge=0, description="J: 單位材積 (Unit CBM)")
    note: Optional[str] = Field(None, description="L: 備註 (Note)")
    location: Optional[str] = Field(None, description="M: 位置/區域 (Location)")
    materials_specs: Optional[str] = Field(None, description="N: 材料/規格 (Materials Used / Specs)")
    brand: Optional[str] = Field(None, description="O: 品牌 (Brand)")

    # 來源參考（保留供追蹤用途）
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: Optional[int] = Field(None, ge=1, description="來源頁碼")

    @classmethod
    def from_boq_item(cls, item: Any) -> "BOQItemResponse":
        """從 BOQItem 轉換為 BOQItemResponse DTO."""
        return cls(
            id=item.id,
            no=item.no,
            item_no=item.item_no,
            description=item.description,
            photo_base64=item.photo_base64,
            dimension=item.dimension,
            qty=item.qty,
            uom=item.uom,
            unit_cbm=item.unit_cbm,
            note=item.note,
            location=item.location,
            materials_specs=item.materials_specs,
            brand=item.brand,
            source_document_id=item.source_document_id,
            source_page=item.source_page,
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
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


class FairmontItemResponse(BaseModel):
    """
    Fairmont Excel 17 欄 DTO.

    完全符合 Fairmont Excel 格式，供前端直接使用：
    - 移除內部欄位：id, source_document_id, source_page
    - 新增留空欄位：unit_rate, amount, total_cbm (皆為 null)
    - 欄位名稱：photo_base64 → photo
    - 新增分類與附屬欄位 (2026-01-08)
    """

    no: int = Field(..., ge=1, description="A: 序號 (NO.)")
    item_no: str = Field(..., description="B: 項目編號 (Item no.)")
    description: str = Field(..., description="C: 描述 (Description)")
    photo: Optional[str] = Field(None, description="D: 圖片 Base64 編碼 (Photo)")
    dimension: Optional[str] = Field(None, description="E: 尺寸 WxDxH mm (Dimension)")
    qty: Optional[float] = Field(None, ge=0, description="F: 數量 (Qty)")
    uom: Optional[str] = Field(None, description="G: 單位 (UOM)")
    unit_rate: Optional[float] = Field(None, description="H: 單價 (Unit Rate) - 留空")
    amount: Optional[float] = Field(None, description="I: 金額 (Amount) - 留空")
    unit_cbm: Optional[float] = Field(None, ge=0, description="J: 單位材積 (Unit CBM)")
    total_cbm: Optional[float] = Field(None, description="K: 總材積 (Total CBM) - 留空")
    note: Optional[str] = Field(None, description="L: 備註 (Note)")
    location: Optional[str] = Field(None, description="M: 位置 (Location)")
    materials_specs: Optional[str] = Field(None, description="N: 材料規格 (Materials Used / Specs)")
    brand: Optional[str] = Field(None, description="O: 品牌 (Brand)")
    category: Optional[int] = Field(None, description="P: 分類 (1=家具, 5=面料)")
    affiliate: Optional[str] = Field(None, description="Q: 附屬 (面料來源的家具編號, 多個用 ', ' 分隔)")

    @classmethod
    def from_boq_item(cls, item: Any) -> "FairmontItemResponse":
        """從 BOQItem 轉換為 FairmontItemResponse DTO."""
        return cls(
            no=item.no,
            item_no=item.item_no,
            description=item.description,
            photo=item.photo_base64,  # 改名
            dimension=item.dimension,
            qty=item.qty,
            uom=item.uom,
            unit_rate=None,   # 留空
            amount=None,      # 留空
            unit_cbm=item.unit_cbm,
            total_cbm=None,   # 留空
            note=item.note,
            location=item.location,
            materials_specs=item.materials_specs,
            brand=item.brand,
            category=getattr(item, 'category', None),
            affiliate=getattr(item, 'affiliate', None),
        )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "no": 1,
                "item_no": "DLX-101",
                "description": "Custom Bed Bench",
                "photo": "iVBORw0KGgo...",
                "dimension": "1930 x 2130 x 290 H",
                "qty": 248.0,
                "uom": "ea",
                "unit_rate": None,
                "amount": None,
                "unit_cbm": 1.74,
                "total_cbm": None,
                "note": "Bed bases only",
                "location": "King DLX (A/B)",
                "materials_specs": "Vinyl: DLX-500 Taupe",
                "brand": "Fairmont",
                "category": 1,
                "affiliate": None,
            }
        }


class ProcessResponse(BaseModel):
    """
    /api/v1/process API 回應結構.

    包含專案名稱與 Fairmont 17 欄項目列表。
    """

    project_name: Optional[str] = Field(
        None, description="專案名稱 (從 PDF 的 PROJECT 標題提取)"
    )
    items: List[FairmontItemResponse] = Field(
        ..., description="Fairmont 17 欄項目列表"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "project_name": "SOLAIRE BAY TOWER",
                "items": [
                    {
                        "no": 1,
                        "item_no": "DLX-101",
                        "description": "Custom Bed Bench",
                        "photo": "iVBORw0KGgo...",
                        "dimension": "1930 x 2130 x 290 H",
                        "qty": 248.0,
                        "uom": "ea",
                        "unit_rate": None,
                        "amount": None,
                        "unit_cbm": 1.74,
                        "total_cbm": None,
                        "note": "Bed bases only",
                        "location": "King DLX (A/B)",
                        "materials_specs": "Vinyl: DLX-500 Taupe",
                        "brand": "Fairmont",
                        "category": 1,
                        "affiliate": None,
                    }
                ],
            }
        }


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model."""

    success: bool = Field(True, description="是否成功")
    message: str = Field("取得資料成功", description="訊息")
    data: List[T] = Field(..., description="資料列表")
    total: int = Field(..., ge=0, description="總筆數")
    page: int = Field(..., ge=1, description="頁碼")
    page_size: int = Field(..., ge=1, description="每頁筆數")
    total_pages: int = Field(..., ge=1, description="總頁數")
    timestamp: datetime = Field(default_factory=datetime.now, description="回應時間")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
