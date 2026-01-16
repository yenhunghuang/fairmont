"""Unit tests for SkillLoaderService."""

import tempfile
from pathlib import Path

import pytest
import yaml

from app.services.skill_loader import (
    ImageExclusionRule,
    PageOffsetConfig,
    PromptTemplate,
    SkillLoaderService,
    SkillNotFoundError,
    SkillParseError,
    get_skill_loader,
)


class TestSkillLoaderService:
    """SkillLoaderService 測試."""

    @pytest.fixture
    def temp_skills_dir(self) -> Path:
        """建立臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            (skills_dir / "vendors").mkdir(parents=True)
            yield skills_dir

    @pytest.fixture
    def sample_vendor_yaml(self) -> dict:
        """範例供應商配置."""
        return {
            "vendor": {
                "name": "Test Vendor",
                "identifier": "test",
                "version": "2.0.0",
            },
            "image_extraction": {
                "product_image": {
                    "source_page": "attachment_page",
                    "selection_strategy": "largest_color_image",
                    "min_area_ratio": 0.1,
                    "min_area_px": 10000,
                },
                "exclusions": [
                    {
                        "type": "logo",
                        "description": "Company Logo",
                        "rules": {"max_area_px": 5000},
                    },
                    {
                        "type": "material_swatch",
                        "description": "Material Swatch",
                        "rules": {"max_width_px": 300},
                    },
                ],
            },
            "prompts": {
                "parse_specification": {
                    "system": "You are a spec parser.",
                    "user_template": "Parse this: {content}",
                },
            },
        }

    @pytest.fixture
    def loader_with_sample(self, temp_skills_dir: Path, sample_vendor_yaml: dict) -> SkillLoaderService:
        """建立包含範例配置的 loader."""
        vendor_path = temp_skills_dir / "vendors" / "test.yaml"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)
        return SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

    # ============================================================
    # 基本載入測試
    # ============================================================

    def test_load_vendor_success(self, loader_with_sample: SkillLoaderService):
        """成功載入供應商配置."""
        skill = loader_with_sample.load_vendor("test")

        assert skill.vendor.name == "Test Vendor"
        assert skill.vendor.identifier == "test"

    def test_version_property(self, loader_with_sample: SkillLoaderService):
        """測試 version 便捷屬性."""
        skill = loader_with_sample.load_vendor("test")

        # version 可透過便捷屬性存取
        assert skill.version == "2.0.0"
        # 也可透過 vendor.version 存取
        assert skill.vendor.version == "2.0.0"

    def test_version_default_value(self, temp_skills_dir: Path):
        """測試 version 預設值."""
        # 建立沒有 version 的配置
        vendor_path = temp_skills_dir / "vendors" / "no_version.yaml"
        config = {
            "vendor": {
                "name": "No Version Vendor",
                "identifier": "no_version",
                # 沒有 version 欄位
            },
        }
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)
        skill = loader.load_vendor("no_version")

        # 預設值應該是 "1.0.0"
        assert skill.version == "1.0.0"

    def test_load_vendor_not_found(self, temp_skills_dir: Path):
        """找不到配置檔時拋出例外."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load_vendor("nonexistent")

        assert "找不到供應商配置檔" in str(exc_info.value)

    def test_load_vendor_invalid_yaml(self, temp_skills_dir: Path):
        """無效 YAML 時拋出例外."""
        vendor_path = temp_skills_dir / "vendors" / "invalid.yaml"
        vendor_path.write_text("invalid: yaml: content:", encoding="utf-8")

        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

        with pytest.raises(SkillParseError) as exc_info:
            loader.load_vendor("invalid")

        assert "YAML 解析失敗" in str(exc_info.value)

    def test_load_vendor_or_default_returns_none_on_error(self, temp_skills_dir: Path):
        """load_vendor_or_default 失敗時回傳 None."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

        result = loader.load_vendor_or_default("nonexistent")

        assert result is None

    # ============================================================
    # 圖片排除規則測試
    # ============================================================

    def test_image_extraction_config(self, loader_with_sample: SkillLoaderService):
        """圖片抓取配置正確解析."""
        skill = loader_with_sample.load_vendor("test")
        img_config = skill.image_extraction

        assert img_config.product_image.min_area_px == 10000
        assert img_config.product_image.min_area_ratio == 0.1
        assert len(img_config.exclusions) == 2

    def test_exclusion_rules(self, loader_with_sample: SkillLoaderService):
        """排除規則正確解析."""
        skill = loader_with_sample.load_vendor("test")
        exclusions = skill.image_extraction.exclusions

        logo_rule = next((e for e in exclusions if e.type == "logo"), None)
        assert logo_rule is not None
        assert logo_rule.description == "Company Logo"
        assert logo_rule.rules.get("max_area_px") == 5000

        swatch_rule = next((e for e in exclusions if e.type == "material_swatch"), None)
        assert swatch_rule is not None
        assert swatch_rule.rules.get("max_width_px") == 300

    def test_get_image_exclusion_rules_convenience(self, loader_with_sample: SkillLoaderService):
        """便捷方法 get_image_exclusion_rules 正確運作."""
        rules = loader_with_sample.get_image_exclusion_rules("test")

        assert len(rules) == 2
        assert all(isinstance(r, ImageExclusionRule) for r in rules)

    def test_get_image_exclusion_rules_returns_empty_on_error(self, temp_skills_dir: Path):
        """載入失敗時 get_image_exclusion_rules 回傳空列表."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

        rules = loader.get_image_exclusion_rules("nonexistent")

        assert rules == []

    # ============================================================
    # Prompt 模板測試
    # ============================================================

    def test_prompts_config(self, loader_with_sample: SkillLoaderService):
        """Prompt 配置正確解析."""
        skill = loader_with_sample.load_vendor("test")
        prompts = skill.prompts

        assert prompts.parse_specification.system == "You are a spec parser."
        assert prompts.parse_specification.user_template == "Parse this: {content}"

    def test_get_prompt_convenience(self, loader_with_sample: SkillLoaderService):
        """便捷方法 get_prompt 正確運作."""
        prompt = loader_with_sample.get_prompt("test", "parse_specification")

        assert prompt is not None
        assert isinstance(prompt, PromptTemplate)
        assert prompt.system == "You are a spec parser."

    def test_get_prompt_returns_none_on_error(self, temp_skills_dir: Path):
        """載入失敗時 get_prompt 回傳 None."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

        prompt = loader.get_prompt("nonexistent", "parse_specification")

        assert prompt is None

    # ============================================================
    # 快取測試
    # ============================================================

    def test_cache_enabled(self, temp_skills_dir: Path, sample_vendor_yaml: dict):
        """啟用快取時，重複載入使用快取."""
        vendor_path = temp_skills_dir / "vendors" / "test.yaml"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=True)

        # 第一次載入
        skill1 = loader.load_vendor("test")
        # 修改檔案
        sample_vendor_yaml["vendor"]["name"] = "Modified Name"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)
        # 第二次載入（應該使用快取）
        skill2 = loader.load_vendor("test")

        assert skill1.vendor.name == skill2.vendor.name == "Test Vendor"

    def test_cache_disabled(self, temp_skills_dir: Path, sample_vendor_yaml: dict):
        """停用快取時，每次重新載入."""
        vendor_path = temp_skills_dir / "vendors" / "test.yaml"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=False)

        # 第一次載入
        skill1 = loader.load_vendor("test")
        # 修改檔案
        sample_vendor_yaml["vendor"]["name"] = "Modified Name"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)
        # 第二次載入（應該讀取新檔案）
        skill2 = loader.load_vendor("test")

        assert skill1.vendor.name == "Test Vendor"
        assert skill2.vendor.name == "Modified Name"

    def test_clear_cache(self, temp_skills_dir: Path, sample_vendor_yaml: dict):
        """清除快取後重新載入."""
        vendor_path = temp_skills_dir / "vendors" / "test.yaml"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir, cache_enabled=True)

        skill1 = loader.load_vendor("test")
        sample_vendor_yaml["vendor"]["name"] = "Modified Name"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_vendor_yaml, f, allow_unicode=True)

        # 清除快取
        loader.clear_cache()
        skill2 = loader.load_vendor("test")

        assert skill1.vendor.name == "Test Vendor"
        assert skill2.vendor.name == "Modified Name"

    # ============================================================
    # 列表功能測試
    # ============================================================

    def test_list_vendors(self, temp_skills_dir: Path, sample_vendor_yaml: dict):
        """列出所有供應商."""
        # 建立多個供應商配置
        for vendor_id in ["vendor1", "vendor2", "vendor3"]:
            vendor_path = temp_skills_dir / "vendors" / f"{vendor_id}.yaml"
            with open(vendor_path, "w", encoding="utf-8") as f:
                yaml.dump(sample_vendor_yaml, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir)
        vendors = loader.list_vendors()

        assert len(vendors) == 3
        assert "vendor1" in vendors
        assert "vendor2" in vendors
        assert "vendor3" in vendors

    def test_list_vendors_excludes_templates(self, temp_skills_dir: Path, sample_vendor_yaml: dict):
        """列出供應商時排除以 _ 開頭的模板檔案."""
        vendor_path = temp_skills_dir / "vendors" / "real_vendor.yaml"
        template_path = temp_skills_dir / "vendors" / "_template.yaml"

        for path in [vendor_path, template_path]:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(sample_vendor_yaml, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir)
        vendors = loader.list_vendors()

        assert "real_vendor" in vendors
        assert "_template" not in vendors

    def test_list_vendors_empty_dir(self, temp_skills_dir: Path):
        """空目錄回傳空列表."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir)
        vendors = loader.list_vendors()

        assert vendors == []


