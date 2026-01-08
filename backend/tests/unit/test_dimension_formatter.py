"""Dimension Formatter Service 單元測試."""

import pytest
from app.services.dimension_formatter import (
    DimensionFormatterService,
    get_dimension_formatter_service,
)
from app.models.boq_item import BOQItem


@pytest.fixture
def formatter():
    """取得 DimensionFormatterService 實例."""
    return get_dimension_formatter_service()


@pytest.fixture
def fabric_item():
    """建立面料項目."""
    return BOQItem(
        id="test-fabric-1",
        no=1,
        item_no="FAB-001",
        description="Fabric upholstery with repeat pattern",
        dimension="",
        source_document_id="doc-1",
    )


@pytest.fixture
def fabric_item_plain():
    """建立無花紋面料項目."""
    return BOQItem(
        id="test-fabric-2",
        no=2,
        item_no="FAB-002",
        description="Plain leather for sofa",
        dimension="",
        source_document_id="doc-1",
    )


@pytest.fixture
def circular_furniture():
    """建立圓形家具項目."""
    return BOQItem(
        id="test-circular-1",
        no=3,
        item_no="FUR-001",
        description="Round coffee table",
        dimension="Dia.600 x H450",
        source_document_id="doc-1",
    )


@pytest.fixture
def regular_furniture():
    """建立一般家具項目."""
    return BOQItem(
        id="test-regular-1",
        no=4,
        item_no="FUR-002",
        description="Rectangular desk",
        dimension="W1200 x D600 x H750",
        source_document_id="doc-1",
    )


class TestDimensionFormatterService:
    """DimensionFormatterService 測試."""

    def test_singleton(self):
        """測試單例模式."""
        service1 = get_dimension_formatter_service()
        service2 = get_dimension_formatter_service()
        assert service1 is service2

    def test_is_fabric_with_fabric_keyword(self, formatter):
        """測試面料識別 - 描述含 fabric 關鍵字."""
        item = BOQItem(
            id="test-1",
            no=1,
            item_no="FAB-001",
            description="Fabric upholstery material",
            source_document_id="doc-1",
        )
        assert formatter.is_fabric(item) is True

    def test_is_fabric_with_leather_keyword(self, formatter):
        """測試面料識別 - 描述含 leather 關鍵字."""
        item = BOQItem(
            id="test-2",
            no=2,
            item_no="LEA-001",
            description="Italian leather cover",
            source_document_id="doc-1",
        )
        assert formatter.is_fabric(item) is True

    def test_is_fabric_with_furniture(self, formatter, regular_furniture):
        """測試面料識別 - 家具項目."""
        assert formatter.is_fabric(regular_furniture) is False

    def test_is_fabric_with_materials_specs(self, formatter):
        """測試面料識別 - materials_specs 含面料關鍵字."""
        item = BOQItem(
            id="test-3",
            no=3,
            item_no="MAT-001",
            description="Sofa cover",
            materials_specs="Premium leather finish",
            source_document_id="doc-1",
        )
        assert formatter.is_fabric(item) is True


class TestFabricDimension:
    """面料 Dimension 格式化測試."""

    def test_fabric_with_repeat_pattern(self, formatter, fabric_item):
        """測試面料 - 有 repeat 顯示 pattern."""
        result = formatter.format_dimension(fabric_item)
        assert result == "pattern"

    def test_fabric_without_repeat_plain(self, formatter, fabric_item_plain):
        """測試面料 - 無 repeat 顯示 plain."""
        result = formatter.format_dimension(fabric_item_plain)
        assert result == "plain"

    def test_fabric_repeat_in_materials_specs(self, formatter):
        """測試面料 - repeat 在 materials_specs 中."""
        item = BOQItem(
            id="test-fab-3",
            no=5,
            item_no="FAB-003",
            description="Upholstery fabric",
            materials_specs="Horizontal repeat 64cm, Vertical repeat 32cm",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert result == "pattern"


class TestCircularDimension:
    """圓形家具 Dimension 格式化測試."""

    def test_circular_dia_format(self, formatter, circular_furniture):
        """測試圓形家具 - Dia.600 x H450 格式."""
        result = formatter.format_dimension(circular_furniture)
        assert "Dia." in result
        assert "600" in result

    def test_circular_diameter_format(self, formatter):
        """測試圓形家具 - diameter 關鍵字."""
        item = BOQItem(
            id="test-cir-2",
            no=6,
            item_no="FUR-003",
            description="Round table",
            dimension="diameter 800 height 400",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert "Dia." in result
        assert "800" in result

    def test_circular_symbol_format(self, formatter):
        """測試圓形家具 - Ø 符號."""
        item = BOQItem(
            id="test-cir-3",
            no=7,
            item_no="FUR-004",
            description="Round stool",
            dimension="Ø450 x 550H",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert "Dia." in result
        assert "450" in result


class TestFurnitureDimension:
    """一般家具 Dimension 格式化測試."""

    def test_furniture_wdh_format(self, formatter, regular_furniture):
        """測試一般家具 - W x D x H 格式."""
        result = formatter.format_dimension(regular_furniture)
        assert "×" in result
        assert "1200" in result
        assert "600" in result
        assert "750" in result

    def test_furniture_plain_numbers(self, formatter):
        """測試一般家具 - 純數字格式 800 x 600 x 450."""
        item = BOQItem(
            id="test-fur-2",
            no=8,
            item_no="FUR-005",
            description="Cabinet",
            dimension="800 x 600 x 450",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert "800" in result
        assert "600" in result
        assert "450" in result

    def test_furniture_oa_prefix(self, formatter):
        """測試一般家具 - OA 前綴."""
        item = BOQItem(
            id="test-fur-3",
            no=9,
            item_no="FUR-006",
            description="Wardrobe",
            dimension="OA: 2000 x 600 x 2100",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert "2000" in result
        assert "600" in result
        assert "2100" in result

    def test_furniture_overall_prefix(self, formatter):
        """測試一般家具 - overall 前綴."""
        item = BOQItem(
            id="test-fur-4",
            no=10,
            item_no="FUR-007",
            description="Bed frame",
            dimension="overall 2000x1600x450",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert "2000" in result
        assert "1600" in result
        assert "450" in result


class TestEdgeCases:
    """邊界情況測試."""

    def test_empty_dimension(self, formatter):
        """測試空 dimension."""
        item = BOQItem(
            id="test-edge-1",
            no=11,
            item_no="EDG-001",
            description="Some furniture",
            dimension="",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert result == ""

    def test_none_dimension(self, formatter):
        """測試 None dimension."""
        item = BOQItem(
            id="test-edge-2",
            no=12,
            item_no="EDG-002",
            description="Another furniture",
            dimension=None,
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        assert result == ""

    def test_unparseable_dimension(self, formatter):
        """測試無法解析的 dimension - 返回原始值."""
        item = BOQItem(
            id="test-edge-3",
            no=13,
            item_no="EDG-003",
            description="Special item",
            dimension="See drawing for details",
            source_document_id="doc-1",
        )
        result = formatter.format_dimension(item)
        # 無法解析時應返回原始值
        assert result == "See drawing for details"
