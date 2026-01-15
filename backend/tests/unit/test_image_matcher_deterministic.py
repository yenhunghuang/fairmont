"""Unit tests for DeterministicImageMatcher."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from app.services.image_matcher_deterministic import (
    DEFAULT_EXCLUSION_RULES,
    DeterministicImageMatcher,
    MIN_PRODUCT_IMAGE_AREA,
    get_deterministic_image_matcher,
)
from app.models import BOQItem


pytestmark = pytest.mark.unit


@pytest.fixture
def matcher():
    return DeterministicImageMatcher()


@pytest.fixture
def sample_images():
    """Images on pages 2 and 3."""
    return [
        {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 0},  # 120000 px
        {"bytes": b"", "width": 50, "height": 50, "page": 2, "index": 1},    # 2500 px (logo)
        {"bytes": b"", "width": 200, "height": 300, "page": 3, "index": 2},  # 60000 px
    ]


@pytest.fixture
def sample_items():
    """Items on pages 1 and 2."""
    return [
        BOQItem(no=1, item_no="FUR-001", description="Desk", source_document_id="doc-1", source_page=1),
        BOQItem(no=2, item_no="FUR-002", description="Chair", source_document_id="doc-1", source_page=2),
    ]


class TestDeterministicImageMatcher:
    """Test cases for DeterministicImageMatcher core functionality."""

    @pytest.mark.asyncio
    async def test_empty_inputs(self, matcher):
        """Both empty inputs return empty mapping."""
        assert await matcher.match_images_to_items([], []) == {}

    @pytest.mark.asyncio
    async def test_empty_images(self, matcher, sample_items):
        """No images returns empty mapping."""
        assert await matcher.match_images_to_items([], sample_items) == {}

    @pytest.mark.asyncio
    async def test_empty_items(self, matcher, sample_images):
        """No items returns empty mapping."""
        assert await matcher.match_images_to_items(sample_images, []) == {}

    @pytest.mark.asyncio
    async def test_page_offset_matching(self, matcher, sample_images, sample_items):
        """Items on page N match images on page N+1."""
        mapping = await matcher.match_images_to_items(
            sample_images,
            sample_items,
            target_page_offset=1
        )

        # FUR-001 (page 1) -> image on page 2 (index 0, largest)
        # FUR-002 (page 2) -> image on page 3 (index 2)
        assert len(mapping) == 2
        assert 0 in mapping  # Image 0 matched
        assert 2 in mapping  # Image 2 matched
        assert 1 not in mapping  # Logo (too small) not matched

    @pytest.mark.asyncio
    async def test_logo_filtering(self, matcher):
        """Small images (logos) are filtered out."""
        images = [
            {"bytes": b"", "width": 50, "height": 50, "page": 2, "index": 0},  # 2500 px
            {"bytes": b"", "width": 80, "height": 80, "page": 2, "index": 1},  # 6400 px
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)
        assert mapping == {}  # Both images below threshold

    @pytest.mark.asyncio
    async def test_no_image_reuse(self, matcher):
        """Each image is used only once."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
            BOQItem(
                no=2,
                item_no="FUR-002",
                description="Chair",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)
        assert len(mapping) == 1  # Only one image, one match

    @pytest.mark.asyncio
    async def test_custom_page_offset(self, matcher):
        """Custom page offset works correctly."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 3, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        # Default offset=1 would look at page 2, find nothing
        mapping_default = await matcher.match_images_to_items(images, items, target_page_offset=1)
        assert mapping_default == {}

        # Offset=2 looks at page 3, finds image
        mapping_custom = await matcher.match_images_to_items(images, items, target_page_offset=2)
        assert 0 in mapping_custom

    @pytest.mark.asyncio
    async def test_source_page_none_defaults_to_1(self, matcher):
        """Items without source_page default to page 1."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=None,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)
        assert 0 in mapping  # Page 1 + offset 1 = page 2

    def test_singleton_pattern(self):
        """get_deterministic_image_matcher returns same instance."""
        m1 = get_deterministic_image_matcher()
        m2 = get_deterministic_image_matcher()
        assert m1 is m2


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_single_page_pdf(self, matcher):
        """Single page PDF with image on same page."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 1, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        # With offset=1, looks at page 2 (no images)
        mapping = await matcher.match_images_to_items(images, items, target_page_offset=1)
        assert mapping == {}

        # With offset=0, looks at page 1 (has image)
        mapping = await matcher.match_images_to_items(images, items, target_page_offset=0)
        assert 0 in mapping

    @pytest.mark.asyncio
    async def test_multiple_items_same_page(self, matcher):
        """Multiple items on same page get different images."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 0},  # Largest
            {"bytes": b"", "width": 200, "height": 300, "page": 2, "index": 1},  # Second
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
            BOQItem(
                no=2,
                item_no="FUR-002",
                description="Chair",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)

        # First item gets largest, second gets next largest
        assert len(mapping) == 2
        assert 0 in mapping
        assert 1 in mapping

    @pytest.mark.asyncio
    async def test_multiple_pages_multiple_items(self, matcher):
        """Multiple pages with items on different pages."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 0},  # 120000 px
            {"bytes": b"", "width": 250, "height": 350, "page": 3, "index": 1},  # 87500 px
            {"bytes": b"", "width": 200, "height": 300, "page": 4, "index": 2},  # 60000 px
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
            BOQItem(
                no=2,
                item_no="FUR-002",
                description="Chair",
                source_document_id="doc-1",
                source_page=2,
            ),
            BOQItem(
                no=3,
                item_no="FUR-003",
                description="Table",
                source_document_id="doc-1",
                source_page=3,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)

        # Each item should match with image on next page
        assert len(mapping) == 3
        assert 0 in mapping  # Page 1 -> page 2
        assert 1 in mapping  # Page 2 -> page 3
        assert 2 in mapping  # Page 3 -> page 4

    @pytest.mark.asyncio
    async def test_no_images_on_target_page(self, matcher):
        """Items with no images on target page are skipped."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 3, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
            BOQItem(
                no=2,
                item_no="FUR-002",
                description="Chair",
                source_document_id="doc-1",
                source_page=2,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)

        # FUR-001 (page 1) looks at page 2, finds nothing
        # FUR-002 (page 2) looks at page 3, finds image 0
        assert len(mapping) == 1
        assert 0 in mapping

    @pytest.mark.asyncio
    async def test_largest_image_selection(self, matcher):
        """Largest available image is always selected."""
        images = [
            {"bytes": b"", "width": 100, "height": 150, "page": 2, "index": 0},  # 15000 px
            {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 1},  # 120000 px
            {"bytes": b"", "width": 150, "height": 200, "page": 2, "index": 2},  # 30000 px
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)

        # Should select index 1 (largest)
        assert len(mapping) == 1
        assert 1 in mapping

    @pytest.mark.asyncio
    async def test_negative_page_offset(self, matcher):
        """Negative offset searches pages before item."""
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 1, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=2,
            ),
        ]

        # Offset=1 looks at page 3, finds nothing
        mapping_forward = await matcher.match_images_to_items(images, items, target_page_offset=1)
        assert mapping_forward == {}

        # Offset=-1 looks at page 1, finds image
        mapping_backward = await matcher.match_images_to_items(images, items, target_page_offset=-1)
        assert 0 in mapping_backward


