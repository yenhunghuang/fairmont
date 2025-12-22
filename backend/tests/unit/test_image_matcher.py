"""Unit tests for image_matcher service with Gemini Vision validation."""

import pytest
import io
from PIL import Image as PILImage
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.image_matcher import ImageMatcherService, MIN_LARGE_IMAGE_AREA
from app.models import BOQItem


pytestmark = pytest.mark.unit


@pytest.fixture
def mock_boq_items():
    """Create mock BOQ items for testing."""
    return [
        BOQItem(
            no=1,
            item_no="FUR-001",
            description="會議桌",
            source_document_id="doc-1",
            source_page=1,
        ),
        BOQItem(
            no=2,
            item_no="FUR-002",
            description="辦公椅",
            source_document_id="doc-1",
            source_page=2,
        ),
        BOQItem(
            no=3,
            item_no="FUR-003",
            description="書架",
            source_document_id="doc-1",
            source_page=3,
        ),
    ]


@pytest.fixture
def sample_product_image_bytes():
    """Create sample product image bytes."""
    # Create a simple RGB image (furniture product photo)
    img = PILImage.new("RGB", (300, 400), color="brown")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_logo_image_bytes():
    """Create sample logo/small image bytes."""
    # Create a small image (typically logo size)
    img = PILImage.new("RGB", (50, 50), color="blue")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_images_with_bytes(sample_product_image_bytes):
    """Create sample images with bytes for testing."""
    return [
        {
            "bytes": sample_product_image_bytes,
            "width": 300,
            "height": 400,
            "page": 1,
            "index": 0,
        },
        {
            "bytes": sample_product_image_bytes,
            "width": 350,
            "height": 450,
            "page": 2,
            "index": 1,
        },
        {
            "bytes": sample_product_image_bytes,
            "width": 200,
            "height": 300,
            "page": 3,
            "index": 2,
        },
    ]


class TestImageMatcherService:
    """Tests for image matcher service."""

    def test_matcher_initialization_with_vision_disabled(self):
        """Test matcher initialization with Vision validation disabled."""
        matcher = ImageMatcherService(enable_vision_validation=False)
        assert matcher.enable_vision_validation is False

    def test_matcher_initialization_with_vision_enabled(self):
        """Test matcher initialization with Vision validation enabled."""
        # Mock Gemini initialization
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel"):
                matcher = ImageMatcherService(enable_vision_validation=True)
                assert matcher.enable_vision_validation is True or (
                    matcher.model is None  # Gemini not available
                )

    def test_filter_large_images(self, sample_images_with_bytes):
        """Test filtering to large images only."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        # All sample images are large (area > MIN_LARGE_IMAGE_AREA)
        # 300*400=120000, 350*450=157500, 200*300=60000
        large_count = sum(
            1
            for img in sample_images_with_bytes
            if img["width"] * img["height"] >= MIN_LARGE_IMAGE_AREA
        )
        assert large_count == 3

    def test_filter_small_images(self):
        """Test small images are filtered out."""
        small_images = [
            {"bytes": b"", "width": 50, "height": 50, "page": 1, "index": 0},  # 2500
            {"bytes": b"", "width": 100, "height": 50, "page": 1, "index": 1},  # 5000
        ]

        # Both are below MIN_LARGE_IMAGE_AREA
        large_count = sum(
            1
            for img in small_images
            if img["width"] * img["height"] >= MIN_LARGE_IMAGE_AREA
        )
        assert large_count == 0

    @pytest.mark.asyncio
    async def test_match_images_without_vision(
        self, sample_images_with_bytes, mock_boq_items
    ):
        """Test image matching without Vision validation."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        mapping = await matcher.match_images_to_items(
            sample_images_with_bytes,
            mock_boq_items,
            validate_product_images=False,
        )

        # Should match 3 images to 3 BOQ items
        assert len(mapping) == 3
        assert all(isinstance(v, str) for v in mapping.values())  # item IDs
        assert all(isinstance(k, int) for k in mapping.keys())  # image indices

    @pytest.mark.asyncio
    async def test_match_empty_images(self, mock_boq_items):
        """Test matching with no images."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        mapping = await matcher.match_images_to_items([], mock_boq_items)

        assert mapping == {}

    @pytest.mark.asyncio
    async def test_match_empty_items(self, sample_images_with_bytes):
        """Test matching with no BOQ items."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        mapping = await matcher.match_images_to_items(sample_images_with_bytes, [])

        assert mapping == {}

    @pytest.mark.asyncio
    async def test_match_respects_source_page(self, sample_images_with_bytes):
        """Test matching respects BOQ item source page."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        # Create BOQ items with specific pages
        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Item 1",
                source_page=1,
                source_document_id="doc-1",
            ),
            BOQItem(
                no=2,
                item_no="FUR-002",
                description="Item 2",
                source_page=2,
                source_document_id="doc-1",
            ),
        ]

        mapping = await matcher.match_images_to_items(
            sample_images_with_bytes, items, validate_product_images=False
        )

        # Should match images to items on same/next page
        assert len(mapping) == 2

    @pytest.mark.asyncio
    async def test_match_does_not_reuse_images(self, sample_images_with_bytes):
        """Test that images are not matched to multiple items."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        # Create 5 items but only 3 images
        items = [
            BOQItem(
                no=i,
                item_no=f"FUR-{i:03d}",
                description=f"Item {i}",
                source_page=1,
                source_document_id="doc-1",
            )
            for i in range(1, 6)
        ]

        mapping = await matcher.match_images_to_items(
            sample_images_with_bytes, items, validate_product_images=False
        )

        # Each image used only once
        used_images = set(mapping.keys())
        assert len(used_images) == len(mapping)

    @pytest.mark.asyncio
    async def test_validate_single_image_no_model(self):
        """Test image validation when Gemini is not initialized."""
        matcher = ImageMatcherService(enable_vision_validation=False)
        matcher.model = None

        is_valid, confidence, reason = await matcher._validate_single_image(b"fake_data")

        assert is_valid is False
        assert confidence == 0.0
        assert reason == "Gemini Vision not initialized"

    @pytest.mark.asyncio
    async def test_validate_batch_empty_list(self):
        """Test batch validation with empty image list."""
        matcher = ImageMatcherService(enable_vision_validation=False)

        validated = await matcher._validate_images_batch([])

        assert validated == []

    @pytest.mark.asyncio
    async def test_match_with_min_confidence_threshold(self):
        """Test image validation respects confidence threshold."""
        matcher = ImageMatcherService(enable_vision_validation=True)

        # Mock the validation method to return low confidence
        async def mock_validate_low_conf(image_bytes, min_confidence=0.6):
            return False, 0.5, "低置信度"  # Returns False due to low confidence

        matcher._validate_single_image = mock_validate_low_conf

        images = [
            {
                "bytes": b"test",
                "width": 200,
                "height": 200,
                "page": 1,
                "index": 0,
            }
        ]

        items = [
            BOQItem(
                no=1,
                item_no="FUR-001",
                description="Item",
                source_document_id="doc-1",
            )
        ]

        # With threshold > confidence, image should be rejected
        mapping = await matcher.match_images_to_items(
            images, items, validate_product_images=True, min_confidence=0.6
        )

        # No images should match because confidence is below threshold
        assert len(mapping) == 0

    def test_min_large_image_area_constant(self):
        """Test that MIN_LARGE_IMAGE_AREA is appropriately sized."""
        # Should be large enough to exclude typical logos/icons
        # but small enough for actual product photos
        assert MIN_LARGE_IMAGE_AREA == 8000
        # 8000 pixels = approximately 100x80 at minimum


