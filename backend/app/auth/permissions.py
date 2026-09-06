"""
Role-Based Authorization & Permission Controls.
Ensures authorization is strictly executed server-side in deterministic Python code.
"""
from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from backend.app.core.config import settings

security_bearer = HTTPBearer(auto_error=False)


class UserRole(str, Enum):
    PUBLIC = "public"
    EMPLOYEE = "employee"
    SUPPORT = "support"
    ADMIN = "admin"


# Role hierarchy weights
ROLE_HIERARCHY = {
    UserRole.PUBLIC: 1,
    UserRole.EMPLOYEE: 2,
    UserRole.SUPPORT: 3,
    UserRole.ADMIN: 4,
}


def has_sufficient_role(current_role: str, required_role: UserRole) -> bool:
    """Verifies whether the current role satisfies the required role rank."""
    current_val = ROLE_HIERARCHY.get(UserRole(current_role), 1) if current_role in UserRole._value2member_map_ else 1
    required_val = ROLE_HIERARCHY.get(required_role, 1)
    return current_val >= required_val


async def get_current_user_role(
    request: Request = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> str:
    """
    Extracts user role from X-Admin-API-Key header, Admin Bearer token, or JWT.
    Defaults to 'public' for anonymous visitors.
    """
    # 1. Check direct X-Admin-API-Key header (ideal for webhooks, CI/CD, curl)
    if request:
        admin_key_header = request.headers.get("X-Admin-API-Key")
        if admin_key_header and admin_key_header == settings.ADMIN_API_KEY:
            return UserRole.ADMIN.value

    # 2. Check Bearer token
    if credentials:
        token = credentials.credentials

        # Direct admin API key match via Bearer header
        if token == settings.ADMIN_API_KEY:
            return UserRole.ADMIN.value

        # JWT Bearer token decode
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"]
            )
            return payload.get("role", UserRole.PUBLIC.value)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication credentials"
            )

    return UserRole.PUBLIC.value

