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


class PageOffsetConfig(BaseModel):
    """頁面偏移配置（圖片在規格頁後幾頁）."""

    default: int = Field(1, description="預設頁面偏移")
    by_document_type: dict[str, int] = Field(
        default_factory=dict,
        description="依文件類型的頁面偏移（如 furniture_specification: 1）"
    )

    def get_offset(self, document_type: Optional[str] = None) -> int:
        """取得指定文件類型的頁面偏移.

        Args:
            document_type: 文件類型（如 'furniture_specification'）

        Returns:
            頁面偏移值，若文件類型不存在則回傳預設值
        """
        if document_type and document_type in self.by_document_type:
            return self.by_document_type[document_type]
        return self.default


class ImageExtractionConfig(BaseModel):
    """圖片抓取配置."""

    product_image: ProductImageConfig = Field(default_factory=ProductImageConfig)
    exclusions: list[ImageExclusionRule] = Field(default_factory=list)
    page_offset: PageOffsetConfig = Field(default_factory=PageOffsetConfig)


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
    requires: Optional[dict[str, str]] = Field(
        default=None,
        description="版本依賴聲明，如 {'merge_rules': '>=1.1.0', 'output_format': '>=1.0.0'}"
    )


# ============================================================
# OutputFormatSkill 模型定義
# ============================================================


class FormatInfo(BaseModel):
    """輸出格式基本資訊."""

    name: str = Field(..., description="格式名稱")
    identifier: str = Field(..., description="格式識別碼")
    version: str = Field("1.0.0", description="配置版本")


class CompanyInfo(BaseModel):
    """公司資訊."""

    name: str = Field(..., description="公司名稱")
    address: str = Field("", description="地址")
    phone: str = Field("", description="電話")
    fax: str = Field("", description="傳真")
    website: str = Field("", description="網站")
    logo_file: str = Field("", description="Logo 檔案路徑")


class LogoConfig(BaseModel):
    """Logo 配置."""

    position: str = Field("A1", description="Logo 位置")
    width_px: int = Field(280, description="寬度（像素）")
    height_px: int = Field(75, description="高度（像素）")
    span_cols: int = Field(3, description="跨越欄數")
    span_rows: int = Field(3, description="跨越列數")


class LayoutConfig(BaseModel):
    """版面配置."""

    sheet_name: str = Field("報價單", description="工作表名稱")
    rows: dict[str, int] = Field(
        default_factory=lambda: {"header_start": 1, "data_header": 16, "data_start": 17}
    )
    logo: LogoConfig = Field(default_factory=LogoConfig)


class ImageColumnConfig(BaseModel):
    """圖片欄位配置."""

    width_px: int = Field(105, description="圖片寬度")
    height_px: int = Field(75, description="圖片高度")
    row_height_px: int = Field(90, description="列高度")


class ConditionalDisplay(BaseModel):
    """條件顯示配置."""

    show_only_for: str = Field("", description="僅對特定類別顯示")


class ColumnDefinition(BaseModel):
    """欄位定義."""

    header: str = Field(..., description="欄位標題")
    field: str = Field(..., description="對應資料欄位")
    width: int = Field(10, description="欄位寬度")
    alignment: str = Field("left", description="對齊方式")
    description: str = Field("", description="欄位說明")
    type: str = Field("text", description="類型：text, image")
    number_format: Optional[str] = Field(None, description="數字格式")
    formula: Optional[str] = Field(None, description="Excel 公式")
    editable: bool = Field(False, description="是否可編輯")
    image_config: Optional[ImageColumnConfig] = Field(None, description="圖片配置")
    conditional: Optional[ConditionalDisplay] = Field(None, description="條件顯示")


class HeaderStyle(BaseModel):
    """標題列樣式."""

    fill_color: str = Field("366092", description="背景色")
    font_color: str = Field("FFFFFF", description="字體色")
    font_size: int = Field(11, description="字體大小")
    font_bold: bool = Field(True, description="粗體")
    alignment: str = Field("center", description="對齊")
    wrap_text: bool = Field(True, description="自動換行")
    row_height: int = Field(25, description="列高")


class DataStyle(BaseModel):
    """資料列樣式."""

    border: str = Field("thin", description="邊框樣式")
    row_height: int = Field(85, description="列高")


