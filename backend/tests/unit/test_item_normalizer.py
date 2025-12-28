"""Unit tests for ItemNormalizerService.

測試 Item No. 標準化服務的各種格式轉換與比對功能。
"""

import pytest

from app.services.item_normalizer import (
    ItemNormalizerService,
    get_item_normalizer_service,
)


class TestItemNormalizerService:
    """ItemNormalizerService 單元測試."""

    @pytest.fixture
    def service(self) -> ItemNormalizerService:
        """建立測試用服務實例."""
        return ItemNormalizerService()

    # ============================================================================
    # normalize() 方法測試
    # ============================================================================

    class TestNormalize:
        """normalize() 方法測試."""

        @pytest.fixture
        def service(self) -> ItemNormalizerService:
            """建立測試用服務實例."""
            return ItemNormalizerService()

        def test_normalize_basic_format(self, service: ItemNormalizerService):
            """測試基本格式保持不變."""
            assert service.normalize("DLX-100") == "DLX-100"
            assert service.normalize("ABC-123") == "ABC-123"

        def test_normalize_lowercase_to_uppercase(self, service: ItemNormalizerService):
            """測試小寫轉大寫."""
            assert service.normalize("dlx-100") == "DLX-100"
            assert service.normalize("abc-123") == "ABC-123"
            assert service.normalize("AbC-123") == "ABC-123"

        def test_normalize_remove_spaces(self, service: ItemNormalizerService):
            """測試移除空格."""
            assert service.normalize("DLX 100") == "DLX100"
            assert service.normalize("  DLX-100  ") == "DLX-100"
            assert service.normalize("DLX  -  100") == "DLX-100"

        def test_normalize_dot_to_dash(self, service: ItemNormalizerService):
            """測試點號轉為破折號."""
            assert service.normalize("DLX.100") == "DLX-100"
            assert service.normalize("A.B.C") == "A-B-C"

        def test_normalize_underscore_to_dash(self, service: ItemNormalizerService):
            """測試底線轉為破折號."""
            assert service.normalize("DLX_100") == "DLX-100"
            assert service.normalize("A_B_C") == "A-B-C"

        def test_normalize_multiple_dashes(self, service: ItemNormalizerService):
            """測試多個破折號合併為一個."""
            assert service.normalize("DLX--100") == "DLX-100"
            assert service.normalize("ABC---123") == "ABC-123"

        def test_normalize_mixed_separators(self, service: ItemNormalizerService):
            """測試混合分隔符號."""
            assert service.normalize("DLX.-_100") == "DLX-100"
            assert service.normalize("A.B-C_D") == "A-B-C-D"

        def test_normalize_leading_trailing_dashes(self, service: ItemNormalizerService):
            """測試移除開頭結尾的破折號."""
            assert service.normalize("-DLX-100-") == "DLX-100"
            assert service.normalize("--ABC--") == "ABC"

        def test_normalize_empty_string(self, service: ItemNormalizerService):
            """測試空字串."""
            assert service.normalize("") == ""
            assert service.normalize("   ") == ""

        def test_normalize_none_input(self, service: ItemNormalizerService):
            """測試 None 輸入（應由呼叫端處理）."""
            # 假設傳入空字串行為
            assert service.normalize("") == ""

        def test_normalize_complex_cases(self, service: ItemNormalizerService):
            """測試複雜案例."""
            assert service.normalize("  dlx.100-a_b  ") == "DLX-100-A-B"
            assert service.normalize("STD...200") == "STD-200"
            assert service.normalize("item___no") == "ITEM-NO"

    # ============================================================================
    # are_equivalent() 方法測試
    # ============================================================================

    class TestAreEquivalent:
        """are_equivalent() 方法測試."""

        @pytest.fixture
        def service(self) -> ItemNormalizerService:
            """建立測試用服務實例."""
            return ItemNormalizerService()

        def test_equivalent_same_format(self, service: ItemNormalizerService):
            """測試相同格式等價."""
            assert service.are_equivalent("DLX-100", "DLX-100") is True

        def test_equivalent_different_case(self, service: ItemNormalizerService):
            """測試不同大小寫等價."""
            assert service.are_equivalent("DLX-100", "dlx-100") is True
            assert service.are_equivalent("ABC", "abc") is True

        def test_equivalent_different_separator(self, service: ItemNormalizerService):
            """測試不同分隔符號等價."""
            assert service.are_equivalent("DLX-100", "DLX.100") is True
            assert service.are_equivalent("DLX-100", "DLX_100") is True

        def test_equivalent_with_spaces(self, service: ItemNormalizerService):
            """測試有空格時等價."""
            assert service.are_equivalent("DLX-100", "  DLX-100  ") is True
            assert service.are_equivalent("DLX100", "DLX 100") is True

        def test_not_equivalent_different_values(self, service: ItemNormalizerService):
            """測試不同值不等價."""
            assert service.are_equivalent("DLX-100", "DLX-101") is False
            assert service.are_equivalent("ABC", "DEF") is False

        def test_not_equivalent_similar_but_different(
            self, service: ItemNormalizerService
        ):
            """測試相似但不同的值不等價."""
            assert service.are_equivalent("DLX100", "DLX-1000") is False

    # ============================================================================
    # is_format_different() 方法測試
    # ============================================================================

    class TestIsFormatDifferent:
        """is_format_different() 方法測試."""

        @pytest.fixture
        def service(self) -> ItemNormalizerService:
            """建立測試用服務實例."""
            return ItemNormalizerService()

        def test_format_different_case(self, service: ItemNormalizerService):
            """測試大小寫格式不同."""
            assert service.is_format_different("DLX-100", "dlx-100") is True

        def test_format_different_separator(self, service: ItemNormalizerService):
            """測試分隔符號格式不同."""
            assert service.is_format_different("DLX-100", "DLX.100") is True
            assert service.is_format_different("DLX-100", "DLX_100") is True

        def test_format_same(self, service: ItemNormalizerService):
            """測試格式相同."""
            assert service.is_format_different("DLX-100", "DLX-100") is False

        def test_format_different_not_equivalent(self, service: ItemNormalizerService):
            """測試不等價的值返回 False."""
            assert service.is_format_different("DLX-100", "DLX-101") is False

    # ============================================================================
    # 單例模式測試
    # ============================================================================

    class TestSingleton:
        """單例模式測試."""

        def test_singleton_instance(self):
            """測試單例模式返回相同實例."""
            service1 = ItemNormalizerService()
            service2 = ItemNormalizerService()
            assert service1 is service2

        def test_factory_function(self):
            """測試工廠函式返回單例."""
            service1 = get_item_normalizer_service()
            service2 = get_item_normalizer_service()
            assert service1 is service2

        def test_factory_same_as_direct_instantiation(self):
            """測試工廠函式與直接實例化返回相同實例."""
            service1 = ItemNormalizerService()
            service2 = get_item_normalizer_service()
            assert service1 is service2
