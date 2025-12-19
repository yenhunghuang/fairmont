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
