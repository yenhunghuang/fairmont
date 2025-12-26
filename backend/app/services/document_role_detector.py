"""PDF 文件角色偵測服務.

根據檔名關鍵字自動識別 PDF 文件在跨表合併中的角色。
"""

import re
from typing import Optional, Tuple

from app.models.source_document import DocumentRole, RoleDetectionMethod


class DocumentRoleDetectorService:
    """PDF 文件角色偵測服務."""

    # 數量總表關鍵字（不區分大小寫）
    QUANTITY_SUMMARY_KEYWORDS = [
        "qty",
        "overall",
        "summary",
        "數量",
        "總量",
        "總表",
        "quantity",
        "quantities",
    ]

    # 平面圖關鍵字（不區分大小寫）
    FLOOR_PLAN_KEYWORDS = [
        "floor",
        "plan",
        "layout",
        "平面圖",
        "平面",
        "配置圖",
    ]

    # 單例模式
    _instance: Optional["DocumentRoleDetectorService"] = None

    def __new__(cls) -> "DocumentRoleDetectorService":
        """確保單例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def detect_role(
        self, filename: str
    ) -> Tuple[DocumentRole, RoleDetectionMethod]:
        """
        根據檔名偵測文件角色.

        Args:
            filename: PDF 檔案名稱

        Returns:
            (角色, 偵測方式) 元組

        Examples:
            >>> service = DocumentRoleDetectorService()
            >>> service.detect_role("Bay Tower - Overall Qty.pdf")
            ('quantity_summary', 'filename')
            >>> service.detect_role("Casegoods & Seatings.pdf")
            ('detail_spec', 'filename')
            >>> service.detect_role("Floor Plan Level 1.pdf")
            ('floor_plan', 'filename')
        """
        if not filename:
            return "unknown", "filename"

        filename_lower = filename.lower()

        # 檢查是否為數量總表
        for keyword in self.QUANTITY_SUMMARY_KEYWORDS:
            if keyword.lower() in filename_lower:
                return "quantity_summary", "filename"

        # 檢查是否為平面圖
        for keyword in self.FLOOR_PLAN_KEYWORDS:
            if keyword.lower() in filename_lower:
                return "floor_plan", "filename"

        # 預設為明細規格表
        return "detail_spec", "filename"

    def is_quantity_summary(self, filename: str) -> bool:
        """
        檢查檔案是否為數量總表.

        Args:
            filename: PDF 檔案名稱

        Returns:
            True 如果是數量總表，否則 False
        """
        role, _ = self.detect_role(filename)
        return role == "quantity_summary"

    def is_detail_spec(self, filename: str) -> bool:
        """
        檢查檔案是否為明細規格表.

        Args:
            filename: PDF 檔案名稱

        Returns:
            True 如果是明細規格表，否則 False
        """
        role, _ = self.detect_role(filename)
        return role == "detail_spec"

    def is_floor_plan(self, filename: str) -> bool:
        """
        檢查檔案是否為平面圖.

        Args:
            filename: PDF 檔案名稱

        Returns:
            True 如果是平面圖，否則 False
        """
        role, _ = self.detect_role(filename)
        return role == "floor_plan"

    def get_role_display_name(self, role: DocumentRole) -> str:
        """
        取得角色的中文顯示名稱.

        Args:
            role: 文件角色

        Returns:
            中文顯示名稱
        """
        display_names = {
            "quantity_summary": "數量總表",
            "detail_spec": "明細規格表",
            "floor_plan": "平面圖",
            "unknown": "未知",
        }
        return display_names.get(role, "未知")


# 工廠函式
def get_document_role_detector_service() -> DocumentRoleDetectorService:
    """
    取得 DocumentRoleDetectorService 單例實例.

    Returns:
        DocumentRoleDetectorService 實例
    """
    return DocumentRoleDetectorService()
