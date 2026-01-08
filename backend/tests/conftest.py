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


@pytest.fixture
def sample_processing_task():
    """Sample processing task for testing."""
    from app.models import ProcessingTask

    return ProcessingTask(
        task_type="parse_pdf",
        status="pending",
        message="等待處理",
        document_id="test-doc-id",
    )


# ============================================================================
# 跨表合併相關 fixtures (2025-12-23 新增)
# ============================================================================


@pytest.fixture
def sample_quantity_summary_doc_data():
    """Sample quantity summary document data for merge testing."""
    return {
        "filename": "Bay Tower Furniture - Overall Qty.pdf",
        "file_path": "/tmp/uploads/qty-summary.pdf",
        "file_size": 1024000,
        "document_type": "boq",
        "document_role": "quantity_summary",
        "upload_order": 0,
    }


@pytest.fixture
def sample_detail_spec_doc_data():
    """Sample detail spec document data for merge testing."""
    return {
        "filename": "Casegoods & Seatings.pdf",
        "file_path": "/tmp/uploads/detail-spec-1.pdf",
        "file_size": 2048000,
        "document_type": "boq",
        "document_role": "detail_spec",
        "upload_order": 1,
    }


@pytest.fixture
def sample_quantity_summary_items():
    """Sample quantity summary items for merge testing."""
    return [
        {"item_no_raw": "DLX-100", "item_no_normalized": "DLX-100", "total_qty": 239.0},
        {"item_no_raw": "DLX-101", "item_no_normalized": "DLX-101", "total_qty": 248.0},
        {"item_no_raw": "DLX.102", "item_no_normalized": "DLX-102", "total_qty": 150.0},
        {"item_no_raw": "STD 200", "item_no_normalized": "STD-200", "total_qty": 100.0},
    ]


@pytest.fixture
def sample_boq_items_for_merge():
    """Sample BOQ items for merge testing."""
    return [
        {
            "no": 1,
            "item_no": "DLX-100",
            "description": "King Bed",
            "dimension": "1930 x 2130 x 290 H",
            "qty": 100.0,  # Will be overridden by quantity summary
            "uom": "ea",
            "source_document_id": "detail-doc-1",
            "source_page": 1,
        },
        {
            "no": 2,
            "item_no": "DLX-101",
            "description": "Bedside Table",
            "dimension": "600 x 500 x 550 H",
            "qty": 50.0,  # Will be overridden by quantity summary
            "uom": "ea",
            "source_document_id": "detail-doc-1",
            "source_page": 2,
        },
        {
            "no": 3,
            "item_no": "NEW-001",  # Not in quantity summary
            "description": "New Item",
            "dimension": "300 x 300 x 300 H",
            "qty": 10.0,
            "uom": "ea",
            "source_document_id": "detail-doc-1",
            "source_page": 3,
        },
    ]


@pytest.fixture
def sample_merge_request_data():
    """Sample merge request data for API testing."""
    return {
        "document_ids": ["doc-qty-summary", "doc-detail-1", "doc-detail-2"],
        "title": "Bay Tower 報價單",
    }
