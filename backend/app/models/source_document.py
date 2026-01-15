"""Source Document data model."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum
import uuid


# 文件角色類型定義
# - detail_spec: 家具明細規格表（Casegoods & Seatings）
# - fabric_spec: 面料明細規格表（Fabric/Leather/Vinyl specifications）
DocumentRole = Literal["quantity_summary", "detail_spec", "fabric_spec", "floor_plan", "index", "unknown"]

# 角色偵測方式
RoleDetectionMethod = Literal["filename", "manual", "content"]


class DocumentStatus(str, Enum):
    """Processing status for a document."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


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

    # 專案資訊 (從 PDF 標題頁提取)
    project_name: Optional[str] = Field(None, description="專案名稱 (如 SOLAIRE BAY TOWER)")

    # 時間戳記
    uploaded_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = Field(None, description="處理完成時間")

    # Gemini API 相關
    gemini_file_uri: Optional[str] = Field(None, description="Gemini File API URI")

    # 跨表合併欄位 (2025-12-23 新增)
    document_role: DocumentRole = Field(
        "unknown", description="文件角色（數量總表/明細規格表/平面圖）"
    )
    upload_order: int = Field(
        0, ge=0, description="上傳順序（用於多明細表合併優先順序）"
    )
    role_detected_by: RoleDetectionMethod = Field(
        "filename", description="角色偵測方式"
    )

    # Pipeline 擴展欄位 (SQLite multi-stage pipeline)
    session_id: Optional[str] = Field(None, description="處理 Session ID")
    file_hash: Optional[str] = Field(None, description="檔案內容 Hash (用於重複檢測)")
    processing_status: DocumentStatus = Field(
        DocumentStatus.PENDING, description="Pipeline 處理狀態"
    )
    processing_stage: int = Field(0, ge=0, le=7, description="目前處理階段 (0-7)")
    vendor_id: str = Field("habitus", description="供應商識別碼")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "filename": "BOQ_2025_Q1.pdf",
                "file_path": "/tmp/uploads/doc-123.pdf",
                "file_size": 1024000,
                "document_type": "boq",
                "parse_status": "pending",
            }
        },
    }


class DocumentProgressResponse(BaseModel):
    """API response model for document progress within a session.

    Used within SessionProgressResponse to report per-document status.
    """

    document_id: str
    filename: str
    processing_status: DocumentStatus
    processing_stage: int = Field(ge=0, le=7)
    total_pages: Optional[int] = None
    items_extracted: int = 0
    images_extracted: int = 0
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