class TestAreaThreshold:
    """Test image area threshold behavior."""

    @pytest.mark.asyncio
    async def test_exactly_at_threshold(self, matcher):
        """Image at exact threshold is accepted."""
        images = [
            {"bytes": b"", "width": 100, "height": 100, "page": 2, "index": 0},  # 10000 px
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)
        assert 0 in mapping

    @pytest.mark.asyncio
    async def test_just_below_threshold(self, matcher):
        """Image just below threshold is rejected."""
        images = [
            {"bytes": b"", "width": 99, "height": 100, "page": 2, "index": 0},  # 9900 px
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)
        assert mapping == {}

    @pytest.mark.asyncio
    async def test_mixed_size_images(self, matcher):
        """Mix of images above and below threshold."""
        images = [
            {"bytes": b"", "width": 50, "height": 50, "page": 2, "index": 0},    # 2500 px (logo)
            {"bytes": b"", "width": 200, "height": 200, "page": 2, "index": 1},  # 40000 px (product)
            {"bytes": b"", "width": 80, "height": 80, "page": 2, "index": 2},    # 6400 px (logo)
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Desk",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        mapping = await matcher.match_images_to_items(images, items)
        # Should select index 1 (only product-sized image)
        assert len(mapping) == 1
        assert 1 in mapping


class TestExclusionRules:
    """Test exclusion rules functionality."""

    def test_default_exclusion_rules_exist(self):
        """Default exclusion rules are defined."""
        assert len(DEFAULT_EXCLUSION_RULES) > 0
        assert DEFAULT_EXCLUSION_RULES[0]["type"] == "logo"

    def test_should_exclude_small_logo(self):
        """Small images are excluded by logo rule."""
        matcher = DeterministicImageMatcher()

        # Small image (logo)
        img = {"width": 50, "height": 50, "page": 1, "index": 0}  # 2500 px
        excluded, reason = matcher._should_exclude_image(img)
        assert excluded is True
        assert "logo" in reason.lower()

    def test_should_not_exclude_large_image(self):
        """Large images are not excluded."""
        matcher = DeterministicImageMatcher()

        # Large image (product)
        img = {"width": 300, "height": 400, "page": 1, "index": 0}  # 120000 px
        excluded, reason = matcher._should_exclude_image(img)
        assert excluded is False
        assert reason == ""

    def test_custom_exclusion_rules_from_skill(self):
        """Custom exclusion rules from Skill config are applied."""
        # Mock Skill loader
        mock_skill = MagicMock()
        mock_skill.image_extraction.product_image.min_area_px = 20000
        mock_skill.image_extraction.exclusions = [
            MagicMock(type="material_swatch", description="Swatch", rules={"max_width_px": 200, "max_height_px": 200}),
        ]

        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = mock_skill
            matcher = DeterministicImageMatcher(vendor_id="test_vendor")

            # Check min_area_px was loaded
            assert matcher._min_area_px == 20000

            # Check exclusion rules were loaded
            rules = matcher._get_exclusion_rules()
            assert len(rules) == 1
            assert rules[0]["type"] == "material_swatch"

    def test_fallback_when_skill_not_found(self):
        """Fallback to defaults when Skill config not found."""
        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = None
            matcher = DeterministicImageMatcher(vendor_id="nonexistent")

            # Should use default values
            assert matcher._min_area_px == MIN_PRODUCT_IMAGE_AREA
            assert matcher._get_exclusion_rules() == DEFAULT_EXCLUSION_RULES

    def test_max_width_height_exclusion(self):
        """Exclusion by max_width_px and max_height_px works."""
        matcher = DeterministicImageMatcher()
        matcher._exclusion_rules = [
            {"type": "swatch", "description": "Material swatch", "rules": {"max_width_px": 100, "max_height_px": 100}},
        ]

        # Image within max dimensions (should be excluded)
        small_img = {"width": 80, "height": 90, "page": 1, "index": 0}
        excluded, reason = matcher._should_exclude_image(small_img)
        assert excluded is True
        assert "swatch" in reason.lower()

        # Image exceeds max dimensions (should not be excluded)
        large_img = {"width": 150, "height": 100, "page": 1, "index": 1}
        excluded, reason = matcher._should_exclude_image(large_img)
        assert excluded is False

    def test_max_area_ratio_exclusion(self):
        """Exclusion by max_area_ratio works."""
        matcher = DeterministicImageMatcher()
        matcher._exclusion_rules = [
            {"type": "icon", "description": "Small icon", "rules": {"max_area_ratio": 0.05}},
        ]

        page_area = 1000000  # Total page area

        # Small ratio (should be excluded: 10000/1000000 = 0.01 < 0.05)
        small_img = {"width": 100, "height": 100, "page": 1, "index": 0}  # 10000 px
        excluded, reason = matcher._should_exclude_image(small_img, page_area=page_area)
        assert excluded is True
        assert "icon" in reason.lower()

        # Large ratio (should not be excluded: 100000/1000000 = 0.1 > 0.05)
        large_img = {"width": 500, "height": 200, "page": 1, "index": 1}  # 100000 px
        excluded, reason = matcher._should_exclude_image(large_img, page_area=page_area)
        assert excluded is False


class TestVendorSpecificMatcher:
    """Test vendor-specific matcher configuration."""

    def test_vendor_matcher_logs_info(self, caplog):
        """Vendor matcher logs initialization info."""
        import logging

        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = None
            with caplog.at_level(logging.INFO):
                matcher = DeterministicImageMatcher(vendor_id="habitus")

            assert "habitus" in caplog.text or "default" in caplog.text

    def test_get_matcher_with_vendor_creates_new_instance(self):
        """get_deterministic_image_matcher with vendor_id creates new instance."""
        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = None

            m1 = get_deterministic_image_matcher(vendor_id="vendor1")
            m2 = get_deterministic_image_matcher(vendor_id="vendor2")

            # Different vendors should create different instances
            assert m1 is not m2
            assert m1.vendor_id == "vendor1"
            assert m2.vendor_id == "vendor2"

    def test_is_product_image_respects_min_area(self):
        """_is_product_image respects configured min_area_px."""
        matcher = DeterministicImageMatcher()
        matcher._min_area_px = 50000  # Custom threshold

        # Below threshold
        small_img = {"width": 200, "height": 200, "page": 1, "index": 0}  # 40000 px
        assert matcher._is_product_image(small_img) is False

        # At threshold
        exact_img = {"width": 250, "height": 200, "page": 1, "index": 1}  # 50000 px
        assert matcher._is_product_image(exact_img) is True

        # Above threshold
        large_img = {"width": 300, "height": 200, "page": 1, "index": 2}  # 60000 px
        assert matcher._is_product_image(large_img) is True

    @pytest.mark.asyncio
    async def test_exclusion_count_logged(self, caplog):
        """Excluded images count is logged."""
        import logging

        matcher = DeterministicImageMatcher()
        images = [
            {"bytes": b"", "width": 50, "height": 50, "page": 2, "index": 0},   # Logo (excluded)
            {"bytes": b"", "width": 60, "height": 60, "page": 2, "index": 1},   # Logo (excluded)
            {"bytes": b"", "width": 300, "height": 400, "page": 2, "index": 2}, # Product
        ]
        items = [
            BOQItem(no=1, item_no="FUR-001", description="Desk", source_document_id="doc-1", source_page=1),
        ]

        with caplog.at_level(logging.INFO):
            await matcher.match_images_to_items(images, items)

        # Should log exclusion count
        assert "Excluded" in caplog.text or "excluded" in caplog.text


class TestPageOffsetConfiguration:
    """Test page offset configuration from Skill."""

    def test_get_page_offset_default_without_skill(self):
        """get_page_offset returns default 1 without Skill config."""
        matcher = DeterministicImageMatcher()
        assert matcher.get_page_offset() == 1
        assert matcher.get_page_offset(None) == 1
        assert matcher.get_page_offset("furniture_specification") == 1

    def test_get_page_offset_with_skill_config(self):
        """get_page_offset uses Skill config when available."""
        from app.services.skill_loader import PageOffsetConfig

        mock_skill = MagicMock()
        mock_skill.image_extraction.product_image.min_area_px = 10000
        mock_skill.image_extraction.exclusions = []
        mock_skill.image_extraction.page_offset = PageOffsetConfig(
            default=1,
            by_document_type={
                "furniture_specification": 1,
                "fabric_specification": 2,
                "quantity_summary": 0,
            }
        )

        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = mock_skill
            matcher = DeterministicImageMatcher(vendor_id="habitus")

            assert matcher.get_page_offset() == 1  # Default
            assert matcher.get_page_offset("furniture_specification") == 1
            assert matcher.get_page_offset("fabric_specification") == 2
            assert matcher.get_page_offset("quantity_summary") == 0
            assert matcher.get_page_offset("unknown") == 1  # Falls back to default

    def test_get_page_offset_fallback_when_skill_not_found(self):
        """get_page_offset falls back to 1 when Skill not found."""
        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = None
            matcher = DeterministicImageMatcher(vendor_id="nonexistent")

            assert matcher.get_page_offset() == 1
            assert matcher.get_page_offset("any_type") == 1

    @pytest.mark.asyncio
    async def test_matching_with_configured_offset(self):
        """Integration test: matching uses configured page offset."""
        from app.services.skill_loader import PageOffsetConfig

        mock_skill = MagicMock()
        mock_skill.image_extraction.product_image.min_area_px = 10000
        mock_skill.image_extraction.exclusions = []
        mock_skill.image_extraction.page_offset = PageOffsetConfig(
            default=1,
            by_document_type={"fabric_specification": 2}
        )

        # Image on page 3 (offset 2 from spec on page 1)
        images = [
            {"bytes": b"", "width": 300, "height": 400, "page": 3, "index": 0},
        ]
        items = [
            BOQItem(
                no=1,
                item_no="FAB-001",
                description="Fabric",
                source_document_id="doc-1",
                source_page=1,
            ),
        ]

        with patch("app.services.skill_loader.get_skill_loader") as mock_loader:
            mock_loader.return_value.load_vendor_or_default.return_value = mock_skill
            matcher = DeterministicImageMatcher(vendor_id="habitus")

            # With default offset=1, no match (looks at page 2)
            mapping_default = await matcher.match_images_to_items(
                images, items, target_page_offset=matcher.get_page_offset()
            )
            assert len(mapping_default) == 0

            # With fabric offset=2, match found (looks at page 3)
            mapping_fabric = await matcher.match_images_to_items(
                images, items, target_page_offset=matcher.get_page_offset("fabric_specification")
            )
            assert len(mapping_fabric) == 1
            assert 0 in mapping_fabric
