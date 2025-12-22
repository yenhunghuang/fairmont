"""Pytest configuration and fixtures."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil
from fastapi.testclient import TestClient

from app.main import app
from app.store import InMemoryStore

# API version prefix
API_PREFIX = "/api/v1"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_store():
    """Create mock in-memory store."""
    return InMemoryStore(cache_ttl=60)


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_pdf_file(temp_dir: Path) -> Path:
    """Create a simple PDF file for testing."""
    # Create a minimal PDF file for testing
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000201 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
278
%%EOF
"""
    pdf_path = temp_dir / "test.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def sample_boq_item_data():
    """Sample BOQ item data for testing."""
    return {
        "no": 1,
        "item_no": "FUR-001",
        "description": "會議桌",
        "dimension": "1200x600x750",
        "qty": 5.0,
        "uom": "ea",
        "note": "黑色烤漆",
        "location": "會議室",
        "materials_specs": "密集板 + 木皮",
        "source_type": "boq",
        "source_document_id": "test-doc-id",
        "source_page": 1,
    }


@pytest.fixture
def sample_quotation_data():
    """Sample quotation data for testing."""
    return {
        "title": "RFQ-2025-001",
        "source_document_ids": ["test-doc-id"],
    }


@pytest.mark.asyncio
@pytest.fixture
async def sample_processing_task():
    """Sample processing task for testing."""
    from app.models import ProcessingTask

    return ProcessingTask(
        task_type="parse_pdf",
        status="pending",
        message="等待處理",
        document_id="test-doc-id",
    )
