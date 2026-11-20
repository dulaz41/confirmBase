from __future__ import annotations

import uuid
from datetime import datetime, timezone
import logging
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_admin_rate_limit, get_db, verify_admin_key
from app.schemas.admin import (
    AdminDeleteResponse,
    AdminEntriesListResponse,
    AdminStatsOut,
    WaitlistEntryDetail,
)
from app.services.csv_service import CSVExportService
from app.services.waitlist_service import WaitlistService

logger = logging.getLogger("waitlist.admin")
audit_logger = logging.getLogger("waitlist.audit")

router = APIRouter(
    tags=["Admin"],
    dependencies=[Depends(verify_admin_key), Depends(check_admin_rate_limit)],
)


@router.get(
    "/entries",
    response_model=AdminEntriesListResponse,
    summary="List Waitlist Entries",
    description="Returns a paginated list of waitlist entries with all profile details attached. Filter by 'tenant' or 'agent' to view them separately.",
    responses={
        200: {"description": "List of entries with all attached details"},
        401: {"description": "Missing Authorization header"},
        403: {"description": "Invalid administrative credentials"},
    },
)
async def list_waitlist_entries(
    user_type: Optional[Literal["tenant", "agent"]] = Query(
        default=None,
        alias="type",
        description="Filter entries by 'tenant' or 'agent'. If omitted, returns both.",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> AdminEntriesListResponse:
    """
    Lists waitlist entries with attached details.
    Allows filtering to inspect tenants and agents separately.
    """
    total, entries = await WaitlistService.list_entries(
        db, user_type=user_type, page=page, page_size=page_size
    )
    return AdminEntriesListResponse(
        total=total,
        page=page,
        page_size=page_size,
        entries=[WaitlistEntryDetail.model_validate(e) for e in entries],
    )


@router.get(
    "/entries/tenant",
    response_model=AdminEntriesListResponse,
    summary="List Tenant Entries",
    description="Returns a paginated list of tenant waitlist entries with all preference details.",
)
async def list_tenant_entries(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> AdminEntriesListResponse:
    total, entries = await WaitlistService.list_entries(
        db, user_type="tenant", page=page, page_size=page_size
    )
    return AdminEntriesListResponse(
        total=total,
        page=page,
        page_size=page_size,
        entries=[WaitlistEntryDetail.model_validate(e) for e in entries],
    )


@router.get(
    "/entries/agent",
    response_model=AdminEntriesListResponse,
    summary="List Agent Entries",
    description="Returns a paginated list of agent waitlist entries with operational areas and listing volumes.",
)
async def list_agent_entries(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> AdminEntriesListResponse:
    total, entries = await WaitlistService.list_entries(
        db, user_type="agent", page=page, page_size=page_size
    )
    return AdminEntriesListResponse(
        total=total,
        page=page,
        page_size=page_size,
        entries=[WaitlistEntryDetail.model_validate(e) for e in entries],
    )


@router.get(
    "/export",
    summary="Export Waitlist CSV",
    description="Streams a CSV export of waitlist entries. Use '?type=tenant' or '?type=agent' to download them separately, and '?emails_only=true' for bulk mailer tools.",
    responses={
        200: {
            "description": "Streamed CSV file",
            "content": {"text/csv": {}},
        },
        401: {"description": "Missing Authorization header"},
        403: {"description": "Invalid administrative credentials"},
    },
)
async def export_waitlist_csv(
    user_type: Optional[Literal["tenant", "agent"]] = Query(
        default=None,
        alias="type",
        description="Filter export by 'tenant' or 'agent'. If omitted, exports all entries.",
    ),
    emails_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Streams CSV export of waitlist records.
    When user_type is set: streams only tenants or only agents.
    When emails_only=True: streams email, name, type, created_at for bulk mailers.
    Neutralizes spreadsheet formula injection risks.
    """
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    type_suffix = f"_{user_type}s" if user_type else ""
    email_suffix = "_emails" if emails_only else ""
    filename = f"waitlist{type_suffix}{email_suffix}_{current_date}.csv"

    audit_logger.info(
        "Admin CSV export initiated",
        extra={
            "event": "csv_export_performed",
            "user_type": user_type,
            "emails_only": emails_only,
            "status": "success",
        },
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "text/csv; charset=utf-8",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    return StreamingResponse(
        CSVExportService.stream_waitlist_csv(
            db, emails_only=emails_only, user_type=user_type
        ),
        media_type="text/csv",
        headers=headers,
    )


@router.get(
    "/stats",
    response_model=AdminStatsOut,
    summary="Waitlist Statistics",
    description="Returns aggregate statistics on waitlist registrations without exposing individual emails.",
)
async def get_waitlist_stats(
    db: AsyncSession = Depends(get_db),
) -> AdminStatsOut:
    count, tenants, agents, latest_signup = await WaitlistService.get_stats(db)
    return AdminStatsOut(
        total_entries=count,
        tenant_count=tenants,
        agent_count=agents,
        latest_signup_at=latest_signup,
    )


@router.delete(
    "/{entry_id}",
    response_model=AdminDeleteResponse,
    summary="Delete Waitlist Record",
    description="Deletes a waitlist entry by UUID. Protected admin endpoint.",
    responses={
        200: {"description": "Record successfully deleted"},
        404: {"description": "Record not found"},
    },
)
async def delete_waitlist_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AdminDeleteResponse:
    deleted = await WaitlistService.delete_entry(db, entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist record not found.",
        )

    return AdminDeleteResponse(
        success=True,
        message="Waitlist record deleted successfully.",
        deleted_id=entry_id,
    )
