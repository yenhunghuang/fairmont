"""單元測試：驗證 SSE 格式化正確性.

確保 format_result_event 正確處理包含 DLX-106.1 等項目的數據。
"""

import json
from app.utils.sse import format_sse_event, format_result_event


class TestSSEFormat:
    """測試 SSE 格式化."""

    def test_format_result_event_preserves_all_items(self):
        """測試 format_result_event 保留所有項目."""
        items = [
            {"no": 1, "item_no": "DLX-100", "description": "Item 1"},
            {"no": 2, "item_no": "DLX-106.1", "description": "Item with decimal"},
            {"no": 3, "item_no": "DLX-106.2", "description": "Another with decimal"},
            {"no": 4, "item_no": "DLX-200", "description": "Item 4"},
        ]

        result = format_result_event(
            project_name="Test Project",
            items=items,
            statistics={"total_items": 4},
        )

        # 驗證 SSE 格式
        assert result.startswith("event: result\n")
        assert "data: " in result
        assert result.endswith("\n\n")

        # 提取 JSON 數據
        data_line = [line for line in result.split("\n") if line.startswith("data: ")][0]
        json_str = data_line[6:]  # Remove "data: " prefix
        data = json.loads(json_str)

        # 驗證所有項目都存在
        assert len(data["items"]) == 4
        item_nos = [item["item_no"] for item in data["items"]]
        assert "DLX-106.1" in item_nos, "DLX-106.1 should be in SSE output"
        assert "DLX-106.2" in item_nos, "DLX-106.2 should be in SSE output"

    def test_sse_format_with_large_data(self):
        """測試大量數據的 SSE 格式化."""
        # 建立 100 個項目
        items = [
            {"no": i, "item_no": f"DLX-{i:03d}", "description": f"Item {i}"}
            for i in range(1, 101)
        ]

        result = format_result_event(
            project_name="Large Project",
            items=items,
            statistics={"total_items": 100},
        )

        # 提取並驗證 JSON
        data_line = [line for line in result.split("\n") if line.startswith("data: ")][0]
        json_str = data_line[6:]
        data = json.loads(json_str)

        assert len(data["items"]) == 100

    def test_sse_format_with_special_characters(self):
        """測試包含特殊字符的數據."""
        items = [
            {"no": 1, "item_no": "DLX-106.1", "description": "帶有中文的描述"},
            {"no": 2, "item_no": "STD-200", "description": "Has \"quotes\" and 'apostrophes'"},
            {"no": 3, "item_no": "ABC-300", "description": "Line\nbreak\ttab"},
        ]

        result = format_result_event(
            project_name="Test",
            items=items,
            statistics={},
        )

        # 提取並驗證 JSON
        data_line = [line for line in result.split("\n") if line.startswith("data: ")][0]
        json_str = data_line[6:]
        data = json.loads(json_str)

        assert len(data["items"]) == 3
        assert data["items"][0]["description"] == "帶有中文的描述"

    def test_sse_event_format_correctness(self):
        """測試 SSE 事件格式符合規範."""
        data = {"test": "value", "nested": {"key": "val"}}
        result = format_sse_event("test_event", data)

        lines = result.split("\n")
        assert lines[0] == "event: test_event"
        assert lines[1].startswith("data: ")
        assert lines[2] == ""  # 空行結尾
        # 最後有一個換行符
        assert result.endswith("\n\n")

    def test_json_dumps_in_sse_is_single_line(self):
        """測試 JSON 在 SSE 中是單行的（不會被換行符打斷）."""
        items = [
            {"no": 1, "item_no": "DLX-106.1"},
            {"no": 2, "item_no": "DLX-106.2"},
        ]

        result = format_result_event(
            project_name="Test",
            items=items,
            statistics={},
        )

        # 計算 data: 行的數量，應該只有 1 行
        data_lines = [line for line in result.split("\n") if line.startswith("data: ")]
        assert len(data_lines) == 1, "JSON should be on a single data: line"
