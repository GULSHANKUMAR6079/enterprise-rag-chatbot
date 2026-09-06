"""
Security Event Logging and Database Audit Trails.
Records security events, updates abuse scores, and logs high-severity alerts.
"""
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import SecurityEvent
from backend.app.observability.logger import app_logger
from backend.app.observability.metrics import SECURITY_EVENTS_TOTAL
from backend.app.security.abuse_detector import abuse_detector


async def record_security_event(
    event_type: str,
    severity: str,  # LOW, MEDIUM, HIGH, CRITICAL
    request_id: str,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    db: Optional[AsyncSession] = None
) -> None:
    """
    Logs, tracks metrics, and asynchronously records security violations.
    """
    details_dict = details or {}

    # 1. Structured log
    log_func = app_logger.warning if severity in ("LOW", "MEDIUM") else app_logger.error
    log_func(
        f"SECURITY_ALERT: {event_type} [{severity}]",
        extra={
            "security_event": event_type,
            "severity": severity,
            "request_id": request_id,
            "session_id": session_id,
            "details": details_dict
        }
    )

    # 2. Increment metric
    SECURITY_EVENTS_TOTAL.labels(event_type=event_type, severity=severity).inc()

    # 3. Update abuse score
    if session_id:
        severity_weight = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 5}.get(severity, 1)
        abuse_detector.record_violation(session_id, severity_weight, event_type)

    # 4. Persist to database if session provided
    if db:
        try:
            sec_event = SecurityEvent(
                session_id=session_id,
                event_type=event_type,
                severity=severity,
                request_id=request_id,
                details=details_dict
            )
            db.add(sec_event)
            await db.flush()
        except Exception as exc:
            app_logger.error(f"Failed to persist security event to DB: {exc}")
