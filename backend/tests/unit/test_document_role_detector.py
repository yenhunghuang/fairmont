"""Unit tests for DocumentRoleDetectorService.

測試 PDF 文件角色偵測服務的關鍵字識別功能。
"""

import pytest

from app.services.document_role_detector import (
    DocumentRoleDetectorService,
    get_document_role_detector_service,
)


class TestDocumentRoleDetectorService:
    """DocumentRoleDetectorService 單元測試."""

    @pytest.fixture
    def service(self) -> DocumentRoleDetectorService:
        """建立測試用服務實例."""
        return DocumentRoleDetectorService()

    # ============================================================================
    # detect_role() 方法測試 - 數量總表偵測
    # ============================================================================

    class TestDetectQuantitySummary:
        """數量總表偵測測試."""

        @pytest.fixture
        def service(self) -> DocumentRoleDetectorService:
            """建立測試用服務實例."""
            return DocumentRoleDetectorService()

        def test_detect_qty_keyword(self, service: DocumentRoleDetectorService):
            """測試 qty 關鍵字."""
            role, method = service.detect_role("Bay Tower - Overall Qty.pdf")
            assert role == "quantity_summary"
            assert method == "filename"

        def test_detect_qty_keyword_uppercase(
            self, service: DocumentRoleDetectorService
        ):
            """測試大寫 QTY 關鍵字."""
            role, method = service.detect_role("Project_QTY_Summary.pdf")
            assert role == "quantity_summary"

        def test_detect_overall_keyword(self, service: DocumentRoleDetectorService):
            """測試 overall 關鍵字."""
            role, method = service.detect_role("Overall Summary.pdf")
            assert role == "quantity_summary"

        def test_detect_summary_keyword(self, service: DocumentRoleDetectorService):
            """測試 summary 關鍵字."""
            role, method = service.detect_role("Furniture Summary.pdf")
            assert role == "quantity_summary"

        def test_detect_chinese_qty_keyword(self, service: DocumentRoleDetectorService):
            """測試中文數量關鍵字."""
            role, method = service.detect_role("家具數量總表.pdf")
            assert role == "quantity_summary"

        def test_detect_chinese_total_keyword(
            self, service: DocumentRoleDetectorService
        ):
            """測試中文總量關鍵字."""
            role, method = service.detect_role("總量清單.pdf")
            assert role == "quantity_summary"

        def test_detect_quantity_keyword(self, service: DocumentRoleDetectorService):
            """測試 quantity 關鍵字."""
            role, method = service.detect_role("Quantity Schedule.pdf")
            assert role == "quantity_summary"

        def test_detect_quantities_keyword(self, service: DocumentRoleDetectorService):
            """測試 quantities 關鍵字."""
            role, method = service.detect_role("All Quantities.pdf")
            assert role == "quantity_summary"

    # ============================================================================
    # detect_role() 方法測試 - 平面圖偵測
    # ============================================================================

    class TestDetectFloorPlan:
        """平面圖偵測測試."""

        @pytest.fixture
        def service(self) -> DocumentRoleDetectorService:
            """建立測試用服務實例."""
            return DocumentRoleDetectorService()

        def test_detect_floor_keyword(self, service: DocumentRoleDetectorService):
            """測試 floor 關鍵字."""
            role, method = service.detect_role("Floor Level 1.pdf")
            assert role == "floor_plan"

        def test_detect_plan_keyword(self, service: DocumentRoleDetectorService):
            """測試 plan 關鍵字."""
            role, method = service.detect_role("Building Plan.pdf")
            assert role == "floor_plan"

        def test_detect_floor_plan_combined(self, service: DocumentRoleDetectorService):
            """測試 floor plan 組合關鍵字."""
            role, method = service.detect_role("Floor Plan Level 2.pdf")
            assert role == "floor_plan"

        def test_detect_layout_keyword(self, service: DocumentRoleDetectorService):
            """測試 layout 關鍵字."""
            role, method = service.detect_role("Room Layout.pdf")
            assert role == "floor_plan"

        def test_detect_chinese_floor_plan(self, service: DocumentRoleDetectorService):
            """測試中文平面圖關鍵字."""
            role, method = service.detect_role("一樓平面圖.pdf")
            assert role == "floor_plan"

        def test_detect_chinese_layout(self, service: DocumentRoleDetectorService):
            """測試中文配置圖關鍵字."""
            role, method = service.detect_role("家具配置圖.pdf")
            assert role == "floor_plan"

    # ============================================================================
    # detect_role() 方法測試 - 明細規格表偵測
    # ============================================================================

    class TestDetectDetailSpec:
        """明細規格表偵測測試."""

        @pytest.fixture
        def service(self) -> DocumentRoleDetectorService:
            """建立測試用服務實例."""
            return DocumentRoleDetectorService()

        def test_detect_casegoods(self, service: DocumentRoleDetectorService):
            """測試 Casegoods 檔案."""
            role, method = service.detect_role("Casegoods & Seatings.pdf")
            assert role == "detail_spec"
            assert method == "filename"

        def test_detect_fabric(self, service: DocumentRoleDetectorService):
            """測試 Fabric 檔案."""
            role, method = service.detect_role("Fabric & Leather.pdf")
            assert role == "detail_spec"

        def test_detect_furniture_spec(self, service: DocumentRoleDetectorService):
            """測試 Furniture spec 檔案."""
            role, method = service.detect_role("Furniture Specifications.pdf")
            assert role == "detail_spec"

        def test_detect_generic_boq(self, service: DocumentRoleDetectorService):
            """測試一般 BOQ 檔案."""
            role, method = service.detect_role("BOQ_Project_2025.pdf")
            assert role == "detail_spec"

        def test_detect_item_list(self, service: DocumentRoleDetectorService):
            """測試項目清單檔案."""
            role, method = service.detect_role("Item List.pdf")
            assert role == "detail_spec"

    # ============================================================================
    # detect_role() 方法測試 - 邊界情況
    # ============================================================================

    class TestDetectEdgeCases:
        """邊界情況測試."""

        @pytest.fixture
        def service(self) -> DocumentRoleDetectorService:
            """建立測試用服務實例."""
            return DocumentRoleDetectorService()

        def test_empty_filename(self, service: DocumentRoleDetectorService):
            """測試空檔名."""
            role, method = service.detect_role("")
            assert role == "unknown"
            assert method == "filename"

        def test_none_like_filename(self, service: DocumentRoleDetectorService):
            """測試 None 類型檔名."""
            # 假設空字串處理
            role, method = service.detect_role("")
            assert role == "unknown"

        def test_mixed_keywords(self, service: DocumentRoleDetectorService):
            """測試混合關鍵字（數量總表優先）."""
            # 如果同時包含數量總表和平面圖關鍵字，數量總表優先
            role, method = service.detect_role("Floor Qty Summary.pdf")
            assert role == "quantity_summary"

        def test_case_insensitive(self, service: DocumentRoleDetectorService):
            """測試大小寫不敏感."""
            role1, _ = service.detect_role("QTY.PDF")
            role2, _ = service.detect_role("qty.pdf")
            role3, _ = service.detect_role("Qty.PDF")
            assert role1 == role2 == role3 == "quantity_summary"

    # ============================================================================
    # 輔助方法測試
    # ============================================================================

    class TestHelperMethods:
        """輔助方法測試."""

        @pytest.fixture
        def service(self) -> DocumentRoleDetectorService:
            """建立測試用服務實例."""
            return DocumentRoleDetectorService()

        def test_is_quantity_summary(self, service: DocumentRoleDetectorService):
            """測試 is_quantity_summary 方法."""
            assert service.is_quantity_summary("Overall Qty.pdf") is True
            assert service.is_quantity_summary("Casegoods.pdf") is False

        def test_is_detail_spec(self, service: DocumentRoleDetectorService):
            """測試 is_detail_spec 方法."""
            assert service.is_detail_spec("Casegoods.pdf") is True
            assert service.is_detail_spec("Overall Qty.pdf") is False

        def test_is_floor_plan(self, service: DocumentRoleDetectorService):
            """測試 is_floor_plan 方法."""
            assert service.is_floor_plan("Floor Plan.pdf") is True
            assert service.is_floor_plan("Casegoods.pdf") is False

        def test_get_role_display_name(self, service: DocumentRoleDetectorService):
            """測試中文顯示名稱."""
            assert service.get_role_display_name("quantity_summary") == "數量總表"
            assert service.get_role_display_name("detail_spec") == "明細規格表"
            assert service.get_role_display_name("floor_plan") == "平面圖"
            assert service.get_role_display_name("unknown") == "未知"

    # ============================================================================
    # 單例模式測試
    # ============================================================================

    class TestSingleton:
        """單例模式測試."""

        def test_singleton_instance(self):
            """測試單例模式返回相同實例."""
            service1 = DocumentRoleDetectorService()
            service2 = DocumentRoleDetectorService()
            assert service1 is service2

        def test_factory_function(self):
            """測試工廠函式返回單例."""
            service1 = get_document_role_detector_service()
            service2 = get_document_role_detector_service()
            assert service1 is service2

        def test_factory_same_as_direct_instantiation(self):
            """測試工廠函式與直接實例化返回相同實例."""
            service1 = DocumentRoleDetectorService()
            service2 = get_document_role_detector_service()
            assert service1 is service2
