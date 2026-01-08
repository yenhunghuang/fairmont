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

