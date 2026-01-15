"""MergeService 單元測試.

測試欄位合併策略與圖片選擇邏輯。
"""

import pytest
from unittest.mock import MagicMock, patch

from app.models.boq_item import BOQItem
from app.services.merge_service import MergeService


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


class TestSortItemsByPriority:
    """測試 _sort_items_by_priority 三層排序邏輯."""

    @pytest.fixture
    def service(self):
        """建立 MergeService 實例."""
        with patch("app.services.merge_service.get_item_normalizer_service") as mock_normalizer:
            mock_normalizer.return_value.normalize = lambda x: x.upper().replace(" ", "")
            with patch("app.services.merge_service.get_image_selector_service"):
                service = MergeService()
                service._rules_loaded = True
                service._vendor_loaded = True
                return service

    def _create_item(
        self,
        item_no: str,
        category: int = 1,
        qty_order_index: int = None,
    ) -> BOQItem:
        """建立測試用 BOQItem."""
        return BOQItem(
            no=1,
            item_no=item_no,
            item_no_normalized=item_no.upper(),
            description="Test Item",
            category=category,
            qty_order_index=qty_order_index,
            source_document_id="test-doc",
        )

    def test_qty_furniture_sorted_by_order_index(self, service):
        """測試數量總表家具按 order_index 排序."""
        items = [
            self._create_item("DLX-103", category=1, qty_order_index=2),
            self._create_item("DLX-101", category=1, qty_order_index=0),
            self._create_item("DLX-102", category=1, qty_order_index=1),
        ]

        result = service._sort_items_by_priority(items)

        assert [i.item_no for i in result] == ["DLX-101", "DLX-102", "DLX-103"]

    def test_extra_furniture_sorted_by_item_no(self, service):
        """測試額外家具按 item_no 字母順序排序."""
        items = [
            self._create_item("FUR-003", category=1, qty_order_index=None),
            self._create_item("FUR-001", category=1, qty_order_index=None),
            self._create_item("FUR-002", category=1, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        assert [i.item_no for i in result] == ["FUR-001", "FUR-002", "FUR-003"]

    def test_fabric_sorted_by_item_no(self, service):
        """測試面料按 item_no 字母順序排序."""
        items = [
            self._create_item("FAB-003", category=5, qty_order_index=None),
            self._create_item("FAB-001", category=5, qty_order_index=None),
            self._create_item("FAB-002", category=5, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        assert [i.item_no for i in result] == ["FAB-001", "FAB-002", "FAB-003"]

    def test_three_tier_sorting(self, service):
        """測試三層排序：額外家具按字母順序插入數量總表家具之間，面料放最後."""
        items = [
            # 面料
            self._create_item("FAB-001", category=5, qty_order_index=None),
            # 額外家具（不在數量總表）- 字母順序會在 DLX 之間
            self._create_item("DLX-101.1", category=1, qty_order_index=None),
            # 數量總表家具
            self._create_item("DLX-102", category=1, qty_order_index=1),
            self._create_item("DLX-100", category=1, qty_order_index=0),
            # 更多面料
            self._create_item("FAB-002", category=5, qty_order_index=None),
            # 更多額外家具 - 字母順序在 DLX-100 和 DLX-102 之間
            self._create_item("DLX-101", category=1, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        item_nos = [i.item_no for i in result]
        # 額外家具按字母順序插入到數量總表家具之間
        assert item_nos == [
            "DLX-100",      # 數量總表（order_index=0）
            "DLX-101",      # 額外家具（字母順序在 DLX-100 和 DLX-102 之間）
            "DLX-101.1",    # 額外家具（DLX-101 的子項）
            "DLX-102",      # 數量總表（order_index=1）
            "FAB-001",      # 面料
            "FAB-002",      # 面料
        ]

    def test_empty_list(self, service):
        """測試空列表."""
        result = service._sort_items_by_priority([])
        assert result == []

    def test_only_qty_furniture(self, service):
        """測試只有數量總表家具的情況."""
        items = [
            self._create_item("A-002", category=1, qty_order_index=1),
            self._create_item("A-001", category=1, qty_order_index=0),
        ]

        result = service._sort_items_by_priority(items)

        assert [i.item_no for i in result] == ["A-001", "A-002"]

    def test_only_fabric(self, service):
        """測試只有面料的情況."""
        items = [
            self._create_item("FAB-002", category=5),
            self._create_item("FAB-001", category=5),
        ]

        result = service._sort_items_by_priority(items)

        assert [i.item_no for i in result] == ["FAB-001", "FAB-002"]

    def test_extra_furniture_inserted_after_parent(self, service):
        """測試額外家具插入到對應父項之後."""
        items = [
            self._create_item("DLX-101", category=1, qty_order_index=1),
            self._create_item("DLX-100", category=1, qty_order_index=0),
            self._create_item("DLX-100.2", category=1, qty_order_index=None),
            self._create_item("DLX-100.1", category=1, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        item_nos = [i.item_no for i in result]
        # DLX-100.1 和 DLX-100.2 應該緊跟在 DLX-100 之後
        assert item_nos == ["DLX-100", "DLX-100.1", "DLX-100.2", "DLX-101"]

    def test_extra_furniture_multiple_parents(self, service):
        """測試額外家具分別跟隨各自的父項."""
        items = [
            # 數量總表家具
            self._create_item("DLX-102", category=1, qty_order_index=2),
            self._create_item("DLX-100", category=1, qty_order_index=0),
            self._create_item("DLX-101", category=1, qty_order_index=1),
            # 額外家具（子項）
            self._create_item("DLX-100.1", category=1, qty_order_index=None),
            self._create_item("DLX-101.1", category=1, qty_order_index=None),
            self._create_item("DLX-100.2", category=1, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        item_nos = [i.item_no for i in result]
        # 每個子項應該跟在其父項之後
        assert item_nos == [
            "DLX-100", "DLX-100.1", "DLX-100.2",  # DLX-100 與其子項
            "DLX-101", "DLX-101.1",                # DLX-101 與其子項
            "DLX-102",                             # DLX-102（無子項）
        ]

    def test_extra_furniture_without_parent(self, service):
        """測試沒有對應父項的額外家具按字母順序插入."""
        items = [
            self._create_item("DLX-100", category=1, qty_order_index=0),
            self._create_item("DLX-101", category=1, qty_order_index=1),
            # 額外家具（沒有父項 ABC-100 在數量總表中）- 字母順序在 DLX 之前
            self._create_item("ABC-100.1", category=1, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        item_nos = [i.item_no for i in result]
        # ABC-100.1 字母順序在 DLX-100 之前，所以排在最前面
        assert item_nos == ["ABC-100.1", "DLX-100", "DLX-101"]

    def test_mixed_extra_with_and_without_parent(self, service):
        """測試有父項和沒有父項的額外家具混合情況."""
        items = [
            # 數量總表家具
            self._create_item("DLX-100", category=1, qty_order_index=0),
            self._create_item("DLX-101", category=1, qty_order_index=1),
            # 額外家具 - 有父項
            self._create_item("DLX-100.1", category=1, qty_order_index=None),
            # 額外家具 - 沒有父項，字母順序在 DLX 之前
            self._create_item("ABC-001", category=1, qty_order_index=None),
            # 面料
            self._create_item("FAB-001", category=5, qty_order_index=None),
        ]

        result = service._sort_items_by_priority(items)

        item_nos = [i.item_no for i in result]
        # ABC-001 字母順序在 DLX-100 之前，所以排在最前面
        assert item_nos == [
            "ABC-001",              # 額外家具（字母順序在 DLX 之前）
            "DLX-100", "DLX-100.1", # DLX-100 與其子項
            "DLX-101",              # DLX-101
            "FAB-001",              # 面料放最後
        ]

