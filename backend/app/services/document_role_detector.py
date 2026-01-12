"""PDF 文件角色偵測服務.

根據檔名關鍵字自動識別 PDF 文件在跨表合併中的角色。
支援從 MergeRulesSkill 載入關鍵字配置，並提供 fallback 預設值。
新增內容掃描功能，當檔名無法判斷時，掃描 PDF 前幾頁內容。
"""

import logging
from typing import Optional, Tuple

import fitz  # PyMuPDF

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

DEFAULT_FABRIC_SPEC_KEYWORDS = [
    "fabric",
    "leather",
    "vinyl",
    "textile",
    "upholstery",
    "面料",
    "布料",
    "皮革",
]

# ============================================================
# 內容掃描關鍵字（用於檔名無法判斷時）
# ============================================================

QUANTITY_CONTENT_KEYWORDS = [
    "total qty",
    "quantity summary",
    "overall qty",
    "qty summary",
    "數量總表",
    "總數量",
    "total quantity",
]

DETAIL_CONTENT_KEYWORDS = [
    "item no.:",
    "item no:",
    "project:",
    "description:",
    "furniture com:",
    "attachments:",
]

# 面料規格表內容關鍵字（用於區分家具和面料明細）
FABRIC_CONTENT_KEYWORDS = [
    "item:",  # 面料格式：ITEM: FAB-XXX @ Location
    "vendor:",
    "pattern:",
    "color:",
    "content:",
    "width:",
    "repeat:",
    "martindale",
    "abrasion",
    "vinyl",
    "fabric",
    "leather",
    "textile",
]

DEFAULT_DISPLAY_NAMES = {
    "quantity_summary": "數量總表",
    "detail_spec": "家具明細規格表",
    "fabric_spec": "面料明細規格表",
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

    def _get_fabric_spec_keywords(self) -> list[str]:
        """取得面料規格表關鍵字."""
        return DEFAULT_FABRIC_SPEC_KEYWORDS

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

        # 檢查是否為面料規格表
        for keyword in self._get_fabric_spec_keywords():
            if keyword.lower() in filename_lower:
                return "fabric_spec", "filename"

        # 檢查是否為平面圖
        for keyword in self._get_floor_plan_keywords():
            if keyword.lower() in filename_lower:
                return "floor_plan", "filename"

        # 預設為明細規格表（家具）
        return "detail_spec", "filename"

    def detect_role_with_content(
        self,
        filename: str,
        file_path: str,
        scan_pages: int = 3,
    ) -> Tuple[DocumentRole, RoleDetectionMethod]:
        """
        優先用檔名判斷，失敗時掃描內容.

        當檔名無法明確判斷時（fallback 到 detail_spec），
        會掃描 PDF 前幾頁內容來判斷文件角色。

        Args:
            filename: PDF 檔名
            file_path: PDF 檔案路徑
            scan_pages: 掃描前 N 頁（預設 3 頁）

        Returns:
            (角色, 偵測方式) 元組

        Examples:
            >>> service = DocumentRoleDetectorService()
            >>> service.detect_role_with_content("random.pdf", "/path/to/qty.pdf")
            ('quantity_summary', 'content')
        """
        # 1. 先嘗試檔名偵測
        role, method = self.detect_role(filename)

        # 如果檔名能明確判斷（非 fallback），直接返回
        if role != "detail_spec":
            logger.debug(f"Role detected by filename: {filename} → {role}")
            return role, method

        # 2. 檔名不明確時，掃描內容
        logger.info(f"Filename ambiguous, scanning content: {filename} (path: {file_path})")
        try:
            content_role = self._scan_content(file_path, scan_pages)
            if content_role:
                logger.info(
                    f"Role detected by content scan: {filename} → {content_role}"
                )
                return content_role, "content"
            else:
                logger.info(f"Content scan returned None for {filename}")
        except Exception as e:
            logger.warning(f"Content scan failed for {filename}: {e}", exc_info=True)

        # 3. 最終 fallback
        logger.debug(f"Role fallback to detail_spec: {filename}")
        return role, method

    def _scan_content(
        self, file_path: str, max_pages: int = 3
    ) -> Optional[DocumentRole]:
        """
        掃描 PDF 前幾頁內容判斷角色.

        優先順序：
        1. 數量總表關鍵字（如 total qty, quantity summary）
        2. 面料規格表關鍵字（如 vendor:, pattern:, color:）
        3. 家具明細規格表關鍵字（如 furniture com:, item no.:）

        Args:
            file_path: PDF 檔案路徑
            max_pages: 掃描頁數上限

        Returns:
            偵測到的角色，或 None 表示無法判斷
        """
        doc = fitz.open(file_path)
        try:
            # 提取前 N 頁文字
            text = ""
            for i in range(min(max_pages, doc.page_count)):
                text += doc[i].get_text().lower()

            logger.info(f"Content scan extracted {len(text)} chars from {max_pages} pages")

            # 1. 檢查數量總表關鍵字（最高優先）
            for keyword in QUANTITY_CONTENT_KEYWORDS:
                if keyword in text:
                    logger.info(f"Found quantity keyword: '{keyword}'")
                    return "quantity_summary"

            # 2. 計算面料和家具關鍵字匹配數量
            fabric_matches = sum(1 for kw in FABRIC_CONTENT_KEYWORDS if kw in text)
            detail_matches = sum(1 for kw in DETAIL_CONTENT_KEYWORDS if kw in text)

            logger.debug(
                f"Content keyword matches: fabric={fabric_matches}, detail={detail_matches}"
            )

            # 3. 面料規格表：需要至少 3 個面料關鍵字（如 vendor, pattern, color）
            if fabric_matches >= 3:
                logger.info(
                    f"Detected fabric_spec by content: {fabric_matches} fabric keywords matched"
                )
                return "fabric_spec"

            # 4. 家具明細規格表：有明細關鍵字但面料關鍵字不足
            if detail_matches > 0:
                logger.debug(f"Found detail spec keyword, matches={detail_matches}")
                return "detail_spec"

            logger.debug("No matching keywords found in content")
            return None
        finally:
            doc.close()

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
