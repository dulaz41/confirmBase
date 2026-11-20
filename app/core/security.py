from __future__ import annotations

import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings

# HTTP Bearer scheme for Admin authorization
bearer_scheme = HTTPBearer(auto_error=False)


def verify_admin_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> bool:
    """
    Validates that the provided Bearer token matches the configured ADMIN_API_KEY
    using constant-time comparison to prevent timing attacks.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_key = credentials.credentials
    expected_key = settings.ADMIN_API_KEY

    # Use secrets.compare_digest for constant-time comparison
    if not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid administrative credentials",
        )

    return True
