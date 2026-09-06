"""
Centralized Exception Hierarchy for Enterprise Chatbot.
Ensures zero stack trace leakage to clients and returns uniform JSON responses.
"""
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class ChatbotBaseException(Exception):
    """Base exception for application-level errors."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Dict[str, Any]] = None,
        user_safe_message: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        self.user_safe_message = user_safe_message or "An error occurred while processing your request."


class SecurityBlockException(ChatbotBaseException):
    """Raised when input/output violates security policy (injection, secret leak, jailbreak)."""
    def __init__(self, message: str, reason: str = "security_policy_violation", user_safe_message: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="SECURITY_VIOLATION",
            details={"reason": reason},
            user_safe_message=user_safe_message or "I cannot process this request as it violates company safety policies."
        )


class RateLimitExceededException(ChatbotBaseException):
    """Raised when request quota or rate limit is breached."""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            user_safe_message=f"Too many requests. Please try again in {retry_after} seconds."
        )
        self.retry_after = retry_after


class CostBudgetExceededException(ChatbotBaseException):
    """Raised when per-request or daily cost cap is breached."""
    def __init__(self, message: str = "Daily AI cost budget reached."):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="BUDGET_EXCEEDED",
            user_safe_message="System temporarily operating under reduced quota. Please try again later."
        )


class LLMProviderUnavailableException(ChatbotBaseException):
    """Raised when all LLM providers fail or circuit breaker is open."""
    def __init__(self, message: str = "All LLM providers are currently unavailable."):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="AI_PROVIDER_UNAVAILABLE",
            user_safe_message="Our AI service is temporarily experiencing high load. Please try again in a few moments."
        )


class UnauthorizedToolException(ChatbotBaseException):
    """Raised when tool execution permission check fails."""
    def __init__(self, tool_name: str):
        super().__init__(
            message=f"Unauthorized access to tool: {tool_name}",
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="UNAUTHORIZED_TOOL",
            user_safe_message="Unauthorized tool execution attempted."
        )


class SSRFBlockedException(ChatbotBaseException):
    """Raised when URL resolution targets internal, private, or loopback IPs."""
    def __init__(self, target_url: str):
        super().__init__(
            message=f"SSRF protection blocked target: {target_url}",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="SSRF_DETECTED",
            user_safe_message="Access to the requested URL is restricted."
        )


async def chatbot_exception_handler(request: Request, exc: ChatbotBaseException) -> JSONResponse:
    """Standardized handler for application exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    headers = {}
    if isinstance(exc, RateLimitExceededException):
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.user_safe_message,
            "request_id": request_id,
            "details": exc.details if getattr(request.app.state, "debug", False) else {}
        },
        headers=headers
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback catch-all handler preventing any stack trace or internals from leaking."""
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Something went wrong while processing your request. Please try again later.",
            "request_id": request_id
        }
    )
