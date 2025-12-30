"""PDF 文件角色偵測服務.

根據檔名關鍵字自動識別 PDF 文件在跨表合併中的角色。
支援從 MergeRulesSkill 載入關鍵字配置，並提供 fallback 預設值。
"""

import logging
from typing import Optional, Tuple

from app.models.source_document import DocumentRole, RoleDetectionMethod

logger = logging.getLogger(__name__)

# ============================================================
# Fallback 預設值（當 Skill 載入失敗時使用）
# ============================================================

DEFAULT_QUANTITY_SUMMARY_KEYWORDS = [
    "qty",
    "overall",
    "summary",
    "數量",
    "總量",
    "總表",
    "quantity",
    "quantities",
]

DEFAULT_FLOOR_PLAN_KEYWORDS = [
    "floor",
    "plan",
    "layout",
    "平面圖",
    "平面",
    "配置圖",
]

DEFAULT_DISPLAY_NAMES = {
    "quantity_summary": "數量總表",
    "detail_spec": "明細規格表",
    "floor_plan": "平面圖",
    "unknown": "未知",
}


class DocumentRoleDetectorService:
    """PDF 文件角色偵測服務.

    支援從 MergeRulesSkill 載入關鍵字配置，使用 Constructor Injection。
    """

    def __init__(self, skill_loader: Optional["SkillLoaderService"] = None):
        """初始化服務.

        Args:
            skill_loader: SkillLoaderService 實例，None 時使用全域單例
        """
        self._skill_loader = skill_loader
        self._merge_rules: Optional["MergeRulesSkill"] = None
        self._rules_loaded = False

    def _ensure_skill_loaded(self) -> None:
        """確保 Skill 已載入（懶載入）."""
        if self._rules_loaded:
            return

        if self._skill_loader is None:
            from app.services.skill_loader import get_skill_loader
            self._skill_loader = get_skill_loader()

        self._merge_rules = self._skill_loader.load_merge_rules_or_default("merge-rules")
        self._rules_loaded = True

    def _get_quantity_summary_keywords(self) -> list[str]:
        """取得數量總表關鍵字."""
        self._ensure_skill_loaded()
        if self._merge_rules:
            keywords = self._merge_rules.role_detection.quantity_summary.filename_keywords
            if keywords:
                return keywords
        return DEFAULT_QUANTITY_SUMMARY_KEYWORDS

    def _get_floor_plan_keywords(self) -> list[str]:
        """取得平面圖關鍵字."""
        self._ensure_skill_loaded()
        if self._merge_rules:
            keywords = self._merge_rules.role_detection.floor_plan.filename_keywords
            if keywords:
                return keywords
        return DEFAULT_FLOOR_PLAN_KEYWORDS

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
        for keyword in self._get_quantity_summary_keywords():
            if keyword.lower() in filename_lower:
                return "quantity_summary", "filename"

        # 檢查是否為平面圖
        for keyword in self._get_floor_plan_keywords():
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
        self._ensure_skill_loaded()

        # 嘗試從 Skill 取得顯示名稱
        if self._merge_rules:
            role_config = getattr(self._merge_rules.role_detection, role, None)
            if role_config and role_config.display_name:
                return role_config.display_name

        # Fallback 到預設值
        return DEFAULT_DISPLAY_NAMES.get(role, "未知")


# ============================================================
# 單例工廠
# ============================================================

_detector_instance: Optional[DocumentRoleDetectorService] = None


def get_document_role_detector_service(
    skill_loader: Optional["SkillLoaderService"] = None,
) -> DocumentRoleDetectorService:
    """
    取得 DocumentRoleDetectorService 單例實例.

    Args:
        skill_loader: 可選的 SkillLoaderService 實例

    Returns:
        DocumentRoleDetectorService 實例
    """
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = DocumentRoleDetectorService(skill_loader)
    return _detector_instance
