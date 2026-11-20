from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.routes import admin, health, waitlist
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import (
    AccessLoggingMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.database import engine
from app.services.backup_service import BackupService

# Initialize structured logging
logger = setup_logging(debug=settings.DEBUG)

# Background scheduler for 24-hour backups
scheduler = AsyncIOScheduler()


async def scheduled_backup_job():
    """Background task triggered every 24 hours."""
    logger.info("Executing scheduled 24-hour automated backup job...")
    try:
        service = BackupService()
        await service.run_full_backup()
    except Exception as exc:
        logger.error(f"Scheduled backup job encountered an error: {exc}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: manages background scheduler and connection pools."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' environment")

    # Start 24-hour backup scheduler (do not start during unit testing)
    if settings.APP_ENV != "testing":
        scheduler.add_job(
            scheduled_backup_job,
            trigger=CronTrigger(
                hour=settings.BACKUP_SCHEDULE_HOUR_UTC,
                minute=settings.BACKUP_SCHEDULE_MINUTE_UTC,
                timezone="UTC",
            ),
            id="daily_backup",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            f"Backup scheduler started: runs daily at {settings.BACKUP_SCHEDULE_HOUR_UTC:02d}:{settings.BACKUP_SCHEDULE_MINUTE_UTC:02d} UTC"
        )

    yield

    # Shutdown sequence
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Backup scheduler stopped")

    await engine.dispose()
    logger.info("Database connection pools closed")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    tags_metadata = [
        {
            "name": "Tenant",
            "description": "Tenant waitlist registrations. Captures tenant preferences, budget, move-in timeframe, and deal-breaker red flags.",
        },
        {
            "name": "Agent",
            "description": "Agent and landlord registrations. Captures role, operating areas, and monthly listing volumes.",
        },
        {
            "name": "Admin",
            "description": "Administrative management endpoints. Export CSVs (full data or emails-only for bulk campaigns), view statistics, and manage entries. Requires Bearer API Key authentication.",
        },
        {
            "name": "Waitlist (Unified)",
            "description": "Unified registration endpoint accepting dynamic tenant or agent submissions from frontend forms.",
        },
        {
            "name": "Health",
            "description": "Application health and database connectivity probes.",
        },
    ]

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="Production-grade, privacy-focused waitlist collection and management backend for ConfirmBase.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=tags_metadata,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,
            "docExpansion": "list",
            "filter": True,
            "persistAuthorization": True,
        },
        lifespan=lifespan,
    )

    # 1. Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. Request Size Limiting Middleware (10KB limit)
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_size_bytes=settings.MAX_REQUEST_BODY_SIZE_BYTES,
    )

    # 3. Access Logging Middleware
    app.add_middleware(AccessLoggingMiddleware)

    # 4. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Exception Handlers: Never leak internal tracebacks, SQL queries, or filesystem paths
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail,
            },
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Format human-friendly validation message without raw stack trace
        errors_list = []
        errors_dict = {}
        for err in exc.errors():
            loc = err.get("loc", [])
            field = str(loc[-1]) if loc else "body"
            msg = err.get("msg", "Invalid value")
            errors_dict[field] = msg
            loc_str = " -> ".join(str(p) for p in loc)
            errors_list.append(f"{loc_str}: {msg}")

        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY)
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": "validation",
                "errors": errors_dict,
                "success": False,
                "message": "Validation error: invalid request payload or fields.",
                "details": errors_list,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled internal server error",
            extra={
                "error_type": type(exc).__name__,
                "path": request.url.path,
                "method": request.method,
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "An internal server error occurred.",
            },
        )

    # Register Routers
    app.include_router(health.router)
    app.include_router(waitlist.router)
    app.include_router(waitlist.v1_router)
    app.include_router(admin.router, prefix="/api/v1/admin/waitlist")
    app.include_router(admin.router, prefix="/v1/admin/waitlist")

    # Serve ConfirmBase landing page
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_index():
        index_file = Path(__file__).resolve().parent.parent / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>ConfirmBase API</h1>")

    return app


app = create_app()