class TitleStyle(BaseModel):
    """標題樣式."""

    font_size: int = Field(18, description="字體大小")
    font_bold: bool = Field(True, description="粗體")


class StylesConfig(BaseModel):
    """樣式配置."""

    header: HeaderStyle = Field(default_factory=HeaderStyle)
    data: DataStyle = Field(default_factory=DataStyle)
    title: TitleStyle = Field(default_factory=TitleStyle)


class HeaderFieldConfig(BaseModel):
    """表頭欄位配置."""

    label: str = Field(..., description="欄位標籤")
    row: int = Field(..., description="列位置")
    col: int = Field(..., description="欄位置")
    value_col: Optional[int] = Field(None, description="值的欄位置")
    value_field: Optional[str] = Field(None, description="對應資料欄位")
    value_from: Optional[str] = Field(None, description="值來源")
    prefix: str = Field("", description="前綴")
    default_value: Optional[str] = Field(None, description="預設值")
    format: Optional[str] = Field(None, description="格式化")
    style: Optional[str] = Field(None, description="樣式")


class TermsConfig(BaseModel):
    """條款配置."""

    header: str = Field("Terms & Remarks:", description="條款標題")
    items: list[str] = Field(default_factory=list, description="條款列表")


class OutputFormatSkill(BaseModel):
    """輸出格式 Skill 完整配置."""

    format: FormatInfo
    company: CompanyInfo
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    columns: list[ColumnDefinition] = Field(default_factory=list)
    styles: StylesConfig = Field(default_factory=StylesConfig)
    header_fields: list[HeaderFieldConfig] = Field(default_factory=list)
    terms: TermsConfig = Field(default_factory=TermsConfig)

    @property
    def version(self) -> str:
        """取得配置版本."""
        return self.format.version

    @property
    def data_header_row(self) -> int:
        """取得欄位標題列."""
        return self.layout.rows.get("data_header", 16)

    @property
    def data_start_row(self) -> int:
        """取得資料起始列."""
        return self.layout.rows.get("data_start", 17)


# ============================================================
# MergeRulesSkill 模型定義
# ============================================================


class RulesInfo(BaseModel):
    """合併規則基本資訊."""

    name: str = Field(..., description="規則名稱")
    identifier: str = Field(..., description="規則識別碼")
    version: str = Field("1.0.0", description="配置版本")


class RoleKeywordsConfig(BaseModel):
    """角色關鍵字配置."""

    filename_keywords: list[str] = Field(default_factory=list, description="檔名關鍵字")
    content_indicators: list[str] = Field(default_factory=list, description="內容指標")
    display_name: str = Field("", description="顯示名稱")


class RoleDetectionRulesConfig(BaseModel):
    """文件角色偵測規則."""

    quantity_summary: RoleKeywordsConfig = Field(default_factory=RoleKeywordsConfig)
    detail_spec: RoleKeywordsConfig = Field(default_factory=RoleKeywordsConfig)
    floor_plan: RoleKeywordsConfig = Field(default_factory=RoleKeywordsConfig)
    unknown: RoleKeywordsConfig = Field(default_factory=RoleKeywordsConfig)


class FieldMergeStrategy(BaseModel):
    """欄位合併策略."""

    description: str = Field("", description="策略說明")
    priority: str = Field("upload_order", description="優先順序")
    fill_empty: bool = Field(True, description="填補空值")
    mode: str = Field("override", description="模式：override, concatenate, first_non_empty")
    separator: str = Field("", description="分隔符")


class FieldMergeConfig(BaseModel):
    """欄位合併配置."""

    mergeable_fields: list[str] = Field(default_factory=list, description="可合併欄位")
    strategies: dict[str, FieldMergeStrategy] = Field(default_factory=dict, description="欄位策略")


class ImageMergeConfig(BaseModel):
    """圖片合併配置."""

    strategy: str = Field("highest_resolution", description="策略")
    description: str = Field("", description="說明")
    fallback_order: list[str] = Field(default_factory=list, description="fallback 順序")




class ItemNoNormalizationConfig(BaseModel):
    """Item No. 正規化配置（邏輯硬編碼，僅保留警告開關）."""

    warn_on_format_difference: bool = Field(True, description="格式差異警告")


