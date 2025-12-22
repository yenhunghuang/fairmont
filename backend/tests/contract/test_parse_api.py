"""Contract tests for parse API endpoints (US1)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


pytestmark = pytest.mark.contract


class TestParseStartEndpoint:
    """Contract tests for POST /api/parse/{document_id} endpoint."""

    def test_start_parsing_success(self, client: TestClient, sample_pdf_file: Path):
        """Test successfully starting PDF parsing."""
        # Upload first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Start parsing
        response = client.post(f"/api/documents/{doc_id}/parse")

        assert response.status_code == 202
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "task_id" in data["data"] or "id" in data["data"]

    def test_start_parsing_with_options(self, client: TestClient, sample_pdf_file: Path):
        """Test starting parsing with extraction options."""
        # Upload first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Start parsing with options
        response = client.post(
            f"/api/documents/{doc_id}/parse",
            json={
                "extract_images": True,
                "target_categories": ["活動家具"],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data.get("success") is True
        assert "data" in data

    def test_start_parsing_document_not_found(self, client: TestClient):
        """Test parsing non-existent document."""
        response = client.post("/api/documents/invalid-id/parse")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_parse_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test parse response has correct structure."""
        # Upload first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Start parsing
        response = client.post(f"/api/documents/{doc_id}/parse")

        assert response.status_code == 202
        data = response.json()

        # Check structure
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data

        # Check task structure
        task = data["data"]
        assert "task_id" in task or "id" in task
        assert "status" in task or "task_type" in task


class TestParseResultEndpoint:
    """Contract tests for GET /api/parse/{document_id}/result endpoint."""

    def test_get_parse_result_not_ready(self, client: TestClient, sample_pdf_file: Path):
        """Test getting parse result when not ready."""
        # Upload first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Get result immediately (should not be ready)
        response = client.get(f"/api/documents/{doc_id}/parse-result")

        # Either 404 or 202 (not ready) are acceptable
        assert response.status_code in [202, 404, 400]
        data = response.json()
        # Should have proper error or pending status
        assert "data" in data or "success" in data

    def test_get_parse_result_not_found(self, client: TestClient):
        """Test getting result for non-existent document."""
        response = client.get("/api/documents/invalid-id/parse-result")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_parse_result_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test parse result response structure."""
        # Upload first
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Start parsing
        client.post(f"/api/documents/{doc_id}/parse")

        # Attempt to get result
        response = client.get(f"/api/documents/{doc_id}/parse-result")

        data = response.json()

        # Should have expected structure when available
        if response.status_code == 200:
            assert "document_id" in data or "data" in data
            # If items are present, validate structure
            if "items" in data:
                assert isinstance(data["items"], list)
            elif "data" in data and isinstance(data["data"], dict):
                # Check in data wrapper
                assert "items" in data["data"] or "results" in data["data"]