class TestSkillLoaderSingleton:
    """單例工廠測試."""

    def test_get_skill_loader_returns_same_instance(self):
        """get_skill_loader 回傳相同實例."""
        loader1 = get_skill_loader()
        loader2 = get_skill_loader()

        assert loader1 is loader2


class TestDirectoryBasedVendorLoading:
    """目錄式供應商配置載入測試."""

    @pytest.fixture
    def temp_skills_dir_with_vendor_directory(self) -> Path:
        """建立包含目錄式供應商配置的臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            vendor_dir = skills_dir / "vendors" / "test_vendor"
            vendor_dir.mkdir(parents=True)

            # _vendor.yaml - 基本識別
            vendor_config = {
                "vendor": {
                    "name": "Test Vendor Directory",
                    "identifier": "test_vendor",
                    "version": "2.0.0",
                }
            }
            with open(vendor_dir / "_vendor.yaml", "w", encoding="utf-8") as f:
                yaml.dump(vendor_config, f, allow_unicode=True)

            # document-types.yaml
            doc_types = {
                "document_types": {
                    "furniture_specification": {
                        "description": "Furniture spec",
                        "provides": ["item_no", "description"],
                    }
                }
            }
            with open(vendor_dir / "document-types.yaml", "w", encoding="utf-8") as f:
                yaml.dump(doc_types, f, allow_unicode=True)

            # image-extraction.yaml
            image_config = {
                "image_extraction": {
                    "page_offset": {"default": 1},
                    "product_image": {"min_area_px": 10000},
                    "exclusions": [
                        {"type": "logo", "description": "Logo", "rules": {"max_area_px": 5000}}
                    ],
                }
            }
            with open(vendor_dir / "image-extraction.yaml", "w", encoding="utf-8") as f:
                yaml.dump(image_config, f, allow_unicode=True)

            # prompts/parse-specification.yaml
            prompts_dir = vendor_dir / "prompts"
            prompts_dir.mkdir()
            prompt_config = {
                "system": "You are a parser.",
                "user_template": "Parse: {content}",
            }
            with open(prompts_dir / "parse-specification.yaml", "w", encoding="utf-8") as f:
                yaml.dump(prompt_config, f, allow_unicode=True)

            yield skills_dir

    def test_load_vendor_from_directory(self, temp_skills_dir_with_vendor_directory: Path):
        """從目錄載入供應商配置."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_vendor_directory, cache_enabled=False)
        skill = loader.load_vendor("test_vendor")

        assert skill.vendor.name == "Test Vendor Directory"
        assert skill.vendor.identifier == "test_vendor"
        assert skill.version == "2.0.0"

    def test_directory_loads_image_extraction(self, temp_skills_dir_with_vendor_directory: Path):
        """目錄載入正確解析圖片抓取配置."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_vendor_directory, cache_enabled=False)
        skill = loader.load_vendor("test_vendor")

        assert skill.image_extraction.page_offset.default == 1
        assert len(skill.image_extraction.exclusions) == 1
        assert skill.image_extraction.exclusions[0].type == "logo"

    def test_directory_loads_prompts(self, temp_skills_dir_with_vendor_directory: Path):
        """目錄載入正確解析 Prompt 配置."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_vendor_directory, cache_enabled=False)
        skill = loader.load_vendor("test_vendor")

        assert skill.prompts.parse_specification.system == "You are a parser."
        assert skill.prompts.parse_specification.user_template == "Parse: {content}"

    def test_single_file_fallback(self, temp_skills_dir_with_vendor_directory: Path):
        """當目錄不存在時，仍可載入單檔配置（向後相容）."""
        # 建立單檔配置
        single_file_config = {
            "vendor": {
                "name": "Single File Vendor",
                "identifier": "single_file",
                "version": "1.0.0",
            }
        }
        vendor_path = temp_skills_dir_with_vendor_directory / "vendors" / "single_file.yaml"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(single_file_config, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_vendor_directory, cache_enabled=False)
        skill = loader.load_vendor("single_file")

        assert skill.vendor.name == "Single File Vendor"

    def test_list_vendors_includes_directories(self, temp_skills_dir_with_vendor_directory: Path):
        """list_vendors 包含目錄式供應商."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_vendor_directory, cache_enabled=False)
        vendors = loader.list_vendors()

        assert "test_vendor" in vendors


class TestExternalPromptTemplateLoading:
    """Prompt 模板外部化測試."""

    @pytest.fixture
    def temp_skills_dir_with_external_prompts(self) -> Path:
        """建立包含外部 Prompt 模板的臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            vendor_dir = skills_dir / "vendors" / "external_prompts"
            vendor_dir.mkdir(parents=True)
            prompts_dir = vendor_dir / "prompts"
            prompts_dir.mkdir()
            templates_dir = prompts_dir / "templates"
            templates_dir.mkdir()

            # _vendor.yaml
            vendor_config = {
                "vendor": {
                    "name": "External Prompts Vendor",
                    "identifier": "external_prompts",
                    "version": "1.0.0",
                }
            }
            with open(vendor_dir / "_vendor.yaml", "w", encoding="utf-8") as f:
                yaml.dump(vendor_config, f, allow_unicode=True)

            # prompts/parse-specification.yaml - 使用外部模板
            prompt_config = {
                "system": "You are a professional parser.",
                "user_template_file": "templates/parse-specification-template.md",
            }
            with open(prompts_dir / "parse-specification.yaml", "w", encoding="utf-8") as f:
                yaml.dump(prompt_config, f, allow_unicode=True)

            # prompts/templates/parse-specification-template.md
            template_content = """# Parse Specification Template

Please analyze the PDF content and extract BOQ items.

## Output Format
JSON array with: source_page, category, item_no, description

## Content
{pdf_content}

## Important Notes
- Only output items with detailed spec pages
- Fill null for unknown values
"""
            with open(templates_dir / "parse-specification-template.md", "w", encoding="utf-8") as f:
                f.write(template_content)

            yield skills_dir

    def test_load_prompt_from_external_file(self, temp_skills_dir_with_external_prompts: Path):
        """從外部 .md 檔案載入 Prompt 模板."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_external_prompts, cache_enabled=False)
        skill = loader.load_vendor("external_prompts")

        # 驗證 system 仍從 YAML 載入
        assert skill.prompts.parse_specification.system == "You are a professional parser."
        # 驗證 user_template 從外部 .md 檔案載入
        assert "Parse Specification Template" in skill.prompts.parse_specification.user_template
        assert "{pdf_content}" in skill.prompts.parse_specification.user_template
        assert "Important Notes" in skill.prompts.parse_specification.user_template

    def test_inline_template_still_works(self, temp_skills_dir_with_external_prompts: Path):
        """內嵌模板仍可正常運作（向後相容）."""
        # 新增一個使用內嵌模板的 prompt
        prompts_dir = temp_skills_dir_with_external_prompts / "vendors" / "external_prompts" / "prompts"
        inline_config = {
            "system": "Inline system prompt",
            "user_template": "This is an inline template: {content}",
        }
        with open(prompts_dir / "parse-quantity-summary.yaml", "w", encoding="utf-8") as f:
            yaml.dump(inline_config, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_external_prompts, cache_enabled=False)
        skill = loader.load_vendor("external_prompts")

        assert skill.prompts.parse_quantity_summary.user_template == "This is an inline template: {content}"


class TestVersionDependencies:
    """版本依賴驗證測試."""

    @pytest.fixture
    def temp_skills_dir_with_dependencies(self) -> Path:
        """建立包含版本依賴的臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            (skills_dir / "vendors").mkdir(parents=True)
            (skills_dir / "core").mkdir(parents=True)
            (skills_dir / "output-formats").mkdir(parents=True)

            # vendor 配置（含 requires）
            vendor_config = {
                "vendor": {
                    "name": "Vendor With Deps",
                    "identifier": "vendor_deps",
                    "version": "1.2.0",
                    "requires": {
                        "merge_rules": ">=1.1.0",
                        "output_format": ">=1.0.0",
                    }
                }
            }
            with open(skills_dir / "vendors" / "vendor_deps.yaml", "w", encoding="utf-8") as f:
                yaml.dump(vendor_config, f, allow_unicode=True)

            # merge-rules 配置
            merge_config = {
                "rules": {
                    "name": "Test Merge Rules",
                    "identifier": "merge-rules",
                    "version": "1.1.0",
                }
            }
            with open(skills_dir / "core" / "merge-rules.yaml", "w", encoding="utf-8") as f:
                yaml.dump(merge_config, f, allow_unicode=True)

            # output-format 配置
            output_config = {
                "format": {
                    "name": "Test Output Format",
                    "identifier": "fairmont",
                    "version": "1.0.0",
                },
                "company": {
                    "name": "Test Company",
                }
            }
            with open(skills_dir / "output-formats" / "fairmont.yaml", "w", encoding="utf-8") as f:
                yaml.dump(output_config, f, allow_unicode=True)

            yield skills_dir

    def test_vendor_requires_field_parsed(self, temp_skills_dir_with_dependencies: Path):
        """vendor.requires 欄位正確解析."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_dependencies, cache_enabled=False)
        skill = loader.load_vendor("vendor_deps")

        assert skill.vendor.requires is not None
        assert skill.vendor.requires.get("merge_rules") == ">=1.1.0"
        assert skill.vendor.requires.get("output_format") == ">=1.0.0"

    def test_validate_dependencies_passes(self, temp_skills_dir_with_dependencies: Path):
        """依賴版本驗證通過."""
        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_dependencies, cache_enabled=False)
        skill = loader.load_vendor("vendor_deps")

        # 驗證應該通過
        is_valid, errors = loader.validate_dependencies(skill)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_dependencies_fails_for_incompatible_version(self, temp_skills_dir_with_dependencies: Path):
        """依賴版本不相容時驗證失敗."""
        # 修改 merge-rules 版本為不相容的 1.0.0
        merge_config = {
            "rules": {
                "name": "Old Merge Rules",
                "identifier": "merge-rules",
                "version": "1.0.0",  # 不滿足 >=1.1.0
            }
        }
        with open(temp_skills_dir_with_dependencies / "core" / "merge-rules.yaml", "w", encoding="utf-8") as f:
            yaml.dump(merge_config, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_dir_with_dependencies, cache_enabled=False)
        skill = loader.load_vendor("vendor_deps")

        is_valid, errors = loader.validate_dependencies(skill)
        assert is_valid is False
        assert len(errors) > 0
        assert "merge_rules" in errors[0]


class TestJsonSchemaValidation:
    """JSON Schema 驗證測試."""

    @pytest.fixture
    def temp_skills_with_schemas(self) -> Path:
        """建立包含 Schema 的臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            (skills_dir / "vendors").mkdir(parents=True)
            (skills_dir / "schemas").mkdir(parents=True)

            # 建立 vendor schema
            vendor_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["vendor"],
                "properties": {
                    "vendor": {
                        "type": "object",
                        "required": ["name", "identifier"],
                        "properties": {
                            "name": {"type": "string"},
                            "identifier": {"type": "string"},
                            "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                        }
                    }
                }
            }
            import json
            with open(skills_dir / "schemas" / "vendor.schema.json", "w", encoding="utf-8") as f:
                json.dump(vendor_schema, f, indent=2)

            # 有效的 vendor 配置
            valid_config = {
                "vendor": {
                    "name": "Valid Vendor",
                    "identifier": "valid",
                    "version": "1.0.0",
                }
            }
            with open(skills_dir / "vendors" / "valid.yaml", "w", encoding="utf-8") as f:
                yaml.dump(valid_config, f, allow_unicode=True)

            # 無效的 vendor 配置（缺少 identifier）
            invalid_config = {
                "vendor": {
                    "name": "Invalid Vendor",
                    # 缺少 identifier
                    "version": "1.0.0",
                }
            }
            with open(skills_dir / "vendors" / "invalid.yaml", "w", encoding="utf-8") as f:
                yaml.dump(invalid_config, f, allow_unicode=True)

            yield skills_dir

    def test_schema_validation_passes_for_valid_config(self, temp_skills_with_schemas: Path):
        """有效配置通過 Schema 驗證."""
        loader = SkillLoaderService(skills_dir=temp_skills_with_schemas, cache_enabled=False)

        # 啟用 Schema 驗證
        is_valid, errors = loader.validate_against_schema("valid", "vendor")
        assert is_valid is True
        assert len(errors) == 0

    def test_schema_validation_fails_for_invalid_config(self, temp_skills_with_schemas: Path):
        """無效配置未通過 Schema 驗證."""
        loader = SkillLoaderService(skills_dir=temp_skills_with_schemas, cache_enabled=False)

        is_valid, errors = loader.validate_against_schema("invalid", "vendor")
        assert is_valid is False
        assert len(errors) > 0
        assert "identifier" in errors[0].lower() or "required" in errors[0].lower()

    def test_schema_validation_skipped_when_no_schema(self, temp_skills_with_schemas: Path):
        """無 Schema 檔案時跳過驗證."""
        # 刪除 schema 檔案
        import os
        os.remove(temp_skills_with_schemas / "schemas" / "vendor.schema.json")

        loader = SkillLoaderService(skills_dir=temp_skills_with_schemas, cache_enabled=False)

        # 無 schema 時應返回 True 並顯示警告
        is_valid, errors = loader.validate_against_schema("valid", "vendor")
        assert is_valid is True


