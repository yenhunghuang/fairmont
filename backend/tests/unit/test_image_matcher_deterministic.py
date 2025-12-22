"""Unit tests for DeterministicImageMatcher."""

import pytest
from app.services.image_matcher_deterministic import (
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
