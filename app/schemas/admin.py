from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AdminStatsOut(BaseModel):
    """Waitlist statistics summary for administrators."""
    total_entries: int
    tenant_count: int = 0
    agent_count: int = 0
    latest_signup_at: Optional[datetime] = None


class WaitlistEntryDetail(BaseModel):
    """Full detail of a waitlist entry with attached tenant or agent information."""
    id: uuid.UUID
    type: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    areas: Optional[str] = None
    # Tenant details
    budget: Optional[str] = None
    timing: Optional[str] = None
    redflags: Optional[str] = None
    taste: Optional[str] = None
    # Agent details
    role: Optional[str] = None
    listings: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminEntriesListResponse(BaseModel):
    """Paginated list of waitlist entries with attached profile details."""
    total: int
    page: int
    page_size: int
    entries: list[WaitlistEntryDetail]


class AdminDeleteResponse(BaseModel):
    """Response returned upon administrative record deletion."""
    success: bool
    message: str
    deleted_id: uuid.UUID

