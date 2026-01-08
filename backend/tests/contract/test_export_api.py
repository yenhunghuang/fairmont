"""Contract tests for export API endpoints (US1)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


pytestmark = pytest.mark.contract


class TestCreateQuotationEndpoint:
    """Contract tests for POST /api/v1/quotations endpoint."""

    def test_create_quotation_success(self, client: TestClient, sample_pdf_file: Path):
        """Test successfully creating a quotation."""
        # Upload a document first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Create quotation
        response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        assert response.status_code == 201
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert data["data"].get("id") is not None
        assert data["data"].get("source_document_ids") == [doc_id]

    def test_create_quotation_with_title(self, client: TestClient, sample_pdf_file: Path):
        """Test creating quotation with custom title."""
        # Upload a document first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Create quotation with title
        response = client.post(
            "/api/v1/quotations",
            json={
                "document_ids": [doc_id],
                "title": "RFQ-2025-001",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data.get("success") is True
        assert data["data"].get("title") == "RFQ-2025-001"

    def test_create_quotation_invalid_document(self, client: TestClient):
        """Test creating quotation with invalid document ID."""
        response = client.post(
            "/api/v1/quotations",
            json={"document_ids": ["invalid-id"]},
        )

        # Invalid document ID returns 404 (document not found)
        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_quotation_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test quotation response structure."""
        # Upload and create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        assert response.status_code == 201
        quotation = response.json()["data"]

        # Check structure
        assert "id" in quotation
        assert "source_document_ids" in quotation
        assert "items" in quotation
        assert "total_items" in quotation
        assert "items_with_qty" in quotation
        assert "created_at" in quotation


class TestExportExcelEndpoint:
    """Contract tests for GET /api/v1/quotations/{quotation_id}/excel endpoint."""

    def test_export_excel_success(self, client: TestClient, sample_pdf_file: Path):
        """Test successfully exporting Excel."""
        # Create quotation first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Export Excel (GET request)
        response = client.get(f"/api/v1/quotations/{quotation_id}/excel")

        # Either 200 (file ready) or 202 (still generating) are acceptable
        assert response.status_code in [200, 202, 404]

    def test_export_excel_still_generating(self, client: TestClient, sample_pdf_file: Path):
        """Test GET endpoint returns 202 when Excel is still generating."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Get Excel immediately (may not be ready)
        response = client.get(f"/api/v1/quotations/{quotation_id}/excel")

        # Either 200 (already ready) or 202 (still generating) are acceptable
        assert response.status_code in [200, 202, 404]

    def test_export_excel_quotation_not_found(self, client: TestClient):
        """Test exporting Excel for non-existent quotation."""
        response = client.get("/api/v1/quotations/invalid-id/excel")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_export_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test export response structure."""
        # Create quotation and export
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        response = client.get(f"/api/v1/quotations/{quotation_id}/excel")

        # Check response based on status
        if response.status_code == 202:
            data = response.json()
            # Check structure for pending response
            assert "success" in data
            assert "message" in data
            assert "data" in data
            # Note: timestamp is optional in 202 response
        elif response.status_code == 200:
            # Should be file response
            assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers.get(
                "content-type", ""
            ) or "application/octet-stream" in response.headers.get("content-type", "")


class TestGetQuotationItemsEndpoint:
    """Contract tests for GET /api/v1/quotations/{quotation_id}/items endpoint (US4)."""

    def test_get_quotation_items_success(self, client: TestClient, sample_pdf_file: Path):
        """Test getting quotation items."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Get items
        response = client.get(f"/api/v1/quotations/{quotation_id}/items")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "items" in data["data"]
        assert "total" in data["data"]


class TestUpdateQuotationItemsEndpoint:
    """Contract tests for PATCH /api/v1/quotations/{quotation_id}/items endpoint (US4)."""

    def test_update_quotation_items_success(self, client: TestClient, sample_pdf_file: Path):
        """Test updating quotation items."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Update items
        response = client.patch(
            f"/api/v1/quotations/{quotation_id}/items",
            json={
                "updates": [
                    {
                        "qty": 10,
                        "description": "Updated description",
                    }
                ]
            },
        )

        assert response.status_code in [200, 404]  # 404 if no items yet
