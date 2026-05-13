"""Health check and metrics endpoints"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.metrics import get_metrics_summary

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status", response_model=Dict[str, Any])
async def health_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Health check endpoint

    Returns:
        Health status with database connectivity
    """
    try:
        # Check database connectivity
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
    }


@router.get("/metrics", response_model=Dict[str, Any])
async def application_metrics() -> Dict[str, Any]:
    """Application metrics endpoint

    Returns:
        Aggregated metrics for request tracking
    """
    metrics = get_metrics_summary()
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_requests": metrics.total_requests,
        "successful_requests": metrics.successful_requests,
        "failed_requests": metrics.failed_requests,
        "avg_response_time_ms": round(metrics.avg_response_time_ms, 2),
        "error_count": metrics.error_count,
    }
