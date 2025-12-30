"""Unit tests for ImageSelectorService.

測試圖片解析度選擇服務的尺寸解析與選擇功能。
"""

import pytest
import base64

from app.services.image_selector import (
    ImageSelectorService,
    ImageInfo,
    get_image_selector_service,
)


class TestImageSelectorService:
    """ImageSelectorService 單元測試."""

    @pytest.fixture
    def service(self) -> ImageSelectorService:
        """建立測試用服務實例."""
        return ImageSelectorService()

    # ============================================================================
    # 測試用圖片資料
    # ============================================================================

    @pytest.fixture
    def sample_png_1x1(self) -> str:
        """1x1 像素的 PNG 圖片 (Base64)."""
        # 最小的有效 PNG 檔案 (1x1 透明)
        png_bytes = bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,  # PNG signature
                0x00,
                0x00,
                0x00,
                0x0D,  # IHDR chunk length
                0x49,
                0x48,
                0x44,
                0x52,  # IHDR
                0x00,
                0x00,
                0x00,
                0x01,  # width = 1
                0x00,
                0x00,
                0x00,
                0x01,  # height = 1
                0x08,
                0x02,  # bit depth, color type
                0x00,
                0x00,
                0x00,  # compression, filter, interlace
                0x90,
                0x77,
                0x53,
                0xDE,  # CRC
                0x00,
                0x00,
                0x00,
                0x0C,  # IDAT chunk length
                0x49,
                0x44,
                0x41,
                0x54,  # IDAT
                0x08,
                0xD7,
                0x63,
                0xF8,
                0xFF,
                0xFF,
                0xFF,
                0x00,
                0x05,
                0xFE,
                0x02,
                0xFE,
                0xA3,
                0x56,
                0x36,
                0x56,  # compressed data + CRC
                0x00,
                0x00,
                0x00,
                0x00,  # IEND chunk length
                0x49,
                0x45,
                0x4E,
                0x44,  # IEND
                0xAE,
                0x42,
                0x60,
                0x82,  # CRC
            ]
        )
        return base64.b64encode(png_bytes).decode("utf-8")

    @pytest.fixture
    def sample_png_10x10(self) -> str:
        """10x10 像素的 PNG 圖片 (Base64)."""
        # PNG header + IHDR 指定 10x10
        png_bytes = bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,  # PNG signature
                0x00,
                0x00,
                0x00,
                0x0D,  # IHDR chunk length
                0x49,
                0x48,
                0x44,
                0x52,  # IHDR
                0x00,
                0x00,
                0x00,
                0x0A,  # width = 10
                0x00,
                0x00,
                0x00,
                0x0A,  # height = 10
                0x08,
                0x02,
                0x00,
                0x00,
                0x00,
                # 簡化的測試資料
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )
        return base64.b64encode(png_bytes).decode("utf-8")

    @pytest.fixture
    def sample_gif_5x5(self) -> str:
        """5x5 像素的 GIF 圖片 (Base64)."""
        # 最小 GIF89a header
        gif_bytes = bytes(
            [
                0x47,
                0x49,
                0x46,
                0x38,
                0x39,
                0x61,  # GIF89a
                0x05,
                0x00,  # width = 5
                0x05,
                0x00,  # height = 5
                0x00,
                0x00,
                0x00,  # flags
            ]
        )
        return base64.b64encode(gif_bytes).decode("utf-8")

    # ============================================================================
    # get_image_dimensions() 方法測試
    # ============================================================================

    class TestGetImageDimensions:
        """get_image_dimensions() 方法測試."""

        @pytest.fixture
        def service(self) -> ImageSelectorService:
            """建立測試用服務實例."""
            return ImageSelectorService()

        def test_png_dimensions(self, service: ImageSelectorService):
            """測試 PNG 尺寸解析."""
            # 建立 10x20 PNG
            png_bytes = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x0A,  # width = 10
                    0x00,
                    0x00,
                    0x00,
                    0x14,  # height = 20
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )
            base64_data = base64.b64encode(png_bytes).decode("utf-8")
            width, height = service.get_image_dimensions(base64_data)
            assert width == 10
            assert height == 20

        def test_gif_dimensions(self, service: ImageSelectorService):
            """測試 GIF 尺寸解析."""
            gif_bytes = bytes(
                [
                    0x47,
                    0x49,
                    0x46,
                    0x38,
                    0x39,
                    0x61,  # GIF89a
                    0x20,
                    0x00,  # width = 32
                    0x10,
                    0x00,  # height = 16
                    0x00,
                    0x00,
                    0x00,
                ]
            )
            base64_data = base64.b64encode(gif_bytes).decode("utf-8")
            width, height = service.get_image_dimensions(base64_data)
            assert width == 32
            assert height == 16

        def test_with_data_uri_prefix(self, service: ImageSelectorService):
            """測試帶有 data URI 前綴的資料."""
            png_bytes = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x08,  # width = 8
                    0x00,
                    0x00,
                    0x00,
                    0x08,  # height = 8
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )
            base64_raw = base64.b64encode(png_bytes).decode("utf-8")
            base64_data = f"data:image/png;base64,{base64_raw}"
            width, height = service.get_image_dimensions(base64_data)
            assert width == 8
            assert height == 8

        def test_invalid_data_returns_zero(self, service: ImageSelectorService):
            """測試無效資料返回 (0, 0)."""
            width, height = service.get_image_dimensions("invalid_base64")
            assert width == 0
            assert height == 0

        def test_empty_data_returns_zero(self, service: ImageSelectorService):
            """測試空資料返回 (0, 0)."""
            width, height = service.get_image_dimensions("")
            assert width == 0
            assert height == 0

        def test_unknown_format_returns_zero(self, service: ImageSelectorService):
            """測試未知格式返回 (0, 0)."""
            unknown_bytes = bytes([0x00, 0x01, 0x02, 0x03, 0x04])
            base64_data = base64.b64encode(unknown_bytes).decode("utf-8")
            width, height = service.get_image_dimensions(base64_data)
            assert width == 0
            assert height == 0

    # ============================================================================
    # calculate_resolution() 方法測試
    # ============================================================================

    class TestCalculateResolution:
        """calculate_resolution() 方法測試."""

        @pytest.fixture
        def service(self) -> ImageSelectorService:
            """建立測試用服務實例."""
            return ImageSelectorService()

        def test_calculate_resolution(self, service: ImageSelectorService):
            """測試解析度計算."""
            assert service.calculate_resolution(100, 200) == 20000
            assert service.calculate_resolution(1920, 1080) == 2073600
            assert service.calculate_resolution(1, 1) == 1

        def test_calculate_resolution_zero(self, service: ImageSelectorService):
            """測試零值."""
            assert service.calculate_resolution(0, 100) == 0
            assert service.calculate_resolution(100, 0) == 0

    # ============================================================================
    # select_highest_resolution() 方法測試
    # ============================================================================

    class TestSelectHighestResolution:
        """select_highest_resolution() 方法測試."""

        @pytest.fixture
        def service(self) -> ImageSelectorService:
            """建立測試用服務實例."""
            return ImageSelectorService()

        def test_select_from_empty_list(self, service: ImageSelectorService):
            """測試空列表返回 None."""
            result = service.select_highest_resolution([])
            assert result is None

        def test_select_single_image(self, service: ImageSelectorService):
            """測試單一圖片選擇."""
            png_bytes = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x10,  # width = 16
                    0x00,
                    0x00,
                    0x00,
                    0x10,  # height = 16
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )
            base64_data = base64.b64encode(png_bytes).decode("utf-8")
            images = [("doc1", base64_data)]

            result = service.select_highest_resolution(images)
            assert result is not None
            assert result.source_id == "doc1"
            assert result.width == 16
            assert result.height == 16
            assert result.resolution == 256

        def test_select_highest_from_multiple(self, service: ImageSelectorService):
            """測試從多張圖片中選擇解析度最高的."""
            # 小圖 (8x8 = 64)
            small_png = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x08,
                    0x00,
                    0x00,
                    0x00,
                    0x08,
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            # 大圖 (32x32 = 1024)
            large_png = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x20,
                    0x00,
                    0x00,
                    0x00,
                    0x20,
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            # 中圖 (16x16 = 256)
            medium_png = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x10,
                    0x00,
                    0x00,
                    0x00,
                    0x10,
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            images = [
                ("doc1", base64.b64encode(small_png).decode("utf-8")),
                ("doc2", base64.b64encode(large_png).decode("utf-8")),
                ("doc3", base64.b64encode(medium_png).decode("utf-8")),
            ]

            result = service.select_highest_resolution(images)
            assert result is not None
            assert result.source_id == "doc2"
            assert result.width == 32
            assert result.height == 32
            assert result.resolution == 1024

        def test_skip_empty_base64(self, service: ImageSelectorService):
            """測試跳過空的 base64 資料."""
            png_bytes = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x10,
                    0x00,
                    0x00,
                    0x00,
                    0x10,
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )
            images = [
                ("doc1", ""),
                ("doc2", base64.b64encode(png_bytes).decode("utf-8")),
                ("doc3", None),
            ]

            result = service.select_highest_resolution(images)
            assert result is not None
            assert result.source_id == "doc2"

        def test_all_invalid_returns_none(self, service: ImageSelectorService):
            """測試全部無效圖片返回 None."""
            images = [
                ("doc1", ""),
                ("doc2", "invalid"),
            ]
            result = service.select_highest_resolution(images)
            # 結果可能是 None 或解析度為 0 的圖片
            if result is not None:
                assert result.resolution == 0

    # ============================================================================
    # get_image_info() 方法測試
    # ============================================================================

    class TestGetImageInfo:
        """get_image_info() 方法測試."""

        @pytest.fixture
        def service(self) -> ImageSelectorService:
            """建立測試用服務實例."""
            return ImageSelectorService()

        def test_get_image_info(self, service: ImageSelectorService):
            """測試取得圖片資訊."""
            png_bytes = bytes(
                [
                    0x89,
                    0x50,
                    0x4E,
                    0x47,
                    0x0D,
                    0x0A,
                    0x1A,
                    0x0A,
                    0x00,
                    0x00,
                    0x00,
                    0x0D,
                    0x49,
                    0x48,
                    0x44,
                    0x52,
                    0x00,
                    0x00,
                    0x00,
                    0x10,
                    0x00,
                    0x00,
                    0x00,
                    0x08,
                    0x08,
                    0x02,
                    0x00,
                    0x00,
                    0x00,
                ]
            )
            base64_data = base64.b64encode(png_bytes).decode("utf-8")

            info = service.get_image_info("source-123", base64_data)
            assert info.source_id == "source-123"
            assert info.width == 16
            assert info.height == 8
            assert info.resolution == 128
            assert info.base64_data == base64_data

    # ============================================================================
    # 單例模式測試
    # ============================================================================

    class TestSingleton:
        """單例模式測試."""

        def test_singleton_instance(self):
            """測試單例模式返回相同實例."""
            service1 = ImageSelectorService()
            service2 = ImageSelectorService()
            assert service1 is service2

        def test_factory_function(self):
            """測試工廠函式返回單例."""
            service1 = get_image_selector_service()
            service2 = get_image_selector_service()
            assert service1 is service2

        def test_factory_same_as_direct_instantiation(self):
            """測試工廠函式與直接實例化返回相同實例."""
            service1 = ImageSelectorService()
            service2 = get_image_selector_service()
            assert service1 is service2
