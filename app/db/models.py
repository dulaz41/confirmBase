from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    Uuid,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class WaitlistEntry(Base):
    """
    SQLAlchemy 2.x model representing a waitlist entry for ConfirmBase.
    Supports both tenant and agent registrations with phone-based and email deduplication.
    """

    __tablename__ = "waitlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    # Registration type: "tenant" or "agent"
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="tenant",
        index=True,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    phone_normalized: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    email_normalized: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    areas: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Tenant-specific fields
    budget: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    timing: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    redflags: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    taste: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Agent-specific fields
    role: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    listings: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Status, timestamps, and metadata
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    marketing_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    consent_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "phone_normalized",
            "type",
            name="uq_waitlist_entries_phone_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<WaitlistEntry id={self.id} type={self.type} phone={self.phone_normalized} status={self.status}>"
