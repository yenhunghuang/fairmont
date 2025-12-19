"""FastAPI application entry point."""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .store import get_store
from .utils import APIError
from .models import ErrorResponse


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create store instance
store = get_store()


async def cleanup_temp_files() -> None:
    """Background task to cleanup temporary files."""
    from .utils import FileManager

    try:
        file_manager = FileManager(
            temp_dir=settings.temp_dir_path,
            images_dir=settings.extracted_images_dir_path
        )
        deleted = file_manager.cleanup_temp_files(days=7)
        logger.info(f"Cleaned up {deleted} temporary files")
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Application starting up...")
    logger.info(f"Settings: host={settings.backend_host}, port={settings.backend_port}")
    logger.info(f"Max file size: {settings.max_file_size_mb}MB")
    logger.info(f"Temp directory: {settings.temp_dir}")
    logger.info(f"Store stats: {store.get_stats()}")

    # Schedule cleanup task (every 24 hours)
    cleanup_task = None
    try:
        async def run_cleanup():
            while True:
                await asyncio.sleep(86400)  # 24 hours
                await cleanup_temp_files()

        cleanup_task = asyncio.create_task(run_cleanup())
    except Exception as e:
        logger.warning(f"Could not schedule cleanup task: {e}")

    yield

    # Shutdown
    logger.info("Application shutting down...")
    if cleanup_task:
        cleanup_task.cancel()
    logger.info("Application stopped")


# Create FastAPI app
app = FastAPI(
    title="家具報價單系統",
    description="自動化家具報價單生成系統",
    version="0.1.0",
    lifespan=lifespan,
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error handler for APIError
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle API errors with proper response format."""
    error_response = ErrorResponse(
        success=False,
        message=exc.message,
        error_code=exc.error_code.value,
    )
    logger.error(f"APIError: {exc.error_code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


# General exception handler
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    error_response = ErrorResponse(
        success=False,
        message="伺服器內部錯誤",
        error_code="INTERNAL_ERROR",
    )
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(),
    )


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        Health status and store statistics
    """
    return {
        "status": "healthy",
        "service": "家具報價單系統",
        "version": "0.1.0",
        "store": store.get_stats(),
    }


# Register API routers
from .api.routes import health, upload, parse, export, task

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(parse.router)
app.include_router(export.router)
app.include_router(task.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.backend_debug,
    )
