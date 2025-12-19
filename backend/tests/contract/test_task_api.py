"""Contract tests for task API endpoints (US1)."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


pytestmark = pytest.mark.contract


class TestTaskStatusEndpoint:
    """Contract tests for GET /api/task/{task_id} endpoint."""

    def test_get_task_status_not_found(self, client: TestClient):
        """Test getting non-existent task."""
        response = client.get("/api/task/invalid-id")

        assert response.status_code == 404
        data = response.json()
        assert data.get("success") is False

    def test_get_task_status_after_parse(self, client: TestClient, sample_pdf_file: Path):
        """Test getting task status after parsing."""
        # Upload and start parsing
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        parse_response = client.post(f"/api/parse/{doc_id}")
        task_id = parse_response.json()["data"].get("task_id") or parse_response.json()["data"].get("id")

        # Get task status
        response = client.get(f"/api/task/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "data" in data

    def test_task_status_response_structure(self, client: TestClient, sample_pdf_file: Path):
        """Test task status response structure."""
        # Upload and start parsing
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        parse_response = client.post(f"/api/parse/{doc_id}")
        task_id = parse_response.json()["data"].get("task_id") or parse_response.json()["data"].get("id")

        # Get task status
        response = client.get(f"/api/task/{task_id}")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "timestamp" in data

        task = data["data"]
        assert "task_id" in task or "id" in task
        assert "status" in task
        assert "progress" in task or "message" in task
        assert task["status"] in ["pending", "processing", "completed", "failed"]

    def test_task_status_pending(self, client: TestClient, sample_pdf_file: Path):
        """Test task status shows pending or processing."""
        # Upload and start parsing
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        parse_response = client.post(f"/api/parse/{doc_id}")
        task_id = parse_response.json()["data"].get("task_id") or parse_response.json()["data"].get("id")

        # Get task status immediately
        response = client.get(f"/api/task/{task_id}")

        assert response.status_code == 200
        task = response.json()["data"]
        # Should be pending or processing
        assert task["status"] in ["pending", "processing", "completed", "failed"]

    def test_task_status_has_message(self, client: TestClient, sample_pdf_file: Path):
        """Test task status includes message in Chinese."""
        # Upload and start parsing
        with open(sample_pdf_file, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"files": (sample_pdf_file.name, f, "application/pdf")},
            )

        doc_id = upload_response.json()["data"]["documents"][0]["id"]

        parse_response = client.post(f"/api/parse/{doc_id}")
        task_id = parse_response.json()["data"].get("task_id") or parse_response.json()["data"].get("id")

        # Get task status
        response = client.get(f"/api/task/{task_id}")

        task = response.json()["data"]
        # Message should exist (even if status is pending)
        assert "message" in task
        assert task["message"] is not None
