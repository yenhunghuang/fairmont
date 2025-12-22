"""Unit tests for Google Drive service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import base64

pytestmark = pytest.mark.unit


class TestGoogleDriveService:
    """Tests for Google Drive service."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with Google credentials."""
        with patch("app.services.google_drive_service.settings") as mock:
            mock.google_credentials_path_resolved = MagicMock()
            mock.google_credentials_path_resolved.exists.return_value = True
            mock.google_drive_folder_id = ""
            yield mock

    @pytest.fixture
    def mock_credentials(self):
        """Mock Google API credentials."""
        with patch("app.services.google_drive_service.service_account") as mock:
            mock_creds = MagicMock()
            mock.Credentials.from_service_account_file.return_value = mock_creds
            yield mock

    @pytest.fixture
    def mock_build(self):
        """Mock Google API build function."""
        with patch("app.services.google_drive_service.build") as mock:
            mock_service = MagicMock()
            mock.return_value = mock_service
            yield mock, mock_service

    def test_service_initialization(self, mock_settings, mock_credentials, mock_build):
        """Test service initializes correctly."""
        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        assert service._service is None  # Lazy initialization

    def test_authentication_success(self, mock_settings, mock_credentials, mock_build):
        """Test successful authentication."""
        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        result = service._get_service()

        assert result is not None
        mock_credentials.Credentials.from_service_account_file.assert_called_once()

    def test_authentication_missing_credentials(self):
        """Test authentication fails when credentials missing."""
        with patch("app.services.google_drive_service.settings") as mock_settings:
            mock_settings.google_credentials_path_resolved = None

            from app.services.google_drive_service import GoogleDriveService
            from app.utils import APIError

            service = GoogleDriveService()

            with pytest.raises(APIError) as exc_info:
                service._authenticate()

            assert "GOOGLE_AUTH_FAILED" in str(exc_info.value.error_code)

    def test_create_folder(self, mock_settings, mock_credentials, mock_build):
        """Test folder creation."""
        _, mock_service = mock_build
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_files.create.return_value.execute.return_value = {"id": "folder123"}

        mock_permissions = MagicMock()
        mock_service.permissions.return_value = mock_permissions
        mock_permissions.create.return_value.execute.return_value = {"id": "perm123"}

        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        folder_id = service.create_folder("test-folder")

        assert folder_id == "folder123"
        mock_files.create.assert_called_once()

    def test_upload_image(self, mock_settings, mock_credentials, mock_build):
        """Test image upload returns file ID."""
        _, mock_service = mock_build
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_files.create.return_value.execute.return_value = {"id": "file123"}

        mock_permissions = MagicMock()
        mock_service.permissions.return_value = mock_permissions
        mock_permissions.create.return_value.execute.return_value = {"id": "perm123"}

        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        image_data = b"\x89PNG\r\n\x1a\n"  # PNG header
        url = service.upload_image(image_data, "test.png", "folder123")

        assert url is not None
        assert "file123" in url
        mock_files.create.assert_called_once()

    def test_upload_base64_image(self, mock_settings, mock_credentials, mock_build):
        """Test Base64 image upload."""
        _, mock_service = mock_build
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_files.create.return_value.execute.return_value = {"id": "file456"}

        mock_permissions = MagicMock()
        mock_service.permissions.return_value = mock_permissions
        mock_permissions.create.return_value.execute.return_value = {"id": "perm123"}

        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        # Create a simple Base64 encoded PNG
        image_data = b"\x89PNG\r\n\x1a\n"
        base64_data = f"data:image/png;base64,{base64.b64encode(image_data).decode()}"

        url = service.upload_base64_image(base64_data, "test.png", "folder123")

        assert url is not None
        assert "file456" in url

    def test_set_public_access(self, mock_settings, mock_credentials, mock_build):
        """Test setting public link permission."""
        _, mock_service = mock_build
        mock_permissions = MagicMock()
        mock_service.permissions.return_value = mock_permissions
        mock_permissions.create.return_value.execute.return_value = {"id": "perm123"}

        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        # Should not raise
        service.set_public_access("file123")

        mock_permissions.create.assert_called_once()
        call_args = mock_permissions.create.call_args
        assert call_args.kwargs["body"]["type"] == "anyone"
        assert call_args.kwargs["body"]["role"] == "reader"

    def test_get_image_url(self, mock_settings, mock_credentials, mock_build):
        """Test URL generation for IMAGE() function."""
        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        url = service.get_image_url("file123")

        assert url == "https://drive.google.com/uc?export=view&id=file123"

    def test_handles_api_error(self, mock_settings, mock_credentials, mock_build):
        """Test graceful handling of API errors."""
        from googleapiclient.errors import HttpError

        _, mock_service = mock_build
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files

        # Simulate 500 error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_files.create.return_value.execute.side_effect = HttpError(
            mock_response, b"Internal Server Error"
        )

        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        # upload_image should return None on failure (graceful degradation)
        result = service.upload_image(b"test", "test.png", "folder123")

        assert result is None

    def test_handles_quota_exceeded(self, mock_settings, mock_credentials, mock_build):
        """Test quota exceeded error handling."""
        from googleapiclient.errors import HttpError

        _, mock_service = mock_build
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files

        # Simulate 403 quota error
        mock_response = MagicMock()
        mock_response.status = 403
        mock_files.create.return_value.execute.side_effect = HttpError(
            mock_response, b"Quota exceeded"
        )

        from app.services.google_drive_service import GoogleDriveService
        from app.utils import APIError

        service = GoogleDriveService()

        with pytest.raises(APIError) as exc_info:
            service.create_folder("test-folder")

        assert "GOOGLE_QUOTA_EXCEEDED" in str(exc_info.value.error_code)

    def test_delete_folder(self, mock_settings, mock_credentials, mock_build):
        """Test folder deletion."""
        _, mock_service = mock_build
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_files.delete.return_value.execute.return_value = None

        from app.services.google_drive_service import GoogleDriveService

        service = GoogleDriveService()
        result = service.delete_folder("folder123")

        assert result is True
        mock_files.delete.assert_called_once()

    def test_singleton_factory(self, mock_settings, mock_credentials, mock_build):
        """Test singleton factory function."""
        from app.services.google_drive_service import get_google_drive_service

        # Reset singleton
        import app.services.google_drive_service as module
        module._service_instance = None

        service1 = get_google_drive_service()
        service2 = get_google_drive_service()

        assert service1 is service2
