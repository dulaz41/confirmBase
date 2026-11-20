from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry
from app.schemas.waitlist import AgentWaitlistCreate, TenantWaitlistCreate, WaitlistCreate

logger = logging.getLogger("waitlist.service")
audit_logger = logging.getLogger("waitlist.audit")


class RegistrationResult:
    """Encapsulates the outcome of a waitlist registration or update."""

    def __init__(
        self,
        status: str,  # "created" | "updated" | "duplicate"
        message: str,
        position: int,
        email_newly_added: bool = False,
    ):
        self.status = status
        self.message = message
        self.position = position
        self.email_newly_added = email_newly_added

    @property
    def is_new(self) -> bool:
        return self.status == "created"

    @property
    def is_updated(self) -> bool:
        return self.status == "updated"

    @property
    def is_duplicate(self) -> bool:
        return self.status == "duplicate"

    def __iter__(self):
        # Enables tuple unpacking: is_new, message, position = result
        return iter((self.is_new, self.message, self.position))

    def __getitem__(self, index):
        return (self.is_new, self.message, self.position)[index]

    def __repr__(self) -> str:
        return f"<RegistrationResult status={self.status} position={self.position} message='{self.message}'>"


class WaitlistService:
    @staticmethod
    async def register_entry(
        db: AsyncSession, payload: WaitlistCreate | TenantWaitlistCreate | AgentWaitlistCreate
    ) -> RegistrationResult:
        """
        Registers a tenant or agent to the ConfirmBase early list, or enriches
        an existing entry with step-2 matching preferences.

        Returns:
            RegistrationResult:
            - status == "created": newly registered entry (201).
            - status == "updated": existing entry updated with step-2 fields (200).
            - status == "duplicate": existing entry with no new fields to update (409 / 200).
        """
        # Bot honeypot protection: if honeypot was populated, pretend success without storing
        if (payload.website and payload.website.strip()) or (payload.hp_field and payload.hp_field.strip()):
            logger.warning("Honeypot field was filled; silently ignoring bot submission.")
            return RegistrationResult(
                status="created",
                message="You have successfully joined the waitlist.",
                position=1,
            )

        phone_normalized = payload.normalized_phone
        email_normalized = payload.normalized_email

        # Deduplication lookup: email first, then phone
        existing_entry: Optional[WaitlistEntry] = None

        if email_normalized:
            stmt_email = select(WaitlistEntry).where(
                WaitlistEntry.email_normalized == email_normalized,
                WaitlistEntry.type == payload.type,
            )
            res_email = await db.execute(stmt_email)
            existing_entry = res_email.scalar_one_or_none()

        if existing_entry is None and phone_normalized:
            stmt_phone = select(WaitlistEntry).where(
                WaitlistEntry.phone_normalized == phone_normalized,
                WaitlistEntry.type == payload.type,
            )
            res_phone = await db.execute(stmt_phone)
            existing_entry = res_phone.scalar_one_or_none()

        # If existing entry found, handle step-2 enrichment / idempotent update
        if existing_entry is not None:
            stmt_pos = select(func.count(WaitlistEntry.id)).where(
                WaitlistEntry.created_at <= existing_entry.created_at
            )
            pos_res = await db.execute(stmt_pos)
            pos = pos_res.scalar_one() or 1

            updated = False
            email_newly_added = False

            # Check phone
            if "phone" in payload.model_fields_set and payload.phone is not None:
                if existing_entry.phone_normalized != phone_normalized:
                    existing_entry.phone = payload.phone
                    existing_entry.phone_normalized = phone_normalized
                    updated = True

            # Check email
            if "email" in payload.model_fields_set and payload.email is not None:
                if existing_entry.email_normalized != email_normalized:
                    if not existing_entry.email_normalized and email_normalized:
                        email_newly_added = True
                    existing_entry.email = payload.email
                    existing_entry.email_normalized = email_normalized
                    updated = True

            # Check updatable profile / preference fields
            for field_name in (
                "name",
                "areas",
                "budget",
                "timing",
                "redflags",
                "taste",
                "role",
                "listings",
            ):
                if field_name in payload.model_fields_set:
                    new_val = getattr(payload, field_name, None)
                    if new_val is not None:
                        curr_val = getattr(existing_entry, field_name, None)
                        curr_str = curr_val.strip() if isinstance(curr_val, str) else curr_val
                        new_str = new_val.strip() if isinstance(new_val, str) else new_val
                        if curr_str != new_str:
                            setattr(existing_entry, field_name, new_val)
                            updated = True

            if updated:
                if "submitted_at" in payload.model_fields_set and payload.submitted_at is not None:
                    existing_entry.submitted_at = payload.submitted_at
                try:
                    await db.commit()
                    await db.refresh(existing_entry)
                    logger.info(
                        f"Existing ConfirmBase entry updated [type={payload.type}, id={existing_entry.id}, phone={phone_normalized or existing_entry.phone_normalized}]"
                    )
                    return RegistrationResult(
                        status="updated",
                        message="Your preferences have been updated.",
                        position=pos,
                        email_newly_added=email_newly_added,
                    )
                except IntegrityError:
                    await db.rollback()
                    logger.warning("Integrity error updating existing waitlist entry duplicate")
                    return RegistrationResult(
                        status="duplicate",
                        message="This entry is already on the waitlist.",
                        position=pos,
                    )

            # No fields needed updating -> duplicate
            msg = (
                "This WhatsApp number is already on the waitlist."
                if phone_normalized
                else "This email is already on the waitlist."
            )
            return RegistrationResult(
                status="duplicate",
                message=msg,
                position=pos,
            )

        # 3. Insert new waitlist entry
        entry = WaitlistEntry(
            type=payload.type,
            name=payload.name,
            phone=payload.phone,
            phone_normalized=phone_normalized,
            email=payload.email,
            email_normalized=email_normalized,
            areas=payload.areas,
            budget=payload.budget,
            timing=payload.timing,
            redflags=payload.redflags,
            taste=payload.taste,
            role=payload.role,
            listings=payload.listings,
            submitted_at=payload.submitted_at,
            status="pending",
        )
        db.add(entry)

        try:
            await db.commit()
            await db.refresh(entry)
            logger.info(
                f"New ConfirmBase entry registered successfully [type={payload.type}, name={payload.name}, phone={phone_normalized}]"
            )
            stmt_count = select(func.count(WaitlistEntry.id))
            res_count = await db.execute(stmt_count)
            position = res_count.scalar_one() or 1
            return RegistrationResult(
                status="created",
                message="You have successfully joined the waitlist.",
                position=position,
            )
        except IntegrityError:
            await db.rollback()
            logger.info("Concurrent registration duplicate caught by unique constraint")
            if phone_normalized:
                msg = "This WhatsApp number is already on the waitlist."
            else:
                msg = "This email is already on the waitlist."
            return RegistrationResult(
                status="duplicate",
                message=msg,
                position=1,
            )

    # Backward compatibility alias
    register_email = register_entry

    @staticmethod
    async def delete_entry(
        db: AsyncSession, entry_id: uuid.UUID
    ) -> bool:
        """
        Administratively deletes an entry by UUID.
        Returns True if deleted, False if entry did not exist.
        """
        stmt = delete(WaitlistEntry).where(WaitlistEntry.id == entry_id)
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount > 0:
            audit_logger.info(
                "Waitlist record deleted",
                extra={
                    "event": "waitlist_record_deleted",
                    "status": "success",
                    "record_id": str(entry_id),
                },
            )
            return True
        return False

    @staticmethod
    async def unsubscribe_by_email(
        db: AsyncSession, email: str
    ) -> bool:
        """
        Marks all waitlist records for a given email as unsubscribed,
        revoking marketing consent in compliance with NDPA 2023.
        """
        normalized = email.strip().lower()
        stmt = (
            update(WaitlistEntry)
            .where(WaitlistEntry.email_normalized == normalized)
            .values(
                unsubscribed_at=datetime.now(timezone.utc),
                marketing_consent=False,
            )
        )
        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount > 0:
            audit_logger.info(
                "Waitlist email unsubscribed",
                extra={
                    "event": "waitlist_email_unsubscribed",
                    "status": "success",
                    "email": normalized,
                },
            )
            return True
        return False

    @staticmethod
    async def get_stats(db: AsyncSession) -> Tuple[int, int, int, Optional[object]]:
        """Calculates total count, tenant count, agent count, and latest registration timestamp."""
        stmt = select(
            func.count(WaitlistEntry.id),
            func.coalesce(func.sum(case((WaitlistEntry.type == "tenant", 1), else_=0)), 0),
            func.coalesce(func.sum(case((WaitlistEntry.type == "agent", 1), else_=0)), 0),
            func.max(WaitlistEntry.created_at),
        )
        result = await db.execute(stmt)
        total, tenants, agents, latest = result.one()
        return total or 0, int(tenants or 0), int(agents or 0), latest

    @staticmethod
    async def list_entries(
        db: AsyncSession,
        user_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[int, list[WaitlistEntry]]:
        """
        Lists waitlist entries with optional type filtering ('tenant' or 'agent') and pagination.
        """
        count_stmt = select(func.count(WaitlistEntry.id))
        stmt = select(WaitlistEntry).order_by(WaitlistEntry.created_at.desc())

        if user_type:
            count_stmt = count_stmt.where(WaitlistEntry.type == user_type)
            stmt = stmt.where(WaitlistEntry.type == user_type)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one() or 0

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        res = await db.execute(stmt)
        entries = list(res.scalars().all())

        return total, entries

