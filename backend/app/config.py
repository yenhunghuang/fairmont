"""Application configuration module."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

# 計算專案根目錄的絕對路徑（相對於此文件的位置）
_THIS_DIR = Path(__file__).parent  # backend/app/
_BACKEND_ROOT = _THIS_DIR.parent  # backend/
_PROJECT_ROOT = _BACKEND_ROOT.parent  # Fairmont/
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Gemini API Configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"

    # Backend Configuration
    backend_host: str = "localhost"
    backend_port: int = 8000
    backend_debug: bool = False

    # Frontend Configuration
    frontend_port: int = 8501

    # File Management - 使用絕對路徑以避免從不同目錄啟動時的路徑問題
    temp_dir: str = str(_BACKEND_ROOT / "temp_files")
    extracted_images_dir: str = str(_BACKEND_ROOT / "extracted_images")
    max_file_size_mb: int = 50
    max_files: int = 5

    # Logging
    log_level: str = "INFO"

    # Computed paths
    @property
    def temp_dir_path(self) -> Path:
        """Get temp directory path as Path object (always absolute)."""
        path = Path(self.temp_dir)
        # 如果是相對路徑，基於專案根目錄解析
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def extracted_images_dir_path(self) -> Path:
        """Get extracted images directory path as Path object (always absolute)."""
        path = Path(self.extracted_images_dir)
        # 如果是相對路徑，基於專案根目錄解析
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
