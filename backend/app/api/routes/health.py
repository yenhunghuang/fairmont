"""Health check endpoint."""

from fastapi import APIRouter

from ...api.dependencies import StoreDep


router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health")
async def health_check(store: StoreDep) -> dict:
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
