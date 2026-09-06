"""
FastAPI Route Dependencies.
Injects database sessions, validates user sessions, verifies rate limits, and extracts roles.
"""
from typing import Tuple
from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.auth.permissions import get_current_user_role
from backend.app.auth.session import get_or_create_session, hash_ip
from backend.app.core.config import settings
from backend.app.db.models import Session
from backend.app.db.session import get_db
from backend.app.gateway.rate_limiter import rate_limiter


async def get_session_context(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> Session:
    """Retrieves or initializes a secure session."""
    session, _ = await get_or_create_session(request, response, db)
    return session


async def enforce_rate_limits(
    request: Request,
    session: Session = Depends(get_session_context)
) -> None:
    """Enforces rate limits by IP and Session ID."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    ip_hash = hash_ip(client_ip)

    # Rate limit by IP
    await rate_limiter.check_rate_limit(
        identifier=f"ip:{ip_hash}",
        max_requests=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60
    )

    # Rate limit by Session
    await rate_limiter.check_rate_limit(
        identifier=f"sess:{session.id}",
        max_requests=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60
    )
