"""
Security Middleware for Enterprise Chatbot.
Injects security headers, correlation IDs, and validates request sizing.
"""
import time
import uuid
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies enterprise security headers on every HTTP response:
    CSP, X-Content-Type-Options, Frame-Ancestors, Referrer-Policy, HSTS.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",  # widget bundle
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: https:",
            "connect-src 'self' " + " ".join(settings.ALLOWED_ORIGINS),
            f"frame-ancestors {settings.CSP_FRAME_ANCESTORS}",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Injects unique Request-ID and measures total server request duration.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if upstream proxy provided X-Request-ID, otherwise generate cryptographically secure UUID
        request_id = request.headers.get("X-Request-ID")
        if not request_id or len(request_id) > 64:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(process_time_ms)
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Guards against large payload DOS / resource exhaustion by validating Content-Length.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > settings.MAX_REQUEST_PAYLOAD_BYTES:
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "success": False,
                                "error_code": "PAYLOAD_TOO_LARGE",
                                "message": f"Payload exceeds maximum allowed size of {settings.MAX_REQUEST_PAYLOAD_BYTES} bytes."
                            }
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"success": False, "error_code": "INVALID_CONTENT_LENGTH", "message": "Invalid Content-Length"}
                    )
        return await call_next(request)
