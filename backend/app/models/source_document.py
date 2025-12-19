"""Source Document data model."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class SourceDocument(BaseModel):
    """來源文件資料模型."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="唯一識別碼 (UUID)")

    # 檔案資訊
    filename: str = Field(..., description="原始檔名")
    file_path: str = Field(..., description="暫存檔案路徑")
    file_size: int = Field(..., ge=0, le=52428800, description="檔案大小（bytes，最大 50MB）")
    mime_type: str = Field("application/pdf", description="MIME 類型")

    # 文件類型
    document_type: Literal["boq", "floor_plan", "unknown"] = Field(
        "unknown", description="文件類型"
    )

    # 解析狀態
    parse_status: Literal["pending", "processing", "completed", "failed"] = Field(
        "pending", description="解析狀態"
    )
    parse_progress: int = Field(0, ge=0, le=100, description="解析進度 %")
    parse_message: Optional[str] = Field(None, description="解析狀態訊息")
    parse_error: Optional[str] = Field(None, description="解析錯誤訊息")

    # 解析結果
    total_pages: Optional[int] = Field(None, ge=1, description="總頁數")
    extracted_items_count: int = Field(0, ge=0, description="提取的項目數")
    extracted_images_count: int = Field(0, ge=0, description="提取的圖片數")

    # 時間戳記
    uploaded_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = Field(None, description="處理完成時間")

    # Gemini API 相關
    gemini_file_uri: Optional[str] = Field(None, description="Gemini File API URI")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "filename": "BOQ_2025_Q1.pdf",
                "file_path": "/tmp/uploads/doc-123.pdf",
                "file_size": 1024000,
                "document_type": "boq",
                "parse_status": "pending",
            }
        }