class ConstraintsConfig(BaseModel):
    """合併限制配置."""

    max_quantity_summary_docs: int = Field(1, description="最大數量總表數")
    error_message_multiple_qty: str = Field("上傳多份數量總表，請僅保留一份")
    min_detail_spec_docs: int = Field(1, description="最小明細規格表數")
    error_message_no_detail: str = Field("未上傳明細規格表，無法進行合併")
    max_items_per_merge: int = Field(1000, description="最大合併項目數")


class MergeStatusConfig(BaseModel):
    """合併狀態配置."""

    description: str = Field("", description="狀態說明")
    display_name: str = Field("", description="顯示名稱")
    color: str = Field("", description="顏色")


class WarningTemplates(BaseModel):
    """警告訊息模板."""

    quantity_only: str = Field("Item No. '{item_no}' 僅在數量總表中，無對應明細規格")
    format_mismatch: str = Field("Item No. 格式不一致: '{original}' → '{normalized}'")


class ReportConfig(BaseModel):
    """報告配置."""

    statuses: dict[str, MergeStatusConfig] = Field(default_factory=dict, description="狀態定義")
    warnings: WarningTemplates = Field(default_factory=WarningTemplates)


class FabricDetectionConfig(BaseModel):
    """面料偵測配置.

    歸屬說明：
    - 此配置屬於「客戶輸出需求」而非「供應商 PDF 格式」
    - 建議放在 core/merge-rules.yaml 中
    - 為向後相容，也支援從 vendors/*.yaml 載入
    """

    pattern: str = Field(
        r"\s+to\s+([A-Z0-9][A-Z0-9\-\.]+)",
        description="從 description 提取目標家具 item_no 的正規表達式（支援含 . 的編號）"
    )
    description: str = Field("", description="說明")
    belongs_to: Optional[str] = Field(
        default=None,
        description="歸屬標記：'output_format' 表示客戶輸出需求，'vendor' 表示供應商特定"
    )


