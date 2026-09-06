"""
Secure Session Management.
Uses cryptographically secure random session tokens, IP hashing, and prevents fixation attacks.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.db.models import Session, User


def hash_ip(ip: str) -> str:
    """Hashes IP address with server SECRET_KEY salt to respect privacy while allowing abuse tracking."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        ip.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def generate_session_token() -> str:
    """Generates 256-bit cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def make_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def get_or_create_session(
    request: Request,
    response: Response,
    db: AsyncSession
) -> Tuple[Session, bool]:
    """
    Validates or creates an anonymous or authenticated session.
    Sets secure HttpOnly cookie on response.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent", "unknown")[:500]
    current_ip_hash = hash_ip(client_ip)

    # Check for existing cookie
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    session: Optional[Session] = None
    is_new = False

    now_utc = datetime.now(timezone.utc)
    now_naive = now_utc.replace(tzinfo=None)

    if session_token:
        cutoff = now_naive if "sqlite" in settings.DATABASE_URL else now_utc
        result = await db.execute(
            select(Session).where(
                Session.session_token == session_token,
                Session.is_blocked == False,
                Session.expires_at > cutoff
            )
        )
        session = result.scalars().first()

    if not session:
        # Create brand new session
        is_new = True
        session_token = generate_session_token()
        expires_at = now_utc + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)
        session = Session(
            session_token=session_token,
            ip_hash=current_ip_hash,
            user_agent=user_agent,
            expires_at=expires_at,
            abuse_score=0,
            is_blocked=False
        )
        db.add(session)
        await db.flush()

        # Set secure session cookie
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=session_token,
            max_age=settings.SESSION_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=settings.SECURE_COOKIES or (settings.APP_ENV == "production"),
            path="/"
        )
    else:
        # Extend sliding expiration if halfway through lifetime
        remaining = make_aware(session.expires_at) - now_utc
        if remaining.total_seconds() < (settings.SESSION_MAX_AGE_SECONDS / 2):
            session.expires_at = now_utc + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)
            response.set_cookie(
                key=settings.SESSION_COOKIE_NAME,
                value=session.session_token,
                max_age=settings.SESSION_MAX_AGE_SECONDS,
                httponly=True,
                samesite="lax",
                secure=settings.SECURE_COOKIES or (settings.APP_ENV == "production"),
                path="/"
            )

    return session, is_new
