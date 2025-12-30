"""MergeService 單元測試.

測試面料跟隨家具排序邏輯。
"""

import pytest
from unittest.mock import MagicMock, patch

from app.models.boq_item import BOQItem
from app.services.merge_service import MergeService


class TestParseFabricTargets:
    """測試 _parse_fabric_targets 方法."""

    @pytest.fixture
    def service(self):
        """建立 MergeService 實例."""
        with patch("app.services.merge_service.get_item_normalizer_service") as mock_normalizer:
            mock_normalizer.return_value.normalize = lambda x: x.upper().replace(" ", "")
            with patch("app.services.merge_service.get_image_selector_service"):
                service = MergeService()
                service._rules_loaded = True
                service._merge_rules = None
                return service

    def test_parse_fabric_targets_single(self, service):
        """測試解析單一目標家具 item_no."""
        result = service._parse_fabric_targets("Vinyl to DLX-100")
        assert result == ["DLX-100"]

    def test_parse_fabric_targets_multiple(self, service):
        """測試解析多個目標家具 item_no."""
        result = service._parse_fabric_targets("Fabric to DLX-100 and to DLX-200")
        assert result == ["DLX-100", "DLX-200"]

    def test_parse_fabric_targets_with_lowercase(self, service):
        """測試大小寫不敏感."""
        result = service._parse_fabric_targets("Leather TO abc-123")
        assert result == ["ABC-123"]

    def test_parse_fabric_targets_with_longer_description(self, service):
        """測試較長描述中的解析."""
        result = service._parse_fabric_targets("Premium Fabric to GR-001 for Guest Room")
        assert result == ["GR-001"]

    def test_parse_fabric_targets_without_to(self, service):
        """測試沒有 'to' 的描述返回空列表."""
        result = service._parse_fabric_targets("King Bed")
        assert result == []

    def test_parse_fabric_targets_with_none(self, service):
        """測試 None 描述返回空列表."""
        result = service._parse_fabric_targets(None)
        assert result == []

    def test_parse_fabric_targets_with_empty_string(self, service):
        """測試空字串返回空列表."""
        result = service._parse_fabric_targets("")
        assert result == []

    def test_parse_fabric_targets_with_dot_in_item_no(self, service):
        """測試含小數點的 item_no（如 DLX-100.1）."""
        result = service._parse_fabric_targets("Fabric to DLX-100.1")
        assert result == ["DLX-100.1"]

    def test_parse_fabric_targets_multiple_with_dots(self, service):
        """測試多個含小數點的 item_no."""
        result = service._parse_fabric_targets("Fabric to DLX-100.1 and to DLX-100.2")
        assert result == ["DLX-100.1", "DLX-100.2"]


