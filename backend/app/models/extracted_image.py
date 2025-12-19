"""Extracted Image data model."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class ExtractedImage(BaseModel):
    """提取圖片資料模型."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="唯一識別碼 (UUID)")

    # 檔案資訊
    filename: str = Field(..., description="圖片檔名")
    file_path: str = Field(..., description="圖片檔案路徑")
    format: str = Field(..., description="圖片格式（png/jpeg/etc）")

    # 尺寸
    width: int = Field(..., ge=1, description="寬度 (px)")
    height: int = Field(..., ge=1, description="高度 (px)")
    file_size: int = Field(..., ge=0, description="檔案大小 (bytes)")

    # 來源
    source_document_id: str = Field(..., description="來源文件 ID")
    source_page: int = Field(..., ge=1, description="來源頁碼")

    # 關聯
    boq_item_id: Optional[str] = Field(None, description="關聯的 BOQ 項目 ID")
    matched: bool = Field(False, description="是否已配對到 BOQ 項目")

    # 時間戳記
    extracted_at: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "filename": "image_page1_001.png",
                "file_path": "/app/extracted_images/img-123.png",
                "format": "png",
                "width": 1200,
                "height": 800,
                "file_size": 102400,
                "source_document_id": "doc-123",
                "source_page": 1,
            }
        }
