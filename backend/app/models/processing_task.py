"""Processing Task data model."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime
import uuid


class ProcessingTask(BaseModel):
    """處理任務狀態模型."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="任務 ID (UUID)")

    # 任務類型
    task_type: Literal["parse_pdf", "extract_images", "generate_excel", "analyze_floor_plan"] = Field(
        ..., description="任務類型"
    )

    # 狀態
    status: Literal["pending", "processing", "completed", "failed"] = Field(
        "pending", description="任務狀態"
    )
    progress: int = Field(0, ge=0, le=100, description="進度百分比")
    message: str = Field("等待處理", description="狀態訊息（繁體中文）")

    # 結果
    result: Optional[Any] = Field(None, description="任務結果")
    error: Optional[str] = Field(None, description="錯誤訊息")

    # 時間戳記
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(None, description="開始時間")
    completed_at: Optional[datetime] = Field(None, description="完成時間")

    # 關聯
    document_id: Optional[str] = Field(None, description="相關文件 ID")
    quotation_id: Optional[str] = Field(None, description="相關報價單 ID")

    def start(self) -> None:
        """標記任務開始."""
        self.status = "processing"
        self.started_at = datetime.now()

    def complete(self, result: Any = None) -> None:
        """標記任務完成."""
        self.status = "completed"
        self.progress = 100
        self.message = "處理完成"
        self.result = result
        self.completed_at = datetime.now()

    def fail(self, error: str) -> None:
        """標記任務失敗."""
        self.status = "failed"
        self.error = error
        self.message = f"處理失敗：{error}"
        self.completed_at = datetime.now()

    def update_progress(self, progress: int, message: str) -> None:
        """更新進度."""
        self.progress = min(max(progress, 0), 100)
        self.message = message

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "task_type": "parse_pdf",
                "status": "processing",
                "progress": 50,
                "message": "正在解析 PDF...",
                "document_id": "doc-123",
            }
        }
