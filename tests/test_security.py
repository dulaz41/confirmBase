from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.rate_limit import limiter


@pytest.mark.asyncio
async def test_admin_export_unauthorized_without_token(async_client: AsyncClient):
    """Admin export must reject unauthenticated requests with 401."""
    response = await async_client.get("/api/v1/admin/waitlist/export")
    assert response.status_code == 401
    assert response.json()["message"] == "Missing Authorization header"


@pytest.mark.asyncio
async def test_admin_export_forbidden_with_invalid_token(async_client: AsyncClient):
    """Admin export must reject invalid API keys with 403."""
    response = await async_client.get(
        "/api/v1/admin/waitlist/export",
        headers={"Authorization": "Bearer invalid_secret_key"},
    )
    assert response.status_code == 403
    assert response.json()["message"] == "Invalid administrative credentials"


@pytest.mark.asyncio
async def test_admin_credentials_not_in_url(async_client: AsyncClient):
    """Query parameter authentication is forbidden."""
    response = await async_client.get("/api/v1/admin/waitlist/export?api_key=some_key")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present(async_client: AsyncClient):
    """All responses must contain OWASP recommended security headers."""
    response = await async_client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in response.headers.get("Content-Security-Policy", "")


@pytest.mark.asyncio
async def test_rate_limiting_waitlist(async_client: AsyncClient):
    """Sending more requests than WAITLIST_RATE_LIMIT triggers 429 with Retry-After header."""
    limiter.reset()
    limit = settings.WAITLIST_RATE_LIMIT

    # Send up to the limit
    for i in range(limit):
        res = await async_client.post(
            "/api/v1/waitlist",
            json={"email": f"user{i}@example.com"},
        )
        assert res.status_code == 201

    # Next request should be blocked by rate limiter
    blocked_res = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "exceeded@example.com"},
    )
    assert blocked_res.status_code == 429
    assert blocked_res.json()["success"] is False
    assert "Retry-After" in blocked_res.headers


@pytest.mark.asyncio
async def test_oversized_payload_rejected(async_client: AsyncClient):
    """Requests exceeding MAX_REQUEST_BODY_SIZE_BYTES are rejected with 413."""
    # Create payload larger than 10KB
    large_payload = {"email": "large@example.com", "dummy": "X" * 15000}
    response = await async_client.post(
        "/api/v1/waitlist",
        json=large_payload,
        headers={"Content-Length": str(len(str(large_payload)))},
    )
    assert response.status_code in (413, 422)
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_internal_error_does_not_leak_internals(async_client: AsyncClient, monkeypatch):
    """Simulated unexpected internal errors must return safe message without stack traces or DB details."""
    from app.services.waitlist_service import WaitlistService

    async def mock_fail(*args, **kwargs):
        raise RuntimeError("CRITICAL DATABASE EXCEPTION: postgres://secret_user:secret_pass@10.0.0.1/db")

    monkeypatch.setattr(WaitlistService, "register_email", mock_fail)

    response = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "safe_error@example.com"},
    )
    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "An internal server error occurred."
    # Secrets / stack traces must never appear in response body
    assert "postgres" not in str(data)
    assert "secret_pass" not in str(data)
    assert "CRITICAL" not in str(data)
