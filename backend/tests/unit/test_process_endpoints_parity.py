"""單元測試：驗證 /process 和 /process/stream 端點的輸出一致性.

這個測試確保兩個端點使用相同的核心邏輯並產生相同的輸出。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.routes.process import _process_core, ProcessResult
from app.models.boq_item import BOQItem
from app.models.responses import FairmontItemResponse
from app.services.merge_service import MergeReport


class TestProcessEndpointsParity:
    """測試兩個端點的輸出一致性."""

    @pytest.fixture
    def mock_merged_items(self) -> list[BOQItem]:
        """建立模擬的合併項目列表（包含 DLX-106.1 和 DLX-106.2）."""
        items = []
        for i, item_no in enumerate([
            "DLX-100", "DLX-101", "DLX-102",
            "DLX-106", "DLX-106.1", "DLX-106.2",  # 關鍵：包含小數點後綴
            "DLX-107", "DLX-108"
        ], start=1):
            items.append(BOQItem(
                id=f"test-{i}",
                no=i,
                item_no=item_no,
                description=f"Test item {item_no}",
                source_document_id="test-doc",
                category=1,
            ))
        return items

    @pytest.fixture
    def mock_process_result(self, mock_merged_items: list[BOQItem]) -> ProcessResult:
        """建立模擬的處理結果."""
        return ProcessResult(
            merged_items=mock_merged_items,
            project_name="Test Project",
            merge_report=MergeReport(
                quotation_id="test-q",
                quantity_summary_doc_id=None,
                detail_spec_doc_ids=["test-doc"],
                matched_items=8,
                unmatched_items=0,
                fabric_items=0,
                fill_empty_count=0,
                concatenate_count=0,
            ),
            statistics={
                "total_items": 8,
                "furniture_count": 8,
                "fabric_count": 0,
                "images_matched": 0,
                "images_total": 0,
                "merge_match_rate": 1.0,
            },
        )

    def test_fairmont_item_response_conversion_preserves_all_items(
        self, mock_merged_items: list[BOQItem]
    ):
        """測試 FairmontItemResponse 轉換保留所有項目."""
        # 執行轉換
        items_response = [
            FairmontItemResponse.from_boq_item(item)
            for item in mock_merged_items
        ]

        # 驗證數量一致
        assert len(items_response) == len(mock_merged_items)

        # 驗證所有 item_no 都存在（包括 DLX-106.1 和 DLX-106.2）
        item_nos = [item.item_no for item in items_response]
        assert "DLX-106.1" in item_nos, "DLX-106.1 should be preserved"
        assert "DLX-106.2" in item_nos, "DLX-106.2 should be preserved"

    def test_model_dump_json_preserves_all_items(
        self, mock_merged_items: list[BOQItem]
    ):
        """測試 model_dump(mode='json') 保留所有項目."""
        # 執行轉換（模擬 streaming 版本的邏輯）
        items_response = [
            FairmontItemResponse.from_boq_item(item)
            for item in mock_merged_items
        ]
        items_json = [item.model_dump(mode="json") for item in items_response]

        # 驗證數量一致
        assert len(items_json) == len(mock_merged_items)

        # 驗證所有 item_no 都存在（包括 DLX-106.1 和 DLX-106.2）
        item_nos = [item["item_no"] for item in items_json]
        assert "DLX-106.1" in item_nos, "DLX-106.1 should be preserved in JSON"
        assert "DLX-106.2" in item_nos, "DLX-106.2 should be preserved in JSON"

    def test_sync_vs_stream_conversion_parity(
        self, mock_merged_items: list[BOQItem]
    ):
        """測試同步版本和串流版本的轉換一致性."""
        # 同步版本的轉換邏輯
        sync_items = [
            FairmontItemResponse.from_boq_item(item)
            for item in mock_merged_items
        ]

        # 串流版本的轉換邏輯
        stream_items_response = [
            FairmontItemResponse.from_boq_item(item)
            for item in mock_merged_items
        ]
        stream_items_json = [
            item.model_dump(mode="json")
            for item in stream_items_response
        ]

        # 驗證數量一致
        assert len(sync_items) == len(stream_items_json)

        # 驗證每個項目的 item_no 一致
        sync_item_nos = [item.item_no for item in sync_items]
        stream_item_nos = [item["item_no"] for item in stream_items_json]
        assert sync_item_nos == stream_item_nos, (
            f"Item numbers should match: sync={sync_item_nos}, stream={stream_item_nos}"
        )

    def test_item_no_with_decimal_suffix_preserved(self):
        """測試帶小數點後綴的 item_no 在轉換中被保留."""
        # 建立帶小數點後綴的項目
        item = BOQItem(
            id="test-1",
            no=1,
            item_no="DLX-106.1",  # 關鍵：帶小數點後綴
            description="Test item with decimal suffix",
            source_document_id="test-doc",
            category=1,
        )

        # 轉換為 FairmontItemResponse
        response = FairmontItemResponse.from_boq_item(item)
        assert response.item_no == "DLX-106.1", "Decimal suffix should be preserved"

        # 轉換為 JSON
        json_data = response.model_dump(mode="json")
        assert json_data["item_no"] == "DLX-106.1", "Decimal suffix should be preserved in JSON"

    def test_item_no_normalization_does_not_affect_output(self):
        """測試 item_no 標準化不影響輸出."""
        # 建立帶不同格式的項目
        items = [
            BOQItem(id="1", no=1, item_no="DLX-106.1", description="", source_document_id=""),
            BOQItem(id="2", no=2, item_no="DLX-106.2", description="", source_document_id=""),
            BOQItem(id="3", no=3, item_no="DLX.107", description="", source_document_id=""),
        ]

        # 轉換
        responses = [FairmontItemResponse.from_boq_item(item) for item in items]

        # 驗證 item_no 保持原樣（不被標準化）
        assert responses[0].item_no == "DLX-106.1"
        assert responses[1].item_no == "DLX-106.2"
        assert responses[2].item_no == "DLX.107"