class TestSortItemsFabricFollowsFurniture:
    """測試 _sort_items_fabric_follows_furniture 方法."""

    @pytest.fixture
    def service(self):
        """建立 MergeService 實例."""
        with patch("app.services.merge_service.get_item_normalizer_service") as mock_normalizer:
            mock_normalizer.return_value.normalize = lambda x: x.upper().replace(" ", "").replace("-", "-")
            with patch("app.services.merge_service.get_image_selector_service"):
                service = MergeService()
                service._rules_loaded = True
                service._merge_rules = None
                return service

    def _create_item(self, item_no: str, description: str) -> BOQItem:
        """建立測試用 BOQItem."""
        return BOQItem(
            no=1,
            item_no=item_no,
            item_no_normalized=item_no.upper(),
            description=description,
            source_document_id="test-doc-001",
        )

    def test_fabric_follows_furniture_basic(self, service):
        """測試基本的面料跟隨家具排序."""
        items = [
            self._create_item("FAB-001", "Vinyl to DLX-100"),
            self._create_item("DLX-100", "Deluxe King Bed"),
            self._create_item("GR-001", "Guest Chair"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序: DLX-100 -> FAB-001 -> GR-001
        assert [item.item_no for item in result] == ["DLX-100", "FAB-001", "GR-001"]

    def test_multiple_fabrics_for_one_furniture(self, service):
        """測試多個面料對應同一家具."""
        items = [
            self._create_item("FAB-002", "Leather to DLX-100"),
            self._create_item("FAB-001", "Vinyl to DLX-100"),
            self._create_item("DLX-100", "Deluxe King Bed"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序: DLX-100 -> FAB-001 -> FAB-002
        assert [item.item_no for item in result] == ["DLX-100", "FAB-001", "FAB-002"]

    def test_furniture_without_fabrics_at_bottom(self, service):
        """測試沒有面料引用的家具放到底部."""
        items = [
            self._create_item("ZZZ-001", "Table"),  # 無面料引用
            self._create_item("FAB-001", "Vinyl to AAA-001"),
            self._create_item("AAA-001", "Armchair"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序: AAA-001 -> FAB-001 -> ZZZ-001
        assert [item.item_no for item in result] == ["AAA-001", "FAB-001", "ZZZ-001"]

    def test_complex_ordering(self, service):
        """測試複雜排序場景."""
        items = [
            self._create_item("C-001", "Chair"),
            self._create_item("FAB-B", "Fabric to A-001"),
            self._create_item("B-001", "Bed"),
            self._create_item("FAB-A", "Vinyl to A-001"),
            self._create_item("A-001", "Armchair"),
            self._create_item("FAB-C", "Leather to D-001"),
            self._create_item("D-001", "Desk"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序:
        # 1. 所有家具按 item_no 排序: A-001, B-001, C-001, D-001
        # 2. 面料插入到對應家具之後:
        #    A-001 -> FAB-A, FAB-B
        #    D-001 -> FAB-C
        expected = ["A-001", "FAB-A", "FAB-B", "B-001", "C-001", "D-001", "FAB-C"]
        assert [item.item_no for item in result] == expected

    def test_orphan_fabrics(self, service):
        """測試孤立面料（目標家具不存在）."""
        items = [
            self._create_item("FAB-001", "Vinyl to MISSING-001"),  # 目標不存在
            self._create_item("A-001", "Armchair"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序: A-001 -> FAB-001（孤立面料放最後）
        assert [item.item_no for item in result] == ["A-001", "FAB-001"]

    def test_empty_list(self, service):
        """測試空列表."""
        result = service._sort_items_fabric_follows_furniture([])
        assert result == []

    def test_no_fabrics(self, service):
        """測試完全沒有面料的情況."""
        items = [
            self._create_item("C-001", "Chair"),
            self._create_item("A-001", "Armchair"),
            self._create_item("B-001", "Bed"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 全部按 item_no 排序
        assert [item.item_no for item in result] == ["A-001", "B-001", "C-001"]

    def test_all_fabrics(self, service):
        """測試全部都是面料的情況."""
        items = [
            self._create_item("FAB-002", "Vinyl to MISSING-002"),
            self._create_item("FAB-001", "Vinyl to MISSING-001"),
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 全部為孤立面料，按 item_no 排序
        assert [item.item_no for item in result] == ["FAB-001", "FAB-002"]

    def test_fabric_references_multiple_furniture(self, service):
        """測試面料引用多個家具，應重複出現在每個家具之後."""
        items = [
            self._create_item("A-001", "Armchair"),
            self._create_item("B-001", "Bed"),
            self._create_item("FAB-001", "Fabric to A-001 and to B-001"),  # 引用兩個家具
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序: A-001 -> FAB-001 -> B-001 -> FAB-001（FAB-001 出現兩次）
        expected = ["A-001", "FAB-001", "B-001", "FAB-001"]
        assert [item.item_no for item in result] == expected

    def test_fabric_references_multiple_furniture_partial_exists(self, service):
        """測試面料引用多個家具，其中部分家具不存在."""
        items = [
            self._create_item("A-001", "Armchair"),
            self._create_item("FAB-001", "Fabric to A-001 and to MISSING-001"),  # 只有 A-001 存在
        ]

        result = service._sort_items_fabric_follows_furniture(items)

        # 預期順序: A-001 -> FAB-001（只出現在 A-001 之後，MISSING-001 不存在）
        expected = ["A-001", "FAB-001"]
        assert [item.item_no for item in result] == expected


class TestMergeDetailItemsConcatenate:
    """測試 _merge_detail_items 的 concatenate 模式."""

    @pytest.fixture
    def service(self):
        """建立 MergeService 實例並設置欄位合併策略."""
        with patch("app.services.merge_service.get_item_normalizer_service") as mock_normalizer:
            mock_normalizer.return_value.normalize = lambda x: x.upper().replace(" ", "")
            with patch("app.services.merge_service.get_image_selector_service") as mock_selector:
                mock_selector.return_value.select_highest_resolution = lambda x: None
                service = MergeService()
                service._rules_loaded = True
                service._vendor_loaded = True
                service._vendor_skill = None

                # 建立策略模擬（使用簡單物件避免 MagicMock 複雜性）
                class MockStrategy:
                    def __init__(self, mode, separator=""):
                        self.mode = mode
                        self.separator = separator

                class MockFieldMerge:
                    def __init__(self):
                        self.mergeable_fields = ["location", "note", "description"]
                        self.strategies = {
                            "location": MockStrategy("concatenate", ", "),
                            "note": MockStrategy("concatenate", "; "),
                            "default": MockStrategy("fill_empty", ""),
                        }

                class MockRules:
                    def __init__(self):
                        self.field_merge = MockFieldMerge()

                    @property
                    def mergeable_fields(self):
                        return self.field_merge.mergeable_fields

                service._merge_rules = MockRules()
                return service

    def _create_item(
        self,
        item_no: str,
        location: str = None,
        note: str = None,
        description: str = "Test Item",
        source_doc_id: str = "test-doc-001"
    ) -> BOQItem:
        """建立測試用 BOQItem."""
        return BOQItem(
            no=1,
            item_no=item_no,
            item_no_normalized=item_no.upper(),
            description=description,
            location=location,
            note=note,
            source_document_id=source_doc_id,
        )

    def _create_doc(self, doc_id: str, order: int):
        """建立測試用 SourceDocument."""
        doc = MagicMock()
        doc.id = doc_id
        doc.upload_order = order
        return doc

    def test_location_concatenate_mode(self, service):
        """測試 location 欄位使用 concatenate 模式."""
        item1 = self._create_item("A-001", location="Room 101")
        item2 = self._create_item("A-001", location="Room 102")
        doc1 = self._create_doc("doc-001", 1)
        doc2 = self._create_doc("doc-002", 2)

        result = service._merge_detail_items([(item1, doc1), (item2, doc2)])

        # location 應該用 ", " 串接
        assert result.location == "Room 101, Room 102"

    def test_note_concatenate_mode(self, service):
        """測試 note 欄位使用 concatenate 模式."""
        item1 = self._create_item("A-001", note="Note 1")
        item2 = self._create_item("A-001", note="Note 2")
        doc1 = self._create_doc("doc-001", 1)
        doc2 = self._create_doc("doc-002", 2)

        result = service._merge_detail_items([(item1, doc1), (item2, doc2)])

        # note 應該用 "; " 串接
        assert result.note == "Note 1; Note 2"

    def test_concatenate_removes_duplicates(self, service):
        """測試 concatenate 模式會去除重複值."""
        item1 = self._create_item("A-001", location="Room 101")
        item2 = self._create_item("A-001", location="Room 101")  # 重複
        item3 = self._create_item("A-001", location="Room 102")
        doc1 = self._create_doc("doc-001", 1)
        doc2 = self._create_doc("doc-002", 2)
        doc3 = self._create_doc("doc-003", 3)

        result = service._merge_detail_items([(item1, doc1), (item2, doc2), (item3, doc3)])

        # 應該去除重複的 "Room 101"
        assert result.location == "Room 101, Room 102"

    def test_concatenate_skips_none_values(self, service):
        """測試 concatenate 模式跳過 None 值."""
        item1 = self._create_item("A-001", location="Room 101")
        item2 = self._create_item("A-001", location=None)
        item3 = self._create_item("A-001", location="Room 102")
        doc1 = self._create_doc("doc-001", 1)
        doc2 = self._create_doc("doc-002", 2)
        doc3 = self._create_doc("doc-003", 3)

        result = service._merge_detail_items([(item1, doc1), (item2, doc2), (item3, doc3)])

        # 應該跳過 None 值
        assert result.location == "Room 101, Room 102"

    def test_fill_empty_mode_still_works(self, service):
        """測試 fill_empty 模式（非 concatenate 欄位）仍正常運作."""
        # 注意：description 是必填欄位，所以測試 fill_empty 時使用空字串模擬
        item1 = self._create_item("A-001", description="")  # 空字串視為「無值」
        item2 = self._create_item("A-001", description="King Bed")
        doc1 = self._create_doc("doc-001", 1)
        doc2 = self._create_doc("doc-002", 2)

        result = service._merge_detail_items([(item1, doc1), (item2, doc2)])

        # description 使用 fill_empty 模式，空字串保持原樣（不會被覆蓋）
        # fill_empty 只在 None 時填補，空字串不會觸發
        assert result.description == ""

    def test_fill_empty_keeps_first_non_empty(self, service):
        """測試 fill_empty 模式保留第一個非空值."""
        item1 = self._create_item("A-001", description="Armchair")
        item2 = self._create_item("A-001", description="King Bed")  # 不應覆蓋
        doc1 = self._create_doc("doc-001", 1)
        doc2 = self._create_doc("doc-002", 2)

        result = service._merge_detail_items([(item1, doc1), (item2, doc2)])

        # fill_empty 模式下，第一個非空值被保留
        assert result.description == "Armchair"


class TestGetFieldStrategy:
    """測試 _get_field_strategy 方法."""

    @pytest.fixture
    def service(self):
        """建立 MergeService 實例."""
        with patch("app.services.merge_service.get_item_normalizer_service"):
            with patch("app.services.merge_service.get_image_selector_service"):
                service = MergeService()
                service._rules_loaded = True
                return service

    def test_returns_default_when_no_rules(self, service):
        """測試當沒有載入規則時返回預設策略."""
        service._merge_rules = None
        result = service._get_field_strategy("location")
        assert result["mode"] == "fill_empty"
        assert result["separator"] == ""

    def test_returns_field_specific_strategy(self, service):
        """測試返回欄位特定策略."""
        mock_rules = MagicMock()
        location_strategy = MagicMock()
        location_strategy.mode = "concatenate"
        location_strategy.separator = ", "
        mock_rules.field_merge.strategies = {"location": location_strategy}
        service._merge_rules = mock_rules

        result = service._get_field_strategy("location")
        assert result["mode"] == "concatenate"
        assert result["separator"] == ", "

    def test_falls_back_to_default_strategy(self, service):
        """測試欄位不存在時使用預設策略."""
        mock_rules = MagicMock()
        default_strategy = MagicMock()
        default_strategy.mode = "fill_empty"
        default_strategy.separator = ""
        mock_rules.field_merge.strategies = {"default": default_strategy}
        service._merge_rules = mock_rules

        result = service._get_field_strategy("unknown_field")
        assert result["mode"] == "fill_empty"


class TestFabricPatternFromVendorSkill:
    """測試從 VendorSkill 載入面料偵測 Pattern."""

    @pytest.fixture
    def service(self):
        """建立 MergeService 實例."""
        with patch("app.services.merge_service.get_item_normalizer_service") as mock_normalizer:
            mock_normalizer.return_value.normalize = lambda x: x.upper().replace(" ", "")
            with patch("app.services.merge_service.get_image_selector_service"):
                service = MergeService()
                service._rules_loaded = True
                service._merge_rules = None
                return service

    def test_uses_vendor_skill_pattern(self, service):
        """測試使用 VendorSkill 中的 pattern."""
        mock_vendor_skill = MagicMock()
        mock_vendor_skill.fabric_detection.pattern = r"\s+to\s+([A-Z0-9][A-Z0-9\-\.]+)"
        service._vendor_skill = mock_vendor_skill
        service._vendor_loaded = True

        result = service._parse_fabric_targets("Fabric to TEST-001")
        assert result == ["TEST-001"]

    def test_uses_fallback_pattern_when_no_vendor(self, service):
        """測試沒有 VendorSkill 時使用 fallback pattern."""
        service._vendor_skill = None
        service._vendor_loaded = True

        result = service._parse_fabric_targets("Fabric to FALLBACK-001")
        assert result == ["FALLBACK-001"]

    def test_custom_vendor_pattern(self, service):
        """測試供應商自定義 pattern."""
        # 假設某供應商使用不同格式: "for <item_no>"
        mock_vendor_skill = MagicMock()
        mock_vendor_skill.fabric_detection.pattern = r"\s+for\s+([A-Z0-9][A-Z0-9\-\.]+)"
        service._vendor_skill = mock_vendor_skill
        service._vendor_loaded = True

        result = service._parse_fabric_targets("Fabric for CUSTOM-001")
        assert result == ["CUSTOM-001"]

        # 使用 "to" 格式應該不匹配
        result_no_match = service._parse_fabric_targets("Fabric to NOMATCH-001")
        assert result_no_match == []