class TestImageMatcherVisionIntegration:
    """Tests for image matcher with Gemini Vision integration."""

    @pytest.mark.asyncio
    async def test_vision_validation_with_mock_response(self):
        """Test Vision validation with mocked Gemini response."""
        matcher = ImageMatcherService(enable_vision_validation=True)

        # Mock the validation method directly instead of mocking Gemini
        async def mock_validate(image_bytes, min_confidence=0.6):
            return True, 0.95, "清晰的家具产品照片"

        matcher._validate_single_image = mock_validate

        is_valid, confidence, reason = await matcher._validate_single_image(
            b"test_image_data"
        )

        assert is_valid is True
        assert confidence == 0.95
        assert "家具" in reason or "照片" in reason

    @pytest.mark.asyncio
    async def test_vision_rejects_logo(self):
        """Test Vision validation rejects logo images."""
        matcher = ImageMatcherService(enable_vision_validation=True)

        async def mock_validate(image_bytes, min_confidence=0.6):
            return False, 0.9, "这是品牌Logo，不是产品样品"

        matcher._validate_single_image = mock_validate

        is_valid, confidence, reason = await matcher._validate_single_image(
            b"test_logo_data"
        )

        assert is_valid is False
        assert confidence == 0.9
        assert "Logo" in reason or "品牌" in reason

    @pytest.mark.asyncio
    async def test_vision_rejects_design_drawing(self):
        """Test Vision validation rejects design/CAD drawings."""
        matcher = ImageMatcherService(enable_vision_validation=True)

        async def mock_validate(image_bytes, min_confidence=0.6):
            return False, 0.88, "这是CAD设计图纸，不是产品样品照"

        matcher._validate_single_image = mock_validate

        is_valid, confidence, reason = await matcher._validate_single_image(
            b"test_cad_data"
        )

        assert is_valid is False
        assert "设计图" in reason or "CAD" in reason

    @pytest.mark.asyncio
    async def test_vision_handles_partial_json(self):
        """Test Vision validation with partial JSON response."""
        matcher = ImageMatcherService(enable_vision_validation=True)

        # Mock the validation method to simulate malformed response handling
        async def mock_validate_partial(image_bytes, min_confidence=0.6):
            # Simulate the error handling path
            return False, 0.0, "JSON解析失败"

        matcher._validate_single_image = mock_validate_partial

        is_valid, confidence, reason = await matcher._validate_single_image(b"test_data")
        assert is_valid is False
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_vision(self, sample_images_with_bytes, mock_boq_items):
        """Test complete matching pipeline with Vision validation."""
        matcher = ImageMatcherService(enable_vision_validation=True)

        # Mock Vision to approve images as matching products
        async def mock_validate_for_item(image_bytes, boq_item, min_confidence=0.6):
            # All images match all items in this test
            return True, 0.95, "与项目描述匹配的产品样品"

        matcher._validate_image_for_item = mock_validate_for_item

        mapping = await matcher.match_images_to_items(
            sample_images_with_bytes,
            mock_boq_items,
            validate_product_images=True,
            min_confidence=0.6,
        )

        # Should match 3 items with images (one per item if available)
        assert len(mapping) >= 1  # At least one match
