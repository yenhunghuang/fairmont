"""Unit tests for Google Sheets generator service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import uuid

pytestmark = pytest.mark.unit


class TestGoogleSheetsGeneratorService:
    """Tests for Google Sheets generator."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with Google credentials."""
        with patch("app.services.google_sheets_generator.settings") as mock:
            mock.google_credentials_path_resolved = MagicMock()
            mock.google_credentials_path_resolved.exists.return_value = True
            mock.google_sheets_enabled = True
            mock.google_sheets_available = True
            yield mock

    @pytest.fixture
    def mock_credentials(self):
        """Mock Google API credentials."""
        with patch("app.services.google_sheets_generator.service_account") as mock:
            mock_creds = MagicMock()
            mock.Credentials.from_service_account_file.return_value = mock_creds
            yield mock

    @pytest.fixture
    def mock_build(self):
        """Mock Google API build function."""
        with patch("app.services.google_sheets_generator.build") as mock:
            mock_service = MagicMock()
            mock.return_value = mock_service
            yield mock, mock_service

    @pytest.fixture
    def mock_drive_service(self):
        """Mock Google Drive service."""
        with patch("app.services.google_sheets_generator.get_google_drive_service") as mock:
            mock_service = MagicMock()
            mock.return_value = mock_service
            mock_service.create_folder.return_value = "folder123"
            mock_service.upload_base64_image.return_value = "https://drive.google.com/uc?export=view&id=img123"
            yield mock_service

    @pytest.fixture
    def sample_quotation(self):
        """Create sample quotation for testing."""
        from app.models import Quotation, BOQItem

        items = [
            BOQItem(
                id=str(uuid.uuid4()),
                no=1,
                item_no="FUR-001",
                description="Office Chair",
                dimension="600x600x1000",
                qty=10,
                uom="PCS",
                unit_cbm=0.36,
                location="Floor 1",
                materials_specs="Leather",
                brand="Herman Miller",
                photo_base64="data:image/png;base64,iVBORw0KGgo=",
            ),
            BOQItem(
                id=str(uuid.uuid4()),
                no=2,
                item_no="FUR-002",
                description="Office Desk",
                dimension="1500x750x750",
                qty=5,
                uom="SET",
                unit_cbm=0.84,
                location="Floor 2",
                materials_specs="Oak Wood",
                brand="IKEA",
            ),
        ]

        quotation = Quotation(
            id=str(uuid.uuid4()),
            title="Test Quotation",
            source_document_ids=["doc1"],
            items=items,
        )
        quotation.update_statistics()

        return quotation

    def test_generator_initialization(self, mock_settings, mock_credentials, mock_build):
        """Test generator initializes correctly."""
        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        assert generator._service is None  # Lazy initialization
        assert len(generator.COLUMNS) == 15  # 15 columns per Fairmont format

    def test_columns_match_fairmont_format(self):
        """Test column headers match Fairmont Excel format."""
        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        expected_headers = [
            "NO.", "Item no.", "Description", "Photo",
            "Dimension\nWxDxH (mm)", "Qty", "UOM",
            "Unit Rate\n(USD)", "Amount\n(USD)",
            "Unit\nCBM", "Total\nCBM",
            "Note", "Location", "Materials Used / Specs", "Brand"
        ]

        actual_headers = [col[0] for col in GoogleSheetsGeneratorService.COLUMNS]
        assert actual_headers == expected_headers

    def test_create_spreadsheet(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service
    ):
        """Test spreadsheet creation."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.create.return_value.execute.return_value = {
            "spreadsheetId": "sheet123"
        }

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        spreadsheet_id = generator._create_spreadsheet("Test Sheet")

        assert spreadsheet_id == "sheet123"
        mock_spreadsheets.create.assert_called_once()

    def test_write_headers_correct_format(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service
    ):
        """Test headers match Fairmont 15-column format."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        generator._write_headers("sheet123")

        # Verify update was called with correct range
        call_args = mock_values.update.call_args
        assert call_args.kwargs["range"] == "A1:O1"  # 15 columns

        # Verify header content
        values = call_args.kwargs["body"]["values"]
        assert len(values[0]) == 15

    def test_write_items_with_photos(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service, sample_quotation
    ):
        """Test items written with IMAGE() formulas."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        image_count = generator._write_items(
            "sheet123",
            sample_quotation.items,
            include_photos=True,
            folder_id="folder123",
        )

        # Should have uploaded 1 image (first item has photo)
        assert image_count == 1
        mock_drive_service.upload_base64_image.assert_called_once()

    def test_write_items_without_photos(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service, sample_quotation
    ):
        """Test items without photos."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        image_count = generator._write_items(
            "sheet123",
            sample_quotation.items,
            include_photos=False,
            folder_id=None,
        )

        assert image_count == 0
        mock_drive_service.upload_base64_image.assert_not_called()

    def test_formatting_applied(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service
    ):
        """Test Fairmont formatting is applied."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_spreadsheets.batchUpdate.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        generator._format_sheet("sheet123", row_count=5)

        mock_spreadsheets.batchUpdate.assert_called_once()
        call_args = mock_spreadsheets.batchUpdate.call_args
        requests = call_args.kwargs["body"]["requests"]

        # Should have multiple formatting requests
        assert len(requests) > 0

    def test_sharing_view_mode(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service
    ):
        """Test view-only sharing."""
        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()

        with patch("app.services.google_sheets_generator.build") as mock_build_drive:
            mock_drive = MagicMock()
            mock_build_drive.return_value = mock_drive
            mock_permissions = MagicMock()
            mock_drive.permissions.return_value = mock_permissions
            mock_permissions.create.return_value.execute.return_value = {}

            link = generator._set_sharing("sheet123", "view")

            assert "view" in link
            call_args = mock_permissions.create.call_args
            assert call_args.kwargs["body"]["role"] == "reader"

    def test_sharing_edit_mode(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service
    ):
        """Test edit sharing."""
        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()

        with patch("app.services.google_sheets_generator.build") as mock_build_drive:
            mock_drive = MagicMock()
            mock_build_drive.return_value = mock_drive
            mock_permissions = MagicMock()
            mock_drive.permissions.return_value = mock_permissions
            mock_permissions.create.return_value.execute.return_value = {}

            link = generator._set_sharing("sheet123", "edit")

            assert "edit" in link
            call_args = mock_permissions.create.call_args
            assert call_args.kwargs["body"]["role"] == "writer"

    def test_total_cbm_formula(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service, sample_quotation
    ):
        """Test Total CBM uses formula =F*J."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        generator._write_items(
            "sheet123",
            sample_quotation.items,
            include_photos=False,
            folder_id=None,
        )

        # Check that formula update was called for column K
        calls = mock_values.update.call_args_list
        formula_call = [c for c in calls if "K2:" in str(c)]
        assert len(formula_call) > 0

    def test_empty_price_columns(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service, sample_quotation
    ):
        """Test Unit Rate and Amount are empty."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()
        generator._write_items(
            "sheet123",
            sample_quotation.items,
            include_photos=False,
            folder_id=None,
        )

        # Get the items update call
        calls = mock_values.update.call_args_list
        items_call = [c for c in calls if "A2:" in str(c)][0]
        values = items_call.kwargs["body"]["values"]

        # Check columns H (index 7) and I (index 8) are empty
        for row in values:
            assert row[7] == ""  # Unit Rate
            assert row[8] == ""  # Amount

    def test_create_quotation_sheet_full_flow(
        self, mock_settings, mock_credentials, mock_build, mock_drive_service, sample_quotation
    ):
        """Test complete quotation sheet creation."""
        _, mock_service = mock_build
        mock_spreadsheets = MagicMock()
        mock_service.spreadsheets.return_value = mock_spreadsheets

        # Mock create
        mock_spreadsheets.create.return_value.execute.return_value = {
            "spreadsheetId": "sheet123"
        }

        # Mock values update
        mock_values = MagicMock()
        mock_spreadsheets.values.return_value = mock_values
        mock_values.update.return_value.execute.return_value = {}

        # Mock batch update
        mock_spreadsheets.batchUpdate.return_value.execute.return_value = {}

        from app.services.google_sheets_generator import GoogleSheetsGeneratorService

        generator = GoogleSheetsGeneratorService()

        with patch.object(generator, "_set_sharing") as mock_set_sharing:
            mock_set_sharing.return_value = "https://docs.google.com/spreadsheets/d/sheet123/view"

            result = generator.create_quotation_sheet(
                sample_quotation,
                include_photos=True,
                share_mode="view",
            )

        assert result.spreadsheet_id == "sheet123"
        assert "sheet123" in result.spreadsheet_url
        assert result.shareable_link is not None

    def test_sheets_disabled_error(self, mock_credentials, mock_build):
        """Test error when Sheets is disabled."""
        with patch("app.services.google_sheets_generator.settings") as mock_settings:
            mock_settings.google_sheets_available = False

            from app.services.google_sheets_generator import GoogleSheetsGeneratorService
            from app.utils import APIError
            from app.models import Quotation

            generator = GoogleSheetsGeneratorService()

            with pytest.raises(APIError) as exc_info:
                generator.create_quotation_sheet(
                    Quotation(items=[]),
                    include_photos=False,
                )

            assert "GOOGLE_SHEETS_DISABLED" in str(exc_info.value.error_code)

    def test_singleton_factory(self, mock_settings, mock_credentials, mock_build):
        """Test singleton factory function."""
        from app.services.google_sheets_generator import get_google_sheets_generator

        # Reset singleton
        import app.services.google_sheets_generator as module
        module._generator_instance = None

        generator1 = get_google_sheets_generator()
        generator2 = get_google_sheets_generator()

        assert generator1 is generator2
