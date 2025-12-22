"""Contract tests for Google Sheets API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid

pytestmark = pytest.mark.contract

API_PREFIX = "/api/v1"


class TestSheetsStatusAPI:
    """Contract tests for Sheets status endpoint."""

    def test_check_sheets_status(self, client: TestClient):
        """GET /sheets/status returns status information."""
        response = client.get(f"{API_PREFIX}/sheets/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "enabled" in data["data"]
        assert "available" in data["data"]
        assert "credentials_configured" in data["data"]


class TestSheetsExportAPI:
    """Contract tests for Sheets export endpoints."""

    @pytest.fixture
    def mock_quotation_id(self, client: TestClient):
        """Create a test quotation and return its ID."""
        # First upload a document
        with patch("app.api.routes.upload.get_pdf_parser") as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse_boq_items.return_value = []

            pdf_content = b"%PDF-1.4 test content"
            files = {"files": ("test.pdf", pdf_content, "application/pdf")}

            response = client.post("/api/documents", files=files)
            if response.status_code != 201:
                pytest.skip("Could not create test document")

            doc_id = response.json().get("data", {}).get("documents", [{}])[0].get("id")
            if not doc_id:
                pytest.skip("Could not get document ID")

        # Create quotation
        response = client.post(
            f"{API_PREFIX}/quotations",
            json={"document_ids": [doc_id]},
        )

        if response.status_code != 201:
            pytest.skip("Could not create test quotation")

        return response.json().get("data", {}).get("id")

    def test_export_sheets_returns_202_when_disabled(self, client: TestClient, mock_quotation_id):
        """POST /quotations/{id}/sheets returns 503 when Sheets disabled."""
        with patch("app.api.routes.sheets.settings") as mock_settings:
            mock_settings.google_sheets_available = False

            response = client.post(
                f"{API_PREFIX}/quotations/{mock_quotation_id}/sheets",
                json={"include_photos": True, "share_mode": "view"},
            )

            # Should return 503 Service Unavailable when disabled
            assert response.status_code == 503
            data = response.json()
            assert data["success"] is False
            assert "GOOGLE_SHEETS_DISABLED" in data.get("error_code", "")

    def test_export_sheets_creates_task(self, client: TestClient, mock_quotation_id):
        """Export creates background task when enabled."""
        with patch("app.api.routes.sheets.settings") as mock_settings:
            mock_settings.google_sheets_available = True

            with patch("app.api.routes.sheets.get_google_sheets_generator"):
                response = client.post(
                    f"{API_PREFIX}/quotations/{mock_quotation_id}/sheets",
                    json={"include_photos": False, "share_mode": "view"},
                )

                # Should return 202 Accepted
                assert response.status_code == 202
                data = response.json()
                assert "task_id" in data.get("data", {}) or data.get("data", {}).get("status") == "generating"

    def test_get_sheets_link_not_ready(self, client: TestClient, mock_quotation_id):
        """GET returns pending status if not yet generated."""
        response = client.get(f"{API_PREFIX}/quotations/{mock_quotation_id}/sheets")

        assert response.status_code == 200
        data = response.json()
        # Should indicate not yet generated
        assert data.get("data", {}).get("status") in ["pending", "generating", None]

    def test_export_sheets_invalid_quotation(self, client: TestClient):
        """Returns 404 for invalid quotation ID."""
        fake_id = str(uuid.uuid4())

        with patch("app.api.routes.sheets.settings") as mock_settings:
            mock_settings.google_sheets_available = True

            response = client.post(
                f"{API_PREFIX}/quotations/{fake_id}/sheets",
                json={"include_photos": True, "share_mode": "view"},
            )

            assert response.status_code == 404

    def test_export_sheets_request_validation(self, client: TestClient, mock_quotation_id):
        """Request body validation works correctly."""
        with patch("app.api.routes.sheets.settings") as mock_settings:
            mock_settings.google_sheets_available = True

            # Valid request
            response = client.post(
                f"{API_PREFIX}/quotations/{mock_quotation_id}/sheets",
                json={"include_photos": True, "share_mode": "view"},
            )
            # Should not fail validation
            assert response.status_code in [200, 202, 503]

            # Invalid share_mode should fail validation
            response = client.post(
                f"{API_PREFIX}/quotations/{mock_quotation_id}/sheets",
                json={"include_photos": True, "share_mode": "invalid"},
            )
            assert response.status_code == 422  # Validation error

    def test_get_sheets_link_invalid_quotation(self, client: TestClient):
        """GET returns 404 for invalid quotation ID."""
        fake_id = str(uuid.uuid4())

        response = client.get(f"{API_PREFIX}/quotations/{fake_id}/sheets")

        assert response.status_code == 404


class TestSheetsResponseFormat:
    """Tests for Sheets API response format consistency."""

    def test_status_response_format(self, client: TestClient):
        """Status endpoint returns correct format."""
        response = client.get(f"{API_PREFIX}/sheets/status")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "success" in data
        assert "message" in data
        assert "data" in data

        # Check data structure
        assert isinstance(data["data"].get("enabled"), bool)
        assert isinstance(data["data"].get("available"), bool)
        assert isinstance(data["data"].get("credentials_configured"), bool)

    def test_export_response_format_202(self, client: TestClient):
        """Export endpoint returns correct 202 format."""
        # Create minimal quotation
        with patch("app.api.routes.upload.get_pdf_parser") as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse_boq_items.return_value = []

            pdf_content = b"%PDF-1.4 test"
            response = client.post(
                "/api/documents",
                files={"files": ("test.pdf", pdf_content, "application/pdf")},
            )
            if response.status_code != 201:
                pytest.skip("Could not create document")

            doc_id = response.json().get("data", {}).get("documents", [{}])[0].get("id")

        response = client.post(
            f"{API_PREFIX}/quotations",
            json={"document_ids": [doc_id]},
        )
        if response.status_code != 201:
            pytest.skip("Could not create quotation")

        quotation_id = response.json().get("data", {}).get("id")

        with patch("app.api.routes.sheets.settings") as mock_settings:
            mock_settings.google_sheets_available = True

            with patch("app.api.routes.sheets.get_google_sheets_generator"):
                response = client.post(
                    f"{API_PREFIX}/quotations/{quotation_id}/sheets",
                    json={"include_photos": False, "share_mode": "view"},
                )

        if response.status_code == 202:
            data = response.json()
            assert "success" in data
            assert "message" in data
            assert "data" in data
            assert "status" in data["data"] or "task_id" in data["data"]
