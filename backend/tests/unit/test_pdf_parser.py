"""Unit tests for pdf_parser service."""

import pytest
from pathlib import Path

from app.services.pdf_parser import PDFParserService


pytestmark = pytest.mark.unit


class TestPDFParserService:
    """Tests for PDF parser service."""

    def test_parser_initialization(self):
        """Test PDF parser service initialization."""
        # This test will verify the service can be imported and initialized
        # Implementation details depend on the actual service implementation
        pytest.skip("Service implementation pending")

    def test_parse_empty_pdf_fails(self, sample_pdf_file: Path):
        """Test parsing an empty PDF fails gracefully."""
        pytest.skip("Service implementation pending")

    def test_extract_text_from_pdf(self, sample_pdf_file: Path):
        """Test extracting text from PDF."""
        pytest.skip("Service implementation pending")

    def test_parse_boq_pdf_structure(self, sample_pdf_file: Path):
        """Test PDF parser returns correct BOQ structure."""
        pytest.skip("Service implementation pending")

    def test_parse_returns_items_list(self, sample_pdf_file: Path):
        """Test parser returns list of BOQ items."""
        pytest.skip("Service implementation pending")

    def test_parse_handles_corrupted_pdf(self, temp_dir: Path):
        """Test parser handles corrupted PDF gracefully."""
        # Create a corrupted PDF
        corrupted_pdf = temp_dir / "corrupted.pdf"
        corrupted_pdf.write_bytes(b"This is not a PDF")

        pytest.skip("Service implementation pending")

    def test_parse_handles_password_protected_pdf(self, temp_dir: Path):
        """Test parser handles password-protected PDF."""
        pytest.skip("Service implementation pending")

    def test_parse_respects_max_file_size(self, sample_pdf_file: Path):
        """Test parser respects file size limits."""
        pytest.skip("Service implementation pending")

    def test_gemini_integration(self, sample_pdf_file: Path):
        """Test Gemini API integration."""
        pytest.skip("Service implementation pending")


class TestImageExtractorUnit:
    """Unit tests specifically for image extraction."""

    def test_extract_images_returns_list(self, sample_pdf_file: Path):
        """Test image extraction returns list."""
        pytest.skip("Service implementation pending")

    def test_extract_images_metadata(self, sample_pdf_file: Path):
        """Test extracted images have correct metadata."""
        pytest.skip("Service implementation pending")

    def test_extract_images_with_format_conversion(self, sample_pdf_file: Path):
        """Test image extraction with format conversion."""
        pytest.skip("Service implementation pending")


class TestFindSpecificationPageContent:
    """Tests for _find_specification_page_content method.

    Ensures PROJECT is extracted from the specification page,
    not from index/cover pages.
    """

    @pytest.fixture
    def parser(self):
        """Create a PDFParserService instance for testing."""
        service = PDFParserService.__new__(PDFParserService)
        service.client = None
        service.model_name = "test-model"
        service._prompts_loaded = False
        service._skill = None
        return service

    def test_extracts_project_from_spec_page_with_form_feed_separator(self, parser):
        """Test PROJECT is extracted from spec page when separated by form feed."""
        pdf_text = (
            "INDEX PAGE\n"
            "PROJECT: WRONG_PROJECT_FROM_INDEX\n"
            "Item # | Room | Quantity\n"
            "DLX-100 | @Standard | 50\n"
            "\f"  # Form feed (page separator)
            "SPECIFICATION PAGE\n"
            "PROJECT: CORRECT_PROJECT_NAME\n"
            "ITEM NO.: DLX-100\n"
            "Description: King Bed\n"
        )

        result = parser._find_specification_page_content(pdf_text)

        assert "CORRECT_PROJECT_NAME" in result
        assert "WRONG_PROJECT_FROM_INDEX" not in result

    def test_extracts_project_from_spec_page_with_newline_separator(self, parser):
        """Test PROJECT is extracted from spec page when separated by triple newlines."""
        pdf_text = (
            "INDEX PAGE\n"
            "PROJECT: WRONG_PROJECT_FROM_INDEX\n"
            "Item # | Room | Quantity\n"
            "\n\n\n"  # Triple newline (page separator)
            "SPECIFICATION PAGE\n"
            "PROJECT: CORRECT_PROJECT_NAME\n"
            "ITEM NO.: DLX-100\n"
            "Description: King Bed\n"
        )

        result = parser._find_specification_page_content(pdf_text)

        assert "CORRECT_PROJECT_NAME" in result
        assert "WRONG_PROJECT_FROM_INDEX" not in result

    def test_extracts_project_within_same_page_block(self, parser):
        """Test PROJECT is correctly found within 800 chars before ITEM NO."""
        pdf_text = (
            "PROJECT: SOLAIRE BAY TOWER\n"
            "AREA: Standard\n"
            "ITEM NO.: DLX-100\n"
            "Description: King Bed\n"
        )

        result = parser._find_specification_page_content(pdf_text)

        assert "SOLAIRE BAY TOWER" in result
        assert "ITEM NO.: DLX-100" in result

    def test_handles_missing_project_gracefully(self, parser):
        """Test handles spec page without PROJECT field."""
        pdf_text = (
            "SPECIFICATION PAGE\n"
            "ITEM NO.: DLX-100\n"
            "Description: King Bed\n"
        )

        result = parser._find_specification_page_content(pdf_text)

        assert "ITEM NO.: DLX-100" in result

    def test_handles_no_spec_markers(self, parser):
        """Test fallback when no spec markers found."""
        pdf_text = "Some random content without ITEM NO markers."

        result = parser._find_specification_page_content(pdf_text)

        assert result == pdf_text

    def test_supports_alternate_item_no_formats(self, parser):
        """Test supports ITEM NO: (without dot) format."""
        pdf_text = (
            "PROJECT: TEST_PROJECT\n"
            "ITEM NO: ABC-001\n"
            "Description: Chair\n"
        )

        result = parser._find_specification_page_content(pdf_text)

        assert "TEST_PROJECT" in result
