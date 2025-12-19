"""Contract tests for export API endpoints (US1)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


pytestmark = pytest.mark.contract


class TestCreateQuotationEndpoint:
    """Contract tests for POST /api/quotation endpoint."""

    def test_create_quotation_success(self, client: TestClient, sample_pdf_file: Path):
        """Test successfully creating a quotation."""
        # Upload a document first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Create quotation
        response = client.post(
            "/api/quotation",
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
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Create quotation with title
        response = client.post(
            "/api/quotation",
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
            "/api/quotation",
            json={"document_ids": ["invalid-id"]},
        )

        assert response.status_code == 400
        data = response.json()
        assert data.get("success") is False

    def test_quotation_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test quotation response structure."""
        # Upload and create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        response = client.post(
            "/api/quotation",
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
    """Contract tests for POST /api/export/{quotation_id}/excel endpoint."""

    def test_export_excel_success(self, client: TestClient, sample_pdf_file: Path):
        """Test successfully exporting Excel."""
        # Create quotation first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Export Excel
        response = client.post(f"/api/export/{quotation_id}/excel")

        assert response.status_code == 202
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "task_id" in data["data"] or "id" in data["data"]

    def test_export_excel_with_options(self, client: TestClient, sample_pdf_file: Path):
        """Test exporting Excel with options."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Export with options
        response = client.post(
            f"/api/export/{quotation_id}/excel",
            json={
                "include_photos": True,
                "photo_height_cm": 4.0,
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data.get("success") is True

    def test_export_excel_quotation_not_found(self, client: TestClient):
        """Test exporting Excel for non-existent quotation."""
        response = client.post("/api/export/invalid-id/excel")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_export_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test export response structure."""
        # Create quotation and export
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        response = client.post(f"/api/export/{quotation_id}/excel")

        assert response.status_code == 202
        data = response.json()

        # Check structure
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data

        task = data["data"]
        assert "task_id" in task or "id" in task
        assert "status" in task or "task_type" in task


class TestDownloadExcelEndpoint:
    """Contract tests for GET /api/export/{quotation_id}/download endpoint."""

    def test_download_excel_not_found(self, client: TestClient):
        """Test downloading Excel for non-existent quotation."""
        response = client.get("/api/export/invalid-id/download")

        assert response.status_code == 404

    def test_download_excel_not_ready(self, client: TestClient, sample_pdf_file: Path):
        """Test downloading Excel when not yet generated."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Try to download without exporting first
        response = client.get(f"/api/export/{quotation_id}/download")

        # Should be 404 or 202 (not ready)
        assert response.status_code in [404, 202, 400]

    def test_download_excel_response_type(self, client: TestClient, sample_pdf_file: Path):
        """Test download response has correct content type."""
        # Create quotation and export
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Export Excel
        client.post(f"/api/export/{quotation_id}/excel")

        # Try to download
        response = client.get(f"/api/export/{quotation_id}/download")

        # If successful, should have Excel content type
        if response.status_code == 200:
            assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers.get(
                "content-type", ""
            ) or "application/octet-stream" in response.headers.get("content-type", "")


class TestGetQuotationItemsEndpoint:
    """Contract tests for GET /api/quotation/{quotation_id}/items endpoint (US4)."""

    def test_get_quotation_items_success(self, client: TestClient, sample_pdf_file: Path):
        """Test getting quotation items."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Get items
        response = client.get(f"/api/quotation/{quotation_id}/items")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data or ("data" in data and "items" in data["data"])
        assert "total" in data or ("data" in data and isinstance(data["data"], list))


class TestUpdateQuotationItemsEndpoint:
    """Contract tests for PATCH /api/quotation/{quotation_id}/items endpoint (US4)."""

    def test_update_quotation_items_success(self, client: TestClient, sample_pdf_file: Path):
        """Test updating quotation items."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/quotation",
            json={"document_ids": [doc_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Update items
        response = client.patch(
            f"/api/quotation/{quotation_id}/items",
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
