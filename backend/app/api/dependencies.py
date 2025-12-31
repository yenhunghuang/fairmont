"""API dependencies and injection."""

from typing import Annotated
from fastapi import Depends, UploadFile, File, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from ..store import InMemoryStore, get_store
from ..utils import FileValidator, FileManager
from ..config import settings


logger = logging.getLogger(__name__)


def get_store_dependency() -> InMemoryStore:
    """
    Dependency to get the in-memory store.

    Returns:
        InMemoryStore instance
    """
    return get_store()


def get_file_validator() -> FileValidator:
    """
    Dependency to get file validator.

    Returns:
        FileValidator instance
    """
    return FileValidator(
        max_file_size_mb=settings.max_file_size_mb,
        max_files=settings.max_files,
    )


def get_file_manager() -> FileManager:
    """
    Dependency to get file manager.

    Returns:
        FileManager instance
    """
    return FileManager(
        temp_dir=settings.temp_dir_path,
        images_dir=settings.extracted_images_dir_path,
    )


async def validate_pdf_files(
    files: Annotated[list[UploadFile], File(...)]
) -> list[tuple[str, bytes]]:
    """
    Validate and read PDF files.

    Args:
        files: List of uploaded files

    Returns:
        List of (filename, content) tuples

    Raises:
        APIError: If validation fails
    """
    validator = get_file_validator()

    # Validate count
    validator.validate_file_count(len(files))

    # Validate and read each file
    validated_files = []
    for file in files:
        if file.content_type is None:
            file.content_type = "application/pdf"

        # Validate file
        content = await file.read()
        validator.validate_file(
            filename=file.filename or "unknown",
            file_size=len(content),
            mime_type=file.content_type,
        )

        validated_files.append((file.filename or "upload.pdf", content))

    logger.info(f"Successfully validated {len(validated_files)} files")
    return validated_files


# Type aliases for common dependencies
StoreDep = Annotated[InMemoryStore, Depends(get_store_dependency)]
FileValidatorDep = Annotated[FileValidator, Depends(get_file_validator)]
FileManagerDep = Annotated[FileManager, Depends(get_file_manager)]


# =============================================================================
# API Key Bearer Authentication
# =============================================================================

# Bearer scheme（讓 Swagger UI 顯示 Authorize 按鈕）
api_key_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="請輸入 API Key",
)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(api_key_scheme),
) -> str:
    """
    驗證 API Key.

    - 檢查 Authorization: Bearer <api_key>
    - 返回驗證後的 API Key

    Raises:
        HTTPException: 401 Unauthorized if API Key is invalid
    """
    token = credentials.credentials

    if token != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


# Type alias for API Key dependency
APIKeyDep = Annotated[str, Depends(verify_api_key)]
