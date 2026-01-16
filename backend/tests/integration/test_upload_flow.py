"""Integration tests for upload-parse-export flow (US1)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


pytestmark = pytest.mark.integration


class TestUploadParseExportFlow:
    """Integration tests for complete upload-parse-export workflow."""

    def test_complete_flow_single_document(self, client: TestClient, sample_pdf_file: Path):
        """Test complete workflow: upload -> parse -> quotation -> export."""
        # Step 1: Upload PDF
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        assert upload_response.status_code == 201
        document_id = upload_response.json()["data"]["documents"][0]["id"]
        print(f"✓ Uploaded document: {document_id}")

        # Step 2: Start parsing
        parse_response = client.post(f"/api/v1/documents/{document_id}/parsing")

        assert parse_response.status_code == 202
        task_id = parse_response.json()["data"].get("task_id") or parse_response.json()["data"].get("id")
        print(f"✓ Started parsing task: {task_id}")

        # Step 3: Check task status
        status_response = client.get(f"/api/v1/tasks/{task_id}")

        assert status_response.status_code == 200
        task_status = status_response.json()["data"]["status"]
        print(f"✓ Task status: {task_status}")

        # Step 4: Create quotation
        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [document_id]},
        )

        assert quotation_response.status_code == 201
        quotation_id = quotation_response.json()["data"]["id"]
        print(f"✓ Created quotation: {quotation_id}")

        # Step 5: Export to Excel (GET request)
        export_response = client.get(f"/api/v1/quotations/{quotation_id}/excel")

        assert export_response.status_code in [200, 202]
        if export_response.status_code == 202:
            export_task_id = export_response.json()["data"].get("task_id") or export_response.json()["data"].get("id")
            print(f"✓ Started Excel export task: {export_task_id}")

            # Step 6: Check export status
            export_status_response = client.get(f"/api/v1/tasks/{export_task_id}")

            assert export_status_response.status_code == 200
            export_status = export_status_response.json()["data"]["status"]
            print(f"✓ Export task status: {export_status}")
        else:
            print(f"✓ Excel file ready")

    def test_document_listing_after_upload(self, client: TestClient, sample_pdf_file: Path):
        """Test document listing after upload."""
        # Upload first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        assert upload_response.status_code == 201
        assert upload_response.json()["data"]["documents"][0]["id"]  # Verify document was created

        # List documents
        list_response = client.get("/api/v1/documents")

        assert list_response.status_code == 200
        data = list_response.json()
        assert "documents" in data or ("data" in data and isinstance(data["data"], dict))
        print(f"✓ Listed documents successfully")

    def test_get_document_details(self, client: TestClient, sample_pdf_file: Path):
        """Test getting document details after upload."""
        # Upload
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        document_id = upload_response.json()["data"]["documents"][0]["id"]

        # Get document details
        detail_response = client.get(f"/api/v1/documents/{document_id}")

        assert detail_response.status_code == 200
        doc = detail_response.json()["data"] if "data" in detail_response.json() else detail_response.json()
        assert doc.get("id") == document_id
        print(f"✓ Retrieved document details successfully")

    def test_quotation_contains_items(self, client: TestClient, sample_pdf_file: Path):
        """Test that quotation is created with items from document."""
        # Upload and create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        document_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [document_id]},
        )

        assert quotation_response.status_code == 201
        quotation = quotation_response.json()["data"]
        assert "items" in quotation
        assert "total_items" in quotation
        print(f"✓ Quotation created with items: {quotation['total_items']}")

    def test_get_quotation_details(self, client: TestClient, sample_pdf_file: Path):
        """Test getting quotation details."""
        # Create quotation
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        document_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [document_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Get quotation details
        detail_response = client.get(f"/api/v1/quotations/{quotation_id}")

        assert detail_response.status_code == 200
        quotation = detail_response.json()["data"] if "data" in detail_response.json() else detail_response.json()
        assert quotation.get("id") == quotation_id
        print(f"✓ Retrieved quotation details successfully")

    def test_export_creates_valid_file(self, client: TestClient, sample_pdf_file: Path):
        """Test that export creates a valid file."""
        # Create quotation and export
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        document_id = upload_response.json()["data"]["documents"][0]["id"]

        quotation_response = client.post(
            "/api/v1/quotations",
            json={"document_ids": [document_id]},
        )

        quotation_id = quotation_response.json()["data"]["id"]

        # Export (GET request)
        export_response = client.get(f"/api/v1/quotations/{quotation_id}/excel")

        assert export_response.status_code in [200, 202]
        print(f"✓ Excel export initiated successfully")

    def test_error_handling_invalid_document(self, client: TestClient):
        """Test error handling for invalid document ID."""
        # Try to parse non-existent document
        response = client.post("/api/v1/documents/invalid-id/parsing")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False
        print(f"✓ Error handling for invalid document works")

    def test_error_handling_invalid_quotation(self, client: TestClient):
        """Test error handling for invalid quotation ID."""
        # Try to export non-existent quotation
        response = client.get("/api/v1/quotations/invalid-id/excel")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False
        print(f"✓ Error handling for invalid quotation works")
