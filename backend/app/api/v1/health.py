"""
Health, Readiness, and Metrics Endpoints.
Used by Kubernetes, Docker Compose, and load balancers to evaluate service availability.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.gateway.circuit_breaker import circuit_breakers
from backend.app.gateway.rate_limiter import rate_limiter
from backend.app.observability.metrics import CONTENT_TYPE_LATEST, get_metrics_snapshot
from backend.app.schemas.feedback import HealthStatus, ReadinessStatus

router = APIRouter(tags=["Health & Operations"])


@router.get("/health/live", response_model=HealthStatus)
async def liveness_check() -> HealthStatus:
    """Liveness probe confirming the server process is responsive."""
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.APP_VERSION
    )


@router.get("/health/ready", response_model=ReadinessStatus)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> ReadinessStatus:
    """Readiness probe testing critical dependencies (Database, Redis, LLM circuits)."""
    # 1. Database probe
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # 2. Redis probe
    redis_status = "connected" if rate_limiter._redis_connected else "fallback"

    # 3. Circuit breaker check
    llm_status = "ready"
    for breaker in circuit_breakers.values():
        if breaker.state == "OPEN":
            llm_status = "circuit_open"
            break

    is_overall_ready = db_status == "connected"
    return ReadinessStatus(
        status="ready" if is_overall_ready else "not_ready",
        database=db_status,
        redis=redis_status,
        llm_gateway=llm_status
    )


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics scrape target."""
    data = get_metrics_snapshot()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@router.get("/system/traces")
async def get_system_traces(
    limit: int = 50,
    trace_id: Optional[str] = None
):
    """
    OpenTelemetry Traces Inspection Endpoint.
    Returns in-memory recorded distributed spans and traces with timing, hierarchy, and status.
    """
    from backend.app.observability.tracing import trace_buffer
    return trace_buffer.get_traces_summary(limit=limit, trace_id=trace_id)

