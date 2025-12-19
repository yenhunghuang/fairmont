"""Application configuration module."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Gemini API Configuration
    gemini_api_key: str = ""

    # Backend Configuration
    backend_host: str = "localhost"
    backend_port: int = 8000
    backend_debug: bool = False

    # Frontend Configuration
    frontend_port: int = 8501

    # File Management
    temp_dir: str = "./backend/temp_files"
    extracted_images_dir: str = "./backend/extracted_images"
    max_file_size_mb: int = 50
    max_files: int = 5

    # Logging
    log_level: str = "INFO"

    # Computed paths
    @property
    def temp_dir_path(self) -> Path:
        """Get temp directory path as Path object."""
        path = Path(self.temp_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def extracted_images_dir_path(self) -> Path:
        """Get extracted images directory path as Path object."""
        path = Path(self.extracted_images_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    class Config:
        """Pydantic settings configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Allow loading from environment variables with underscores or hyphens
        fields = {
            "gemini_api_key": {"env": "GEMINI_API_KEY"},
            "backend_host": {"env": "BACKEND_HOST"},
            "backend_port": {"env": "BACKEND_PORT"},
            "backend_debug": {"env": "BACKEND_DEBUG"},
            "frontend_port": {"env": "FRONTEND_PORT"},
            "temp_dir": {"env": "TEMP_DIR"},
            "extracted_images_dir": {"env": "EXTRACTED_IMAGES_DIR"},
            "max_file_size_mb": {"env": "MAX_FILE_SIZE_MB"},
            "max_files": {"env": "MAX_FILES"},
            "log_level": {"env": "LOG_LEVEL"},
        }


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
