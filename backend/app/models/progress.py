"""進度追蹤模型，用於 SSE 串流回報處理進度."""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Callable, Awaitable, Optional, Any


class ProcessingStage(str, Enum):
    """處理階段列舉."""

    VALIDATING = "validating"
    DETECTING_ROLES = "detecting_roles"
    PARSING_DETAIL_SPECS = "parsing_detail_specs"
    PARSING_QUANTITY_SUMMARY = "parsing_quantity_summary"
    MERGING = "merging"
    CONVERTING = "converting"
    COMPLETED = "completed"


@dataclass
class ProgressDetail:
    """進度詳細資訊."""

    current_file: Optional[str] = None
    current_file_index: Optional[int] = None
    total_files: Optional[int] = None
    items_parsed: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典，排除 None 值."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ProgressUpdate:
    """進度更新資料."""

    stage: ProcessingStage
    progress: int  # 0-100
    message: str
    detail: Optional[ProgressDetail] = None

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典."""
        result = {
            "stage": self.stage.value,
            "progress": self.progress,
            "message": self.message,
        }
        if self.detail:
            result["detail"] = self.detail.to_dict()
        return result


# 進度回調類型定義
ProgressCallback = Callable[[ProgressUpdate], Awaitable[None]]
