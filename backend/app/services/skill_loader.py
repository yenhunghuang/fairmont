"""Skill Loader Service - 載入並管理 Skill 配置檔.

提供供應商配置（圖片規則、Prompt 模板）的載入與快取功能。
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Pydantic 模型定義
# ============================================================


class ImageExclusionRule(BaseModel):
    """圖片排除規則."""

    type: str = Field(..., description="排除類型：logo, material_swatch, technical_drawing, hardware_detail")
    description: str = Field("", description="規則說明")
    rules: dict[str, Any] = Field(default_factory=dict, description="具體規則")


class ProductImageConfig(BaseModel):
    """產品圖選擇配置."""

    source_page: str = Field("attachment_page", description="來源頁面類型")
    selection_strategy: str = Field("largest_color_image", description="選擇策略")
    min_area_ratio: float = Field(0.1, description="最小面積比例")
    min_area_px: int = Field(10000, description="最小面積（像素）")
    characteristics: list[str] = Field(default_factory=list, description="特徵描述")


class ImageExtractionConfig(BaseModel):
    """圖片抓取配置."""

    product_image: ProductImageConfig = Field(default_factory=ProductImageConfig)
    exclusions: list[ImageExclusionRule] = Field(default_factory=list)


class PromptTemplate(BaseModel):
    """Prompt 模板."""

    system: str = Field("", description="系統提示")
    user_template: str = Field("", description="使用者提示模板")


class PromptsConfig(BaseModel):
    """Prompts 配置."""

    parse_specification: PromptTemplate = Field(default_factory=PromptTemplate)
    parse_quantity_summary: PromptTemplate = Field(default_factory=PromptTemplate)
    parse_project_metadata: PromptTemplate = Field(default_factory=PromptTemplate)
    classify_image: PromptTemplate = Field(default_factory=PromptTemplate)


class RoleDetectionConfig(BaseModel):
    """文件角色偵測配置."""

    quantity_summary: dict[str, Any] = Field(default_factory=dict)
    detail_specification: dict[str, Any] = Field(default_factory=dict)


class VendorInfo(BaseModel):
    """供應商基本資訊."""

    name: str = Field(..., description="供應商名稱")
    identifier: str = Field(..., description="供應商識別碼")
    version: str = Field("1.0.0", description="配置版本")


class VendorSkill(BaseModel):
    """供應商 Skill 完整配置."""

    vendor: VendorInfo
    document_structure: dict[str, Any] = Field(default_factory=dict)
    image_extraction: ImageExtractionConfig = Field(default_factory=ImageExtractionConfig)
    field_extraction: dict[str, Any] = Field(default_factory=dict)
    role_detection: RoleDetectionConfig = Field(default_factory=RoleDetectionConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)

    @property
    def version(self) -> str:
        """取得配置版本（便捷屬性）."""
        return self.vendor.version


# ============================================================
# 例外定義
# ============================================================


class SkillNotFoundError(Exception):
    """Skill 配置檔不存在."""

    pass


class SkillParseError(Exception):
    """Skill 配置檔解析失敗."""

    pass


# ============================================================
# Skill Loader 服務
# ============================================================


class SkillLoaderService:
    """Skill 載入器服務.

    使用方式：
        loader = get_skill_loader()
        vendor_skill = loader.load_vendor("habitus")
        image_rules = vendor_skill.image_extraction
        prompts = vendor_skill.prompts
    """

    def __init__(self, skills_dir: Optional[Path] = None, cache_enabled: bool = True):
        """初始化 Skill Loader.

        Args:
            skills_dir: Skills 目錄路徑，預設使用 settings.skills_dir_path
            cache_enabled: 是否啟用快取，預設使用 settings.skills_cache_enabled
        """
        self.skills_dir = skills_dir or settings.skills_dir_path
        self.cache_enabled = cache_enabled if cache_enabled is not None else settings.skills_cache_enabled
        self._cache: dict[str, VendorSkill] = {}

    def load_vendor(self, vendor_id: str) -> VendorSkill:
        """載入供應商配置.

        Args:
            vendor_id: 供應商識別碼（如 "habitus"）

        Returns:
            VendorSkill 配置物件

        Raises:
            SkillNotFoundError: 找不到配置檔
            SkillParseError: 配置檔解析失敗
        """
        # 檢查快取
        if self.cache_enabled and vendor_id in self._cache:
            logger.debug(f"從快取載入供應商配置: {vendor_id}")
            return self._cache[vendor_id]

        # 載入 YAML 檔案
        path = self.skills_dir / "vendors" / f"{vendor_id}.yaml"
        if not path.exists():
            raise SkillNotFoundError(f"找不到供應商配置檔: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析失敗: {e}")

        # 解析為 Pydantic 模型
        try:
            skill = VendorSkill(**data)
        except Exception as e:
            raise SkillParseError(f"配置驗證失敗: {e}")

        # 存入快取
        if self.cache_enabled:
            self._cache[vendor_id] = skill
            logger.info(f"載入並快取供應商配置: {vendor_id}")
        else:
            logger.info(f"載入供應商配置（無快取）: {vendor_id}")

        return skill

    def load_vendor_or_default(self, vendor_id: str = "habitus") -> Optional[VendorSkill]:
        """載入供應商配置，失敗時回傳 None（用於 fallback 模式）.

        Args:
            vendor_id: 供應商識別碼

        Returns:
            VendorSkill 或 None（載入失敗時）
        """
        try:
            return self.load_vendor(vendor_id)
        except (SkillNotFoundError, SkillParseError) as e:
            logger.warning(f"載入供應商配置失敗，將使用預設值: {e}")
            return None

    def list_vendors(self) -> list[str]:
        """列出所有可用的供應商.

        Returns:
            供應商識別碼列表
        """
        vendor_dir = self.skills_dir / "vendors"
        if not vendor_dir.exists():
            return []
        return [p.stem for p in vendor_dir.glob("*.yaml") if not p.stem.startswith("_")]

    def clear_cache(self) -> None:
        """清除快取."""
        self._cache.clear()
        logger.info("已清除 Skill 快取")

    def get_image_exclusion_rules(self, vendor_id: str = "habitus") -> list[ImageExclusionRule]:
        """取得圖片排除規則（便捷方法）.

        Args:
            vendor_id: 供應商識別碼

        Returns:
            排除規則列表，載入失敗時回傳空列表
        """
        skill = self.load_vendor_or_default(vendor_id)
        if skill is None:
            return []
        return skill.image_extraction.exclusions

    def get_prompt(self, vendor_id: str, prompt_type: str) -> Optional[PromptTemplate]:
        """取得 Prompt 模板（便捷方法）.

        Args:
            vendor_id: 供應商識別碼
            prompt_type: Prompt 類型（parse_specification, parse_quantity_summary, classify_image）

        Returns:
            PromptTemplate 或 None
        """
        skill = self.load_vendor_or_default(vendor_id)
        if skill is None:
            return None
        return getattr(skill.prompts, prompt_type, None)


# ============================================================
# 單例工廠
# ============================================================

_skill_loader_instance: Optional[SkillLoaderService] = None


def get_skill_loader() -> SkillLoaderService:
    """取得 SkillLoaderService 單例.

    Returns:
        SkillLoaderService 實例
    """
    global _skill_loader_instance
    if _skill_loader_instance is None:
        _skill_loader_instance = SkillLoaderService()
    return _skill_loader_instance


# 使用 lru_cache 快取（適用於模組層級快取）
@lru_cache(maxsize=32)
def load_vendor_cached(vendor_id: str) -> Optional[dict]:
    """快取版本的供應商配置載入（回傳原始 dict）.

    用於需要更細緻控制的場景。

    Args:
        vendor_id: 供應商識別碼

    Returns:
        原始配置 dict 或 None
    """
    loader = get_skill_loader()
    skill = loader.load_vendor_or_default(vendor_id)
    if skill is None:
        return None
    return skill.model_dump()
