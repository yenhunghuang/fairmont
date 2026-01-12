"""FabricValidatorService 單元測試.

測試面料項目驗證邏輯，確保：
1. 有效的獨立面料項目通過驗證
2. 來自 FURNITURE COM 的無效引用被過濾
3. 家具項目不受影響
"""

import pytest
from app.models.boq_item import BOQItem
from app.services.fabric_validator import FabricValidatorService, get_fabric_validator_service


class TestFabricValidatorService:
    """測試 FabricValidatorService."""

    @pytest.fixture
    def service(self):
        """建立測試用的 FabricValidatorService 實例."""
        return FabricValidatorService()

    def _create_item(
        self,
        item_no: str,
        category: int = 5,
        location: str = None,
        dimension: str = None,
        brand: str = None,
        description: str = "Test Item",
    ) -> BOQItem:
        """建立測試用的 BOQItem."""
        return BOQItem(
            no=1,
            item_no=item_no,
            description=description,
            category=category,
            location=location,
            dimension=dimension,
            brand=brand,
            source_document_id="test-doc",
        )

    # ========== 有效面料項目測試 ==========

    def test_valid_fabric_item_passes(self, service):
        """有效的獨立面料項目應該通過驗證."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern Europe-Prodigy PRO 682-Lt Neutral-137cmW plain",
            brand="Morbern Europe",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1
        assert result[0].item_no == "DLX-500"

    def test_valid_fabric_with_multiple_locations(self, service):
        """多個 location 的面料項目應該通過驗證."""
        item = self._create_item(
            item_no="DLX-501",
            category=5,
            location="DLX-100 King Bed, DLX-103 Queen Bed",
            dimension="Fabric-Casamance-Jardin Neroli-Multico-140cmW pattern",
            brand="Casamance",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1

    # ========== 無效面料項目測試 ==========

    def test_fabric_without_location_filtered(self, service):
        """缺少 location 的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location=None,
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_with_empty_location_filtered(self, service):
        """空字串 location 的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="",
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_with_whitespace_location_filtered(self, service):
        """只有空白的 location 應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="   ",
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_without_valid_dimension_filtered(self, service):
        """dimension 格式不完整的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl",  # 不完整的格式
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_with_short_dimension_filtered(self, service):
        """dimension 分隔部分不足的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern",  # 只有兩部分
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_with_non_fabric_dimension_prefix_filtered(self, service):
        """dimension 不以面料類型開頭的項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="W800 x D600 x H450 mm",  # 家具尺寸格式
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_without_dimension_filtered(self, service):
        """缺少 dimension 的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension=None,
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_without_brand_filtered(self, service):
        """缺少 brand 的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand=None,
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    def test_fabric_with_empty_brand_filtered(self, service):
        """空字串 brand 的面料項目應被過濾."""
        item = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand="",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 0

    # ========== 家具項目測試 ==========

    def test_furniture_items_not_affected(self, service):
        """家具項目（category=1）不受影響."""
        item = self._create_item(
            item_no="DLX-100",
            category=1,  # 家具
            location=None,
            dimension=None,
            brand=None,
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1
        assert result[0].item_no == "DLX-100"

    def test_furniture_with_incomplete_fields_passes(self, service):
        """家具項目即使欄位不完整也通過."""
        item = self._create_item(
            item_no="DLX-100",
            category=1,
            location=None,
            dimension="W800 x D600 x H450 mm",
            brand=None,
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1

    # ========== 混合項目測試 ==========

    def test_mixed_items_filtering(self, service):
        """混合的家具和面料項目應正確過濾."""
        furniture = self._create_item(
            item_no="DLX-100",
            category=1,
            location=None,
            dimension="W800 x D600 x H450 mm",
            brand="Custom Made",
        )
        valid_fabric = self._create_item(
            item_no="DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern Europe-Prodigy-Lt Neutral-137cmW plain",
            brand="Morbern Europe",
        )
        invalid_fabric = self._create_item(
            item_no="DLX-501",
            category=5,
            location=None,  # 缺少 location - 來自 FURNITURE COM 引用
            dimension="Fabric",
            brand=None,
        )

        result = service.validate_fabric_items([furniture, valid_fabric, invalid_fabric])
        assert len(result) == 2
        assert result[0].item_no == "DLX-100"
        assert result[1].item_no == "DLX-500"

    # ========== dimension 格式測試 ==========

    def test_leather_dimension_passes(self, service):
        """Leather 開頭的 dimension 應通過."""
        item = self._create_item(
            item_no="DLX-502",
            category=5,
            location="DLX-100 King Bed",
            dimension="Leather-Garrett Leather-Classic-Black-140cmW plain",
            brand="Garrett Leather",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1

    def test_textile_dimension_passes(self, service):
        """Textile 開頭的 dimension 應通過."""
        item = self._create_item(
            item_no="DLX-503",
            category=5,
            location="DLX-100 King Bed",
            dimension="Textile-Brand-Pattern-Color-Width plain",
            brand="Brand",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1

    def test_dimension_case_insensitive(self, service):
        """dimension 前綴應不區分大小寫."""
        item = self._create_item(
            item_no="DLX-504",
            category=5,
            location="DLX-100 King Bed",
            dimension="VINYL-Morbern-Pattern-Color-Width plain",
            brand="Morbern",
        )
        result = service.validate_fabric_items([item])
        assert len(result) == 1

    # ========== 單例工廠測試 ==========

    def test_singleton_factory(self):
        """工廠函式應返回單例實例."""
        instance1 = get_fabric_validator_service()
        instance2 = get_fabric_validator_service()
        assert instance1 is instance2


class TestFilterByUploadedFiles:
    """測試 filter_by_uploaded_files 方法."""

    @pytest.fixture
    def service(self):
        return FabricValidatorService()

    def _create_item(
        self,
        item_no: str,
        category: int,
        location: str = None,
        dimension: str = None,
        brand: str = None,
    ) -> BOQItem:
        return BOQItem(
            no=1,
            item_no=item_no,
            description="Test",
            category=category,
            location=location,
            dimension=dimension,
            brand=brand,
            source_document_id="test-doc",
        )

    def test_no_fabric_file_removes_all_fabric(self, service):
        """沒有上傳面料檔案時，移除所有面料項目."""
        furniture = self._create_item("DLX-100", category=1)
        fabric = self._create_item(
            "DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand="Morbern",
        )

        result = service.filter_by_uploaded_files(
            [furniture, fabric],
            ["Casegoods & Seatings.pdf"],  # 沒有面料檔案
        )

        assert len(result) == 1
        assert result[0].item_no == "DLX-100"

    def test_has_fabric_file_keeps_valid_fabric(self, service):
        """有上傳面料檔案時，保留有效的面料項目."""
        furniture = self._create_item("DLX-100", category=1)
        valid_fabric = self._create_item(
            "DLX-500",
            category=5,
            location="DLX-100 King Bed",
            dimension="Vinyl-Morbern-Pattern-Color-Width plain",
            brand="Morbern",
        )

        result = service.filter_by_uploaded_files(
            [furniture, valid_fabric],
            ["Casegoods.pdf", "Fabric & Leather.pdf"],  # 有面料檔案
        )

        assert len(result) == 2

    def test_has_fabric_file_filters_invalid_fabric(self, service):
        """有上傳面料檔案時，過濾無效的面料項目."""
        furniture = self._create_item("DLX-100", category=1)
        invalid_fabric = self._create_item(
            "DLX-500",
            category=5,
            location=None,  # 缺少 location
            dimension="Vinyl",
            brand=None,
        )

        result = service.filter_by_uploaded_files(
            [furniture, invalid_fabric],
            ["Fabric.pdf"],
        )

        assert len(result) == 1
        assert result[0].item_no == "DLX-100"

    def test_has_fabric_file_detected_by_keyword(self, service):
        """測試面料檔案關鍵字偵測."""
        assert service.has_fabric_file(["Fabric & Leather.pdf"]) is True
        assert service.has_fabric_file(["Vinyl Specs.pdf"]) is True
        assert service.has_fabric_file(["LEATHER-SPEC.PDF"]) is True
        assert service.has_fabric_file(["Casegoods.pdf"]) is False
        assert service.has_fabric_file(["Bay Tower.pdf"]) is False

    def test_case_insensitive_fabric_detection(self, service):
        """面料檔案偵測不區分大小寫."""
        assert service.has_fabric_file(["FABRIC.PDF"]) is True
        assert service.has_fabric_file(["fabric.pdf"]) is True
        assert service.has_fabric_file(["FaBrIc.pdf"]) is True


class TestFabricValidatorHasValidDimension:
    """測試 _has_valid_fabric_dimension 方法."""

    @pytest.fixture
    def service(self):
        return FabricValidatorService()

    def test_valid_vinyl_dimension(self, service):
        """有效的 Vinyl dimension."""
        assert service._has_valid_fabric_dimension(
            "Vinyl-Morbern Europe-Prodigy PRO 682-Lt Neutral-137cmW plain"
        )

    def test_valid_fabric_dimension(self, service):
        """有效的 Fabric dimension."""
        assert service._has_valid_fabric_dimension(
            "Fabric-Casamance-Jardin Neroli 42210236-Multico-140cmW pattern"
        )

    def test_valid_leather_dimension(self, service):
        """有效的 Leather dimension."""
        assert service._has_valid_fabric_dimension(
            "Leather-Garrett Leather-Classic-Black-140cmW"
        )

    def test_invalid_furniture_dimension(self, service):
        """家具尺寸格式應返回 False."""
        assert not service._has_valid_fabric_dimension("W800 x D600 x H450 mm")

    def test_invalid_simple_type(self, service):
        """只有類型名稱應返回 False."""
        assert not service._has_valid_fabric_dimension("Vinyl")
        assert not service._has_valid_fabric_dimension("Fabric")

    def test_invalid_two_parts(self, service):
        """只有兩部分應返回 False."""
        assert not service._has_valid_fabric_dimension("Vinyl-Morbern")

    def test_invalid_three_parts(self, service):
        """只有三部分應返回 False."""
        assert not service._has_valid_fabric_dimension("Vinyl-Morbern-Pattern")

    def test_invalid_none(self, service):
        """None 應返回 False."""
        assert not service._has_valid_fabric_dimension(None)

    def test_invalid_empty_string(self, service):
        """空字串應返回 False."""
        assert not service._has_valid_fabric_dimension("")

    def test_valid_with_na_parts(self, service):
        """包含 N/A 部分的有效格式."""
        assert service._has_valid_fabric_dimension(
            "Fabric-Casamance-Pattern-Color-N/A pattern"
        )
