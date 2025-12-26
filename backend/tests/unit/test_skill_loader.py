"""Unit tests for SkillLoaderService."""

import tempfile
from pathlib import Path

import pytest
import yaml

from app.services.skill_loader import (
    ImageExclusionRule,
    PromptTemplate,
    SkillLoaderService,
    SkillNotFoundError,
    SkillParseError,
    VendorSkill,
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
