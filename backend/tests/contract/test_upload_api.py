"""Contract tests for upload API endpoints (US1)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


pytestmark = pytest.mark.contract


class TestUploadEndpoint:
    """Contract tests for POST /api/upload endpoint."""

    def test_upload_single_pdf_success(self, client: TestClient, sample_pdf_file: Path):
        """Test successful single PDF upload."""
        with open(sample_pdf_file, "rb") as f:
            response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        assert response.status_code == 201
        data = response.json()
        assert data.get("success") is True
        assert "data" in data
        assert "documents" in data["data"]
        assert len(data["data"]["documents"]) == 1
        assert data["data"]["documents"][0].get("id") is not None
        assert data["data"]["documents"][0].get("filename") == sample_pdf_file.name
        assert data["data"]["documents"][0].get("parse_status") == "pending"

    def test_upload_multiple_pdfs_success(self, client: TestClient, sample_pdf_file: Path, temp_dir: Path):
        """Test successful multiple PDF upload."""
        # Create second test file
        second_file = temp_dir / "test2.pdf"
        second_file.write_bytes(sample_pdf_file.read_bytes())

        with open(sample_pdf_file, "rb") as f1, open(second_file, "rb") as f2:
            response = client.post(
                "/api/documents",
                files=[
                    ("files", ("test.pdf", f1, "application/pdf")),
                    ("files", ("test2.pdf", f2, "application/pdf")),
                ],
            )

        assert response.status_code == 201
        data = response.json()
        assert data.get("success") is True
        assert len(data["data"]["documents"]) == 2

    def test_upload_empty_file_fails(self, client: TestClient, temp_dir: Path):
        """Test upload of empty file fails."""
        empty_file = temp_dir / "empty.pdf"
        empty_file.write_bytes(b"")

        with open(empty_file, "rb") as f:
            response = client.post(
                "/api/documents",
                files={"files": ("empty.pdf", f, "application/pdf")},
            )

        assert response.status_code == 400
        data = response.json()
        assert data.get("success") is False
        assert "error_code" in data or "message" in data

    def test_upload_non_pdf_fails(self, client: TestClient, temp_dir: Path):
        """Test upload of non-PDF file fails."""
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("This is a text file")

        with open(txt_file, "rb") as f:
            response = client.post(
                "/api/documents",
                files={"files": ("test.txt", f, "text/plain")},
            )

        assert response.status_code == 400
        data = response.json()
        assert data.get("success") is False

    def test_upload_too_many_files_fails(self, client: TestClient, sample_pdf_file: Path, temp_dir: Path):
        """Test upload of more than 5 files fails."""
        # Create 6 test files
        files_to_upload = []
        for i in range(6):
            f = temp_dir / f"test{i}.pdf"
            f.write_bytes(sample_pdf_file.read_bytes())
            files_to_upload.append(open(f, "rb"))

        try:
            file_tuples = [
                ("files", (f"test{i}.pdf", files_to_upload[i], "application/pdf"))
                for i in range(6)
            ]
            response = client.post("/api/documents", files=file_tuples)

            assert response.status_code == 400
            data = response.json()
            assert data.get("success") is False
        finally:
            for f in files_to_upload:
                f.close()

    def test_upload_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test upload response has correct structure."""
        with open(sample_pdf_file, "rb") as f:
            response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        assert response.status_code == 201
        data = response.json()

        # Check response structure
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data

        # Check document structure
        doc = data["data"]["documents"][0]
        assert "id" in doc
        assert "filename" in doc
        assert "file_size" in doc
        assert "document_type" in doc
        assert "parse_status" in doc
        assert "uploaded_at" in doc


class TestDocumentListingEndpoint:
    """Contract tests for GET /api/documents endpoint (US2)."""

    def test_list_documents_empty(self, client: TestClient):
        """Test listing documents when none exist."""
        response = client.get("/api/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data or "data" in data
        assert "total" in data or (isinstance(data.get("data"), list) and len(data["data"]) == 0)

    def test_list_documents_after_upload(self, client: TestClient, sample_pdf_file: Path):
        """Test listing documents after upload."""
        # Upload a document
        with open(sample_pdf_file, "rb") as f:
            client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        # List documents
        response = client.get("/api/documents")

        assert response.status_code == 200
        data = response.json()
        # Response should contain documents list
        assert data.get("success") is True or "documents" in data or "data" in data


class TestDocumentDetailEndpoint:
    """Contract tests for GET /api/documents/{document_id} endpoint (US2)."""

    def test_get_document_not_found(self, client: TestClient):
        """Test getting non-existent document."""
        response = client.get("/api/documents/invalid-id")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_get_document_after_upload(self, client: TestClient, sample_pdf_file: Path):
        """Test getting document after upload."""
        # Upload a document
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/documents",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        # Get document
        response = client.get(f"/api/documents/{doc_id}")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        if "data" in data:
            assert data["data"].get("id") == doc_id
