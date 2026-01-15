"""Application configuration module."""

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
    gemini_model: str = "gemini-2.0-flash-lite"
    gemini_timeout_seconds: int = 300  # API 呼叫超時（5 分鐘）
    gemini_max_retries: int = 2  # 失敗時重試次數

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

    # Environment
    environment: str = "development"  # development, staging, production

    # Skills Configuration
    skills_dir: str = str(_PROJECT_ROOT / "skills")
    skills_cache_enabled: bool = True  # 生產環境啟用快取

    # Store Configuration
    store_cache_ttl: int = 3600  # 快取 TTL（秒），預設 1 小時

    # LangFuse Observability Configuration
    langfuse_enabled: bool = False  # 預設關閉，需設定 API Key 後啟用
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"  # 或自架 LangFuse 伺服器
    langfuse_release: str = "1.0.0"  # 版本標記

    # API Key Authentication
    api_key: str = ""  # Bearer Token 認證用

    # POC Configuration (固定值，未來可改為可配置)
    # 這些值在 POC 階段是固定的，集中管理以便未來擴展
    default_vendor_id: str = "habitus"  # 預設供應商 ID
    default_format_id: str = "fairmont"  # 預設輸出格式 ID

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

    @property
    def skills_dir_path(self) -> Path:
        """Get skills directory path as Path object (always absolute)."""
        path = Path(self.skills_dir)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # 忽略 .env 中的額外變數（如已移除的 Google Sheets 設定）
    }


# Global settings instance
settings = Settings()
