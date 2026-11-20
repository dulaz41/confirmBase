from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import check_database_health, get_db

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Application Health Probe",
    description="Minimal health response indicating the application process is running. Never leaks internals.",
)
@router.head(
    "/health",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def health_check():
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Application Readiness Probe",
    description="Verifies that critical backing services, specifically PostgreSQL, are reachable.",
)
@router.head(
    "/ready",
    include_in_schema=False,
)
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db)):
    is_db_ready = await check_database_health(db)
    if is_db_ready:
        return {"status": "ready", "database": "connected"}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unavailable", "database": "disconnected"}
