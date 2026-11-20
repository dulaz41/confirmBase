from __future__ import annotations

import time
import asyncio
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException, status
from app.core.config import settings


class InMemoryRateLimiter:
    """
    Thread-safe, sliding-window rate limiter for FastAPI.
    Supports in-memory tracking with auto-expiration of older timestamps.
    Interface is pluggable and easily replaceable with Redis in distributed deployments.
    """

    def __init__(self):
        # Maps client_identifier -> list of request timestamps
        self._requests: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if request is allowed under sliding window.
        Returns (is_allowed, remaining, retry_after_seconds).
        """
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            timestamps = self._requests.get(key, [])
            # Filter timestamps within window
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= max_requests:
                # Limit exceeded
                oldest_in_window = valid_timestamps[0]
                retry_after = max(1, int(oldest_in_window + window_seconds - now))
                self._requests[key] = valid_timestamps
                return False, 0, retry_after

            # Record current timestamp
            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps
            remaining = max_requests - len(valid_timestamps)

            # Periodically cleanup empty/expired entries if dictionary grows large
            if len(self._requests) > 10000:
                self._cleanup_expired(now)

            return True, remaining, 0

    def _cleanup_expired(self, now: float):
        keys_to_delete = [
            k for k, v in self._requests.items() if not v or v[-1] < (now - 3600)
        ]
        for k in keys_to_delete:
            del self._requests[k]

    def reset(self):
        """Reset all rate limiter state (useful for tests)."""
        self._requests.clear()


limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    """Extracts client IP from proxy headers or direct client connection."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in X-Forwarded-For is client behind reverse proxy
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_waitlist_rate_limit(request: Request):
    """Rate limit dependency for public waitlist endpoint."""
    ip = get_client_ip(request)
    key = f"waitlist:{ip}"
    allowed, remaining, retry_after = await limiter.is_allowed(
        key=key,
        max_requests=settings.WAITLIST_RATE_LIMIT,
        window_seconds=settings.WAITLIST_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


async def check_admin_rate_limit(request: Request):
    """Rate limit dependency for admin endpoints."""
    ip = get_client_ip(request)
    key = f"admin:{ip}"
    allowed, remaining, retry_after = await limiter.is_allowed(
        key=key,
        max_requests=settings.ADMIN_RATE_LIMIT,
        window_seconds=settings.ADMIN_RATE_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Admin rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