class MergeRulesSkill(BaseModel):
    """合併規則 Skill 完整配置.

    注意：
    - 排序邏輯（fabric_follows_furniture）硬編碼於 merge_service.py
    - fabric_detection 建議放在此處（客戶輸出需求）
    - 為向後相容，也支援從 VendorSkill 載入
    """

    rules: RulesInfo
    role_detection: RoleDetectionRulesConfig = Field(default_factory=RoleDetectionRulesConfig)
    field_merge: FieldMergeConfig = Field(default_factory=FieldMergeConfig)
    image_merge: ImageMergeConfig = Field(default_factory=ImageMergeConfig)
    item_no_normalization: ItemNoNormalizationConfig = Field(default_factory=ItemNoNormalizationConfig)
    constraints: ConstraintsConfig = Field(default_factory=ConstraintsConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    fabric_detection: Optional[FabricDetectionConfig] = Field(
        default=None,
        description="面料偵測配置（建議放在此處，屬於客戶輸出需求）"
    )

    @property
    def version(self) -> str:
        """取得配置版本."""
        return self.rules.version

    @property
    def mergeable_fields(self) -> list[str]:
        """取得可合併欄位列表."""
        return self.field_merge.mergeable_fields


class DimensionFormattingConfig(BaseModel):
    """Dimension 格式化配置."""

    fabric_keywords: list[str] = Field(
        default=["fabric", "leather", "textile", "upholstery", "vinyl", "面料", "皮革", "布料"],
        description="面料相關關鍵字（用於判斷 is_fabric）"
    )
    circular_keywords: list[str] = Field(
        default=["dia", "dia.", "diameter", "ø", "Ø"],
        description="圓形家具關鍵字（用於判斷 is_circular）"
    )
    fabric_format_prefixes: list[str] = Field(
        default=["vinyl", "fabric", "leather", "textile"],
        description="完整面料格式的開頭前綴（用於早期返回）"
    )


class VendorSkill(BaseModel):
    """供應商 Skill 完整配置."""

    vendor: VendorInfo
    document_structure: dict[str, Any] = Field(default_factory=dict)
    image_extraction: ImageExtractionConfig = Field(default_factory=ImageExtractionConfig)
    field_extraction: dict[str, Any] = Field(default_factory=dict)
    role_detection: RoleDetectionConfig = Field(default_factory=RoleDetectionConfig)
    dimension_formatting: DimensionFormattingConfig = Field(default_factory=DimensionFormattingConfig)
    fabric_detection: FabricDetectionConfig = Field(default_factory=FabricDetectionConfig)
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
        self._vendor_cache: dict[str, VendorSkill] = {}
        self._output_format_cache: dict[str, OutputFormatSkill] = {}
        self._merge_rules_cache: dict[str, MergeRulesSkill] = {}

    def load_vendor(self, vendor_id: str) -> VendorSkill:
        """載入供應商配置.

        支援兩種載入方式：
        1. 目錄式：vendors/{vendor_id}/ 目錄下的多個 YAML 檔案
        2. 單檔式：vendors/{vendor_id}.yaml 單一檔案（向後相容）

        Args:
            vendor_id: 供應商識別碼（如 "habitus"）

        Returns:
            VendorSkill 配置物件

        Raises:
            SkillNotFoundError: 找不到配置檔
            SkillParseError: 配置檔解析失敗
        """
        # 檢查快取
        if self.cache_enabled and vendor_id in self._vendor_cache:
            logger.debug(f"從快取載入供應商配置: {vendor_id}")
            return self._vendor_cache[vendor_id]

        # 優先嘗試目錄式載入
        vendor_dir = self.skills_dir / "vendors" / vendor_id
        if vendor_dir.is_dir():
            skill = self._load_vendor_from_directory(vendor_dir, vendor_id)
        else:
            # 向後相容：單檔載入
            skill = self._load_vendor_from_file(vendor_id)

        # 存入快取
        if self.cache_enabled:
            self._vendor_cache[vendor_id] = skill
            logger.info(f"載入並快取供應商配置: {vendor_id}")
        else:
            logger.info(f"載入供應商配置（無快取）: {vendor_id}")

        return skill

    def _load_vendor_from_file(self, vendor_id: str) -> VendorSkill:
        """從單一 YAML 檔案載入供應商配置（向後相容）."""
        path = self.skills_dir / "vendors" / f"{vendor_id}.yaml"
        if not path.exists():
            raise SkillNotFoundError(f"找不到供應商配置檔: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析失敗: {e}")

        try:
            return VendorSkill(**data)
        except Exception as e:
            raise SkillParseError(f"配置驗證失敗: {e}")

    def _load_vendor_from_directory(self, vendor_dir: Path, vendor_id: str) -> VendorSkill:
        """從目錄載入供應商配置（漸進式揭露設計）.

        目錄結構：
            vendors/{vendor_id}/
            ├── _vendor.yaml           # 基本識別（必要）
            ├── document-types.yaml    # 文件類型定義（選用）
            ├── page-structure.yaml    # 頁面結構（選用）
            ├── image-extraction.yaml  # 圖片規則（選用）
            ├── field-extraction.yaml  # 欄位提取（選用）
            ├── dimension-rules.yaml   # Dimension 格式化（選用）
            ├── fabric-detection.yaml  # 面料偵測（選用）
            └── prompts/
                ├── parse-specification.yaml
                ├── parse-quantity-summary.yaml
                └── parse-project-metadata.yaml
        """
        data: dict[str, Any] = {}

        # 1. 載入必要的 _vendor.yaml
        vendor_file = vendor_dir / "_vendor.yaml"
        if not vendor_file.exists():
            raise SkillNotFoundError(f"找不到供應商識別檔: {vendor_file}")

        try:
            with open(vendor_file, "r", encoding="utf-8") as f:
                vendor_data = yaml.safe_load(f) or {}
            data.update(vendor_data)
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析失敗 (_vendor.yaml): {e}")

        # 2. 載入選用的配置檔案
        optional_files = [
            ("document-types.yaml", "document_types"),
            ("document-structure.yaml", "document_structure"),
            ("image-extraction.yaml", "image_extraction"),
            ("field-extraction.yaml", "field_extraction"),
            ("dimension-rules.yaml", "dimension_formatting"),
            ("fabric-detection.yaml", "fabric_detection"),
        ]

        for filename, key in optional_files:
            file_path = vendor_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_data = yaml.safe_load(f) or {}
                    # 支援直接使用 key 或巢狀結構
                    if key in file_data:
                        data[key] = file_data[key]
                    else:
                        data[key] = file_data
                except yaml.YAMLError as e:
                    raise SkillParseError(f"YAML 解析失敗 ({filename}): {e}")

        # 3. 載入 prompts 目錄
        prompts_dir = vendor_dir / "prompts"
        if prompts_dir.is_dir():
            prompts_data: dict[str, Any] = {}
            prompt_files = [
                ("parse-specification.yaml", "parse_specification"),
                ("parse-quantity-summary.yaml", "parse_quantity_summary"),
                ("parse-project-metadata.yaml", "parse_project_metadata"),
                ("classify-image.yaml", "classify_image"),
            ]

            for filename, key in prompt_files:
                file_path = prompts_dir / filename
                if file_path.exists():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            prompt_data = yaml.safe_load(f) or {}

                        # 支援外部模板檔案：user_template_file
                        prompt_data = self._resolve_external_template(prompt_data, prompts_dir)
                        prompts_data[key] = prompt_data
                    except yaml.YAMLError as e:
                        raise SkillParseError(f"YAML 解析失敗 (prompts/{filename}): {e}")

            if prompts_data:
                data["prompts"] = prompts_data

        # 解析為 Pydantic 模型
        try:
            return VendorSkill(**data)
        except Exception as e:
            raise SkillParseError(f"配置驗證失敗: {e}")

    def validate_dependencies(self, vendor_skill: VendorSkill) -> tuple[bool, list[str]]:
        """驗證供應商配置的版本依賴.

        Args:
            vendor_skill: 供應商配置

        Returns:
            (is_valid, errors) 元組，is_valid 為 True 表示所有依賴滿足
        """
        if vendor_skill.vendor.requires is None:
            return True, []

        errors: list[str] = []

        for dep_type, required_version in vendor_skill.vendor.requires.items():
            actual_version: Optional[str] = None

            if dep_type == "merge_rules":
                try:
                    merge_rules = self.load_merge_rules("merge-rules")
                    actual_version = merge_rules.version
                except (SkillNotFoundError, SkillParseError):
                    errors.append(f"無法載入 merge_rules 配置")
                    continue
            elif dep_type == "output_format":
                try:
                    output_format = self.load_output_format("fairmont")
                    actual_version = output_format.version
                except (SkillNotFoundError, SkillParseError):
                    errors.append(f"無法載入 output_format 配置")
                    continue

            if actual_version:
                if not self._version_satisfies(actual_version, required_version):
                    errors.append(
                        f"{dep_type} 版本不相容: 需要 {required_version}, 實際為 {actual_version}"
                    )

        return len(errors) == 0, errors

    def get_disclosure_levels(self, vendor_id: str) -> dict[str, Optional[int]]:
        """取得供應商配置的揭露層級標記.

        揭露層級說明：
        - L1 (1): 識別層 - 快速識別用（name, identifier, version）
        - L2 (2): 結構層 - 初始化時載入（document_types, columns）
        - L3 (3): 規則層 - 特定場景按需載入（field_extraction, exclusions）
        - L4 (4): 執行層 - LLM 呼叫時才載入（prompts）

        Args:
            vendor_id: 供應商識別碼

        Returns:
            各區塊的揭露層級 dict，如 {"vendor": 1, "prompts.parse_specification": 4}
        """
        levels: dict[str, Optional[int]] = {}
        vendor_dir = self.skills_dir / "vendors" / vendor_id

        if not vendor_dir.is_dir():
            # 單檔模式：從單一 YAML 載入
            single_file = self.skills_dir / "vendors" / f"{vendor_id}.yaml"
            if single_file.exists():
                try:
                    with open(single_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    self._extract_disclosure_levels(data, "", levels)
                except yaml.YAMLError:
                    pass
            return levels

        # 目錄模式
        # 1. _vendor.yaml
        vendor_file = vendor_dir / "_vendor.yaml"
        if vendor_file.exists():
            try:
                with open(vendor_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if "vendor" in data and isinstance(data["vendor"], dict):
                    level = data["vendor"].get("_disclosure_level")
                    if level is not None:
                        levels["vendor"] = level
            except yaml.YAMLError:
                pass

        # 2. 其他配置檔案
        config_files = [
            ("document-types.yaml", "document_types"),
            ("image-extraction.yaml", "image_extraction"),
            ("field-extraction.yaml", "field_extraction"),
            ("dimension-rules.yaml", "dimension_formatting"),
            ("fabric-detection.yaml", "fabric_detection"),
        ]

        for filename, key in config_files:
            file_path = vendor_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    level = data.get("_disclosure_level")
                    if level is not None:
                        levels[key] = level
                except yaml.YAMLError:
                    pass

        # 3. prompts 目錄
        prompts_dir = vendor_dir / "prompts"
        if prompts_dir.is_dir():
            prompt_files = [
                ("parse-specification.yaml", "prompts.parse_specification"),
                ("parse-quantity-summary.yaml", "prompts.parse_quantity_summary"),
                ("parse-project-metadata.yaml", "prompts.parse_project_metadata"),
            ]
            for filename, key in prompt_files:
                file_path = prompts_dir / filename
                if file_path.exists():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        level = data.get("_disclosure_level")
                        if level is not None:
                            levels[key] = level
                    except yaml.YAMLError:
                        pass

        return levels

    def _extract_disclosure_levels(
        self, data: dict[str, Any], prefix: str, levels: dict[str, Optional[int]]
    ) -> None:
        """遞迴提取揭露層級標記（用於單檔模式）."""
        for key, value in data.items():
            if key == "_disclosure_level" and isinstance(value, int):
                # 將此層級記錄到父節點
                parent_key = prefix.rstrip(".")
                if parent_key:
                    levels[parent_key] = value
            elif isinstance(value, dict):
                new_prefix = f"{prefix}{key}." if prefix else f"{key}."
                # 檢查這個 dict 是否有 _disclosure_level
                if "_disclosure_level" in value:
                    key_path = f"{prefix}{key}" if prefix else key
                    levels[key_path] = value["_disclosure_level"]
                self._extract_disclosure_levels(value, new_prefix, levels)

    def validate_against_schema(self, skill_id: str, skill_type: str) -> tuple[bool, list[str]]:
        """使用 JSON Schema 驗證配置.

        Args:
            skill_id: Skill 識別碼（如 "habitus", "fairmont"）
            skill_type: Skill 類型（"vendor", "output_format", "merge_rules"）

        Returns:
            (is_valid, errors) 元組
        """
        import json

        # 決定 schema 和配置檔案路徑
        schema_path = self.skills_dir / "schemas" / f"{skill_type}.schema.json"
        if not schema_path.exists():
            logger.warning(f"Schema 檔案不存在，跳過驗證: {schema_path}")
            return True, []

        # 決定配置檔案路徑
        if skill_type == "vendor":
            config_path = self.skills_dir / "vendors" / f"{skill_id}.yaml"
        elif skill_type == "output_format":
            config_path = self.skills_dir / "output-formats" / f"{skill_id}.yaml"
        elif skill_type == "merge_rules":
            config_path = self.skills_dir / "core" / f"{skill_id}.yaml"
        else:
            return False, [f"不支援的 skill_type: {skill_type}"]

        if not config_path.exists():
            return False, [f"配置檔案不存在: {config_path}"]

        # 載入 schema
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            return False, [f"Schema 解析失敗: {e}"]

        # 載入配置
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return False, [f"配置解析失敗: {e}"]

        # 使用 jsonschema 驗證
        try:
            import jsonschema
            jsonschema.validate(instance=config, schema=schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e.message)]
        except jsonschema.SchemaError as e:
            return False, [f"Schema 無效: {e.message}"]
        except ImportError:
            logger.warning("jsonschema 套件未安裝，跳過 Schema 驗證")
            return True, []

    def _version_satisfies(self, actual: str, required: str) -> bool:
        """檢查實際版本是否滿足要求.

        支援的運算符：>=, >, <=, <, ==, =

        Args:
            actual: 實際版本（如 "1.1.0"）
            required: 要求版本（如 ">=1.1.0"）

        Returns:
            True 如果滿足要求
        """
        import re

        # 解析運算符和版本
        match = re.match(r'^(>=|>|<=|<|==|=)?(\d+\.\d+\.\d+)$', required)
        if not match:
            logger.warning(f"無效的版本要求格式: {required}")
            return True  # 無效格式時通過

        operator = match.group(1) or "=="
        required_version = match.group(2)

        # 解析版本為元組以進行比較
        def parse_version(v: str) -> tuple[int, int, int]:
            parts = v.split(".")
            return (int(parts[0]), int(parts[1]), int(parts[2]))

        try:
            actual_tuple = parse_version(actual)
            required_tuple = parse_version(required_version)
        except (ValueError, IndexError):
            return True  # 無效版本格式時通過

        if operator in (">=",):
            return actual_tuple >= required_tuple
        elif operator in (">",):
            return actual_tuple > required_tuple
        elif operator in ("<=",):
            return actual_tuple <= required_tuple
        elif operator in ("<",):
            return actual_tuple < required_tuple
        else:  # == or =
            return actual_tuple == required_tuple

    def _resolve_external_template(self, prompt_data: dict[str, Any], prompts_dir: Path) -> dict[str, Any]:
        """解析外部 Prompt 模板檔案.

        支援 user_template_file 和 system_file 欄位，
        從指定的外部檔案載入模板內容。

        Args:
            prompt_data: 原始 prompt 配置 dict
            prompts_dir: prompts 目錄路徑

        Returns:
            處理後的 prompt 配置 dict，外部模板已載入為字串
        """
        result = prompt_data.copy()

        # 處理 user_template_file
        if "user_template_file" in result:
            template_path = prompts_dir / result["user_template_file"]
            if template_path.exists():
                try:
                    with open(template_path, "r", encoding="utf-8") as f:
                        result["user_template"] = f.read()
                except IOError as e:
                    raise SkillParseError(f"無法讀取外部模板檔案: {template_path}: {e}")
            else:
                raise SkillParseError(f"找不到外部模板檔案: {template_path}")
            # 移除 user_template_file 欄位
            del result["user_template_file"]

        # 處理 system_file（可選）
        if "system_file" in result:
            system_path = prompts_dir / result["system_file"]
            if system_path.exists():
                try:
                    with open(system_path, "r", encoding="utf-8") as f:
                        result["system"] = f.read()
                except IOError as e:
                    raise SkillParseError(f"無法讀取外部 system 檔案: {system_path}: {e}")
            else:
                raise SkillParseError(f"找不到外部 system 檔案: {system_path}")
            del result["system_file"]

        return result

    def load_output_format(self, format_id: str) -> OutputFormatSkill:
        """載入輸出格式配置.

        Args:
            format_id: 格式識別碼（如 "fairmont"）

        Returns:
            OutputFormatSkill 配置物件

        Raises:
            SkillNotFoundError: 找不到配置檔
            SkillParseError: 配置檔解析失敗
        """
        # 檢查快取
        if self.cache_enabled and format_id in self._output_format_cache:
            logger.debug(f"從快取載入輸出格式配置: {format_id}")
            return self._output_format_cache[format_id]

        # 載入 YAML 檔案
        path = self.skills_dir / "output-formats" / f"{format_id}.yaml"
        if not path.exists():
            raise SkillNotFoundError(f"找不到輸出格式配置檔: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析失敗: {e}")

        # 解析為 Pydantic 模型
        try:
            skill = OutputFormatSkill(**data)
        except Exception as e:
            raise SkillParseError(f"配置驗證失敗: {e}")

        # 存入快取
        if self.cache_enabled:
            self._output_format_cache[format_id] = skill
            logger.info(f"載入並快取輸出格式配置: {format_id}")
        else:
            logger.info(f"載入輸出格式配置（無快取）: {format_id}")

        return skill

    def load_output_format_or_default(self, format_id: str = "fairmont") -> Optional[OutputFormatSkill]:
        """載入輸出格式配置，失敗時回傳 None（用於 fallback 模式）.

        Args:
            format_id: 格式識別碼

        Returns:
            OutputFormatSkill 或 None（載入失敗時）
        """
        try:
            return self.load_output_format(format_id)
        except (SkillNotFoundError, SkillParseError) as e:
            logger.warning(f"載入輸出格式配置失敗，將使用預設值: {e}")
            return None

    def load_merge_rules(self, rules_id: str) -> MergeRulesSkill:
        """載入合併規則配置.

        Args:
            rules_id: 規則識別碼（如 "merge-rules"）

        Returns:
            MergeRulesSkill 配置物件

        Raises:
            SkillNotFoundError: 找不到配置檔
            SkillParseError: 配置檔解析失敗
        """
        # 檢查快取
        if self.cache_enabled and rules_id in self._merge_rules_cache:
            logger.debug(f"從快取載入合併規則配置: {rules_id}")
            return self._merge_rules_cache[rules_id]

        # 載入 YAML 檔案
        path = self.skills_dir / "core" / f"{rules_id}.yaml"
        if not path.exists():
            raise SkillNotFoundError(f"找不到合併規則配置檔: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise SkillParseError(f"YAML 解析失敗: {e}")

        # 解析為 Pydantic 模型
        try:
            skill = MergeRulesSkill(**data)
        except Exception as e:
            raise SkillParseError(f"配置驗證失敗: {e}")

        # 存入快取
        if self.cache_enabled:
            self._merge_rules_cache[rules_id] = skill
            logger.info(f"載入並快取合併規則配置: {rules_id}")
        else:
            logger.info(f"載入合併規則配置（無快取）: {rules_id}")

        return skill

    def load_merge_rules_or_default(self, rules_id: str = "merge-rules") -> Optional[MergeRulesSkill]:
        """載入合併規則配置，失敗時回傳 None（用於 fallback 模式）.

        Args:
            rules_id: 規則識別碼

        Returns:
            MergeRulesSkill 或 None（載入失敗時）
        """
        try:
            return self.load_merge_rules(rules_id)
        except (SkillNotFoundError, SkillParseError) as e:
            logger.warning(f"載入合併規則配置失敗，將使用預設值: {e}")
            return None

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

        支援目錄式和單檔式供應商配置。

        Returns:
            供應商識別碼列表
        """
        vendor_dir = self.skills_dir / "vendors"
        if not vendor_dir.exists():
            return []

        vendors: set[str] = set()

        # 1. 單檔式供應商（*.yaml）
        for p in vendor_dir.glob("*.yaml"):
            if not p.stem.startswith("_"):
                vendors.add(p.stem)

        # 2. 目錄式供應商（含 _vendor.yaml 的目錄）
        for d in vendor_dir.iterdir():
            if d.is_dir() and not d.name.startswith("_"):
                if (d / "_vendor.yaml").exists():
                    vendors.add(d.name)

        return sorted(vendors)

    def clear_cache(self) -> None:
        """清除所有快取."""
        self._vendor_cache.clear()
        self._output_format_cache.clear()
        self._merge_rules_cache.clear()
        logger.info("已清除所有 Skill 快取")

    def list_output_formats(self) -> list[str]:
        """列出所有可用的輸出格式.

        Returns:
            格式識別碼列表
        """
        output_dir = self.skills_dir / "output-formats"
        if not output_dir.exists():
            return []
        return [p.stem for p in output_dir.glob("*.yaml") if not p.stem.startswith("_")]

    def list_merge_rules(self) -> list[str]:
        """列出所有可用的合併規則.

        Returns:
            規則識別碼列表
        """
        core_dir = self.skills_dir / "core"
        if not core_dir.exists():
            return []
        return [p.stem for p in core_dir.glob("*.yaml") if not p.stem.startswith("_")]

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

    def get_fabric_detection(
        self,
        vendor_id: str = "habitus",
        merge_rules_id: str = "merge-rules"
    ) -> Optional[FabricDetectionConfig]:
        """取得面料偵測配置（便捷方法）.

        優先順序：
        1. core/merge-rules.yaml 的 fabric_detection（建議位置）
        2. vendors/{vendor_id}.yaml 的 fabric_detection（向後相容）

        Args:
            vendor_id: 供應商識別碼（用於向後相容）
            merge_rules_id: 合併規則識別碼

        Returns:
            FabricDetectionConfig 或 None
        """
        # 1. 優先從 merge-rules 載入
        try:
            merge_rules = self.load_merge_rules(merge_rules_id)
            if merge_rules.fabric_detection is not None:
                return merge_rules.fabric_detection
        except (SkillNotFoundError, SkillParseError):
            pass

        # 2. 向後相容：從 vendor 載入
        vendor_skill = self.load_vendor_or_default(vendor_id)
        if vendor_skill is not None:
            return vendor_skill.fabric_detection

        return None


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
