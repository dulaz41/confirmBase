from __future__ import annotations

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.core.config import settings

logger = logging.getLogger("waitlist.access")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies security headers to every HTTP response.
    Documented for reverse-proxy compatibility.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Standard OWASP recommended security headers for APIs
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        # For interactive documentation routes (/docs, /redoc), allow Swagger UI assets
        if request.url.path in ("/docs", "/redoc"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests whose payload exceeds the configured maximum allowed size.
    Prevents denial of service attacks via oversized payloads.
    """

    def __init__(self, app, max_size_bytes: int = 10240):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next):
        # Fast check via Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_size_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"success": False, "message": "Request payload exceeds allowed limit."},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid Content-Length header."},
                )

        return await call_next(request)


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs structured HTTP requests with execution duration.
    Strictly avoids logging request bodies, authorization tokens, or user emails.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_host = request.client.host if request.client else "unknown"

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            # Avoid logging noisy health checks in normal logs
            if request.url.path not in ("/health", "/ready"):
                logger.info(
                    "HTTP request processed",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": client_host,
                    },
                )
            return response
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "Unhandled error during request processing",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": client_host,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "An internal server error occurred.",
                },
            )
