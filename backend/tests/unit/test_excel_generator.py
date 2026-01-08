"""Unit tests for excel_generator service."""

import pytest
from pathlib import Path


pytestmark = pytest.mark.unit


class TestExcelGeneratorService:
    """Tests for Excel generator service."""

    def test_generator_initialization(self):
        """Test Excel generator service initialization."""
        pytest.skip("Service implementation pending")

    def test_create_excel_from_quotation(self, sample_boq_item_data, temp_dir: Path):
        """Test creating Excel file from quotation."""
        pytest.skip("Service implementation pending")

    def test_excel_has_correct_columns(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel file has all 10 required columns."""
        # Columns: NO., Item No., Description, Photo, Dimension, Qty, UOM, Note, Location, Materials
        pytest.skip("Service implementation pending")

    def test_excel_includes_item_data(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel includes correct item data."""
        pytest.skip("Service implementation pending")

    def test_excel_embeds_photos(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel embeds photos correctly."""
        pytest.skip("Service implementation pending")

    def test_excel_photo_sizing(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel photo sizing is correct."""
        # Default: 3cm height
        pytest.skip("Service implementation pending")

    def test_excel_custom_photo_height(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel respects custom photo height."""
        pytest.skip("Service implementation pending")

    def test_excel_handles_missing_photos(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel handles items without photos."""
        pytest.skip("Service implementation pending")

    def test_excel_formatting(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel has proper formatting."""
        # Headers, borders, alignment, etc.
        pytest.skip("Service implementation pending")

    def test_excel_file_size(self, sample_boq_item_data, temp_dir: Path):
        """Test generated Excel file is reasonable size."""
        pytest.skip("Service implementation pending")

    def test_excel_is_valid_xlsx(self, sample_boq_item_data, temp_dir: Path):
        """Test generated file is valid XLSX format."""
        pytest.skip("Service implementation pending")


class TestExcelFormatting:
    """Tests for Excel formatting compliance."""

    def test_fairmont_format_compliance(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel matches Fairmont format requirements."""
        pytest.skip("Service implementation pending")

    def test_excel_header_row(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel header row formatting."""
        pytest.skip("Service implementation pending")

    def test_excel_data_row_formatting(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel data row formatting."""
        pytest.skip("Service implementation pending")

    def test_excel_number_formatting(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel number formatting (qty, dimensions)."""
        pytest.skip("Service implementation pending")


class TestExcelMultipleDocuments:
    """Tests for Excel generation from multiple documents."""

    def test_excel_from_multiple_docs(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel from multiple merged documents."""
        pytest.skip("Service implementation pending")

    def test_excel_deduplication(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel handles duplicate item numbers."""
        pytest.skip("Service implementation pending")

    def test_excel_item_numbering(self, sample_boq_item_data, temp_dir: Path):
        """Test Excel renumbers items sequentially."""
        pytest.skip("Service implementation pending")