class TestDisclosureLevelMarking:
    """漸進式揭露層級標記測試."""

    @pytest.fixture
    def temp_skills_with_disclosure(self) -> Path:
        """建立包含揭露層級標記的臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            vendor_dir = skills_dir / "vendors" / "disclosure_test"
            vendor_dir.mkdir(parents=True)

            # _vendor.yaml 含揭露層級標記
            vendor_config = {
                "vendor": {
                    "name": "Disclosure Test Vendor",
                    "identifier": "disclosure_test",
                    "version": "1.0.0",
                    "_disclosure_level": 1,  # L1: 識別層
                }
            }
            with open(vendor_dir / "_vendor.yaml", "w", encoding="utf-8") as f:
                yaml.dump(vendor_config, f, allow_unicode=True)

            # document-types.yaml
            doc_types = {
                "_disclosure_level": 2,  # L2: 初始化載入
                "document_types": {
                    "furniture_specification": {
                        "description": "Furniture spec",
                    }
                }
            }
            with open(vendor_dir / "document-types.yaml", "w", encoding="utf-8") as f:
                yaml.dump(doc_types, f, allow_unicode=True)

            # prompts
            prompts_dir = vendor_dir / "prompts"
            prompts_dir.mkdir()
            prompt_config = {
                "_disclosure_level": 4,  # L4: 執行時才載入
                "_lazy_load": True,
                "system": "Lazy loaded prompt",
                "user_template": "Template",
            }
            with open(prompts_dir / "parse-specification.yaml", "w", encoding="utf-8") as f:
                yaml.dump(prompt_config, f, allow_unicode=True)

            yield skills_dir

    def test_get_disclosure_level_for_vendor(self, temp_skills_with_disclosure: Path):
        """取得 vendor 的揭露層級."""
        loader = SkillLoaderService(skills_dir=temp_skills_with_disclosure, cache_enabled=False)

        levels = loader.get_disclosure_levels("disclosure_test")
        assert levels.get("vendor") == 1
        assert levels.get("document_types") == 2
        assert levels.get("prompts.parse_specification") == 4

    def test_disclosure_levels_default_to_none(self, temp_skills_with_disclosure: Path):
        """未標記的區塊揭露層級為 None."""
        loader = SkillLoaderService(skills_dir=temp_skills_with_disclosure, cache_enabled=False)

        levels = loader.get_disclosure_levels("disclosure_test")
        # 未標記的區塊應該不存在或為 None
        assert levels.get("image_extraction") is None


class TestFabricDetectionLocation:
    """fabric_detection 歸屬測試."""

    @pytest.fixture
    def temp_skills_with_fabric_in_merge_rules(self) -> Path:
        """建立 fabric_detection 在 merge-rules.yaml 中的臨時 skills 目錄."""
        with tempfile.TemporaryDirectory() as temp_dir:
            skills_dir = Path(temp_dir)
            (skills_dir / "vendors").mkdir(parents=True)
            (skills_dir / "core").mkdir(parents=True)

            # vendor 配置（不含 fabric_detection）
            vendor_config = {
                "vendor": {
                    "name": "Test Vendor",
                    "identifier": "test_vendor",
                    "version": "1.0.0",
                }
            }
            with open(skills_dir / "vendors" / "test_vendor.yaml", "w", encoding="utf-8") as f:
                yaml.dump(vendor_config, f, allow_unicode=True)

            # merge-rules 配置（含 fabric_detection）
            merge_config = {
                "rules": {
                    "name": "Test Merge Rules",
                    "identifier": "merge-rules",
                    "version": "1.2.0",
                },
                "fabric_detection": {
                    "pattern": r"\s+to\s+([A-Z0-9][A-Z0-9\-\.]+)",
                    "description": "匹配 'Fabric to DLX-100' 格式",
                    "belongs_to": "output_format",  # 明確標記歸屬
                }
            }
            with open(skills_dir / "core" / "merge-rules.yaml", "w", encoding="utf-8") as f:
                yaml.dump(merge_config, f, allow_unicode=True)

            yield skills_dir

    def test_fabric_detection_loaded_from_merge_rules(self, temp_skills_with_fabric_in_merge_rules: Path):
        """fabric_detection 從 merge-rules.yaml 載入."""
        loader = SkillLoaderService(skills_dir=temp_skills_with_fabric_in_merge_rules, cache_enabled=False)
        merge_rules = loader.load_merge_rules("merge-rules")

        assert merge_rules.fabric_detection is not None
        assert merge_rules.fabric_detection.pattern == r"\s+to\s+([A-Z0-9][A-Z0-9\-\.]+)"
        assert merge_rules.fabric_detection.belongs_to == "output_format"

    def test_get_fabric_detection_helper(self, temp_skills_with_fabric_in_merge_rules: Path):
        """便捷方法取得 fabric_detection 配置."""
        loader = SkillLoaderService(skills_dir=temp_skills_with_fabric_in_merge_rules, cache_enabled=False)
        fabric_detection = loader.get_fabric_detection()

        assert fabric_detection is not None
        assert fabric_detection.pattern == r"\s+to\s+([A-Z0-9][A-Z0-9\-\.]+)"

    def test_vendor_fabric_detection_fallback(self, temp_skills_with_fabric_in_merge_rules: Path):
        """當 merge-rules 無配置時，從 vendor 載入（向後相容）."""
        # 移除 merge-rules 中的 fabric_detection
        merge_config = {
            "rules": {
                "name": "Test Merge Rules",
                "identifier": "merge-rules",
                "version": "1.2.0",
            }
        }
        with open(temp_skills_with_fabric_in_merge_rules / "core" / "merge-rules.yaml", "w", encoding="utf-8") as f:
            yaml.dump(merge_config, f, allow_unicode=True)

        # 在 vendor 中新增 fabric_detection
        vendor_config = {
            "vendor": {
                "name": "Test Vendor",
                "identifier": "test_vendor",
                "version": "1.0.0",
            },
            "fabric_detection": {
                "pattern": r"\s+to\s+([A-Z]+)",
                "description": "Vendor-specific pattern",
            }
        }
        with open(temp_skills_with_fabric_in_merge_rules / "vendors" / "test_vendor.yaml", "w", encoding="utf-8") as f:
            yaml.dump(vendor_config, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=temp_skills_with_fabric_in_merge_rules, cache_enabled=False)
        fabric_detection = loader.get_fabric_detection(vendor_id="test_vendor")

        assert fabric_detection is not None
        assert fabric_detection.pattern == r"\s+to\s+([A-Z]+)"


class TestHabitusSkillIntegration:
    """HABITUS Skill 整合測試（使用真實配置檔）."""

    def test_load_habitus_skill(self):
        """載入真實的 habitus.yaml 配置."""
        loader = get_skill_loader()

        # 嘗試載入，若檔案不存在則跳過
        try:
            skill = loader.load_vendor("habitus")
        except SkillNotFoundError:
            pytest.skip("habitus.yaml 尚未建立")

        # 驗證基本結構
        assert skill.vendor.name == "HABITUS Design Group"
        assert skill.vendor.identifier == "habitus"

        # 驗證圖片排除規則
        exclusions = skill.image_extraction.exclusions
        exclusion_types = [e.type for e in exclusions]
        assert "logo" in exclusion_types
        assert "material_swatch" in exclusion_types
        assert "technical_drawing" in exclusion_types

        # 驗證 Prompt 模板
        parse_prompt = skill.prompts.parse_specification
        assert parse_prompt.system  # 非空
        assert parse_prompt.user_template  # 非空

        # 驗證頁面偏移配置
        page_offset = skill.image_extraction.page_offset
        assert page_offset.default == 1
        assert "furniture_specification" in page_offset.by_document_type


class TestPageOffsetConfig:
    """PageOffsetConfig 測試."""

    def test_default_offset(self):
        """預設偏移值."""
        config = PageOffsetConfig()
        assert config.default == 1
        assert config.by_document_type == {}

    def test_get_offset_default(self):
        """get_offset 回傳預設值."""
        config = PageOffsetConfig(default=1)
        assert config.get_offset() == 1
        assert config.get_offset(None) == 1

    def test_get_offset_by_document_type(self):
        """get_offset 依文件類型回傳正確偏移."""
        config = PageOffsetConfig(
            default=1,
            by_document_type={
                "furniture_specification": 1,
                "fabric_specification": 2,
                "quantity_summary": 0,
            }
        )
        assert config.get_offset("furniture_specification") == 1
        assert config.get_offset("fabric_specification") == 2
        assert config.get_offset("quantity_summary") == 0

    def test_get_offset_unknown_type_uses_default(self):
        """未知文件類型使用預設值."""
        config = PageOffsetConfig(
            default=1,
            by_document_type={"furniture_specification": 1}
        )
        assert config.get_offset("unknown_type") == 1

    def test_get_offset_custom_default(self):
        """自訂預設值."""
        config = PageOffsetConfig(default=2)
        assert config.get_offset() == 2
        assert config.get_offset("any_type") == 2

    def test_page_offset_in_vendor_skill(self, tmp_path: Path):
        """VendorSkill 正確解析 page_offset 配置."""
        skills_dir = tmp_path
        (skills_dir / "vendors").mkdir(parents=True)

        # 建立包含 page_offset 的配置
        config = {
            "vendor": {
                "name": "Test Vendor",
                "identifier": "test",
            },
            "image_extraction": {
                "page_offset": {
                    "default": 1,
                    "by_document_type": {
                        "furniture_specification": 1,
                        "fabric_specification": 2,
                    }
                },
                "product_image": {
                    "min_area_px": 10000,
                },
            },
        }
        vendor_path = skills_dir / "vendors" / "test.yaml"
        with open(vendor_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        loader = SkillLoaderService(skills_dir=skills_dir, cache_enabled=False)
        skill = loader.load_vendor("test")

        page_offset = skill.image_extraction.page_offset
        assert page_offset.default == 1
        assert page_offset.get_offset("furniture_specification") == 1
        assert page_offset.get_offset("fabric_specification") == 2
        assert page_offset.get_offset("unknown") == 1
