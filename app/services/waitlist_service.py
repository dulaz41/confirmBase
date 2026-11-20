from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry
from app.schemas.waitlist import WaitlistCreate

logger = logging.getLogger("waitlist.service")
audit_logger = logging.getLogger("waitlist.audit")


class WaitlistService:
    @staticmethod
    async def register_entry(
        db: AsyncSession, payload: WaitlistCreate
    ) -> Tuple[bool, str, int]:
        """
        Registers a tenant or agent to the ConfirmBase early list.
        Returns:
            (is_new, message, position):
            - (True, "You have successfully joined the waitlist.", position) if newly registered.
            - (False, "already_on_list", position) if already exists.

        Handles duplicate prevention via phone_normalized and email_normalized.
        """
        # Bot honeypot protection: if honeypot was populated, pretend success without storing
        if (payload.website and payload.website.strip()) or (payload.hp_field and payload.hp_field.strip()):
            logger.warning("Honeypot field was filled; silently ignoring bot submission.")
            return True, "You have successfully joined the waitlist.", 1

        phone_normalized = payload.normalized_phone
        email_normalized = payload.normalized_email

        # 1. Check if phone already exists for this type
        if phone_normalized:
            stmt_phone = select(WaitlistEntry).where(
                WaitlistEntry.phone_normalized == phone_normalized,
                WaitlistEntry.type == payload.type,
            )
            res_phone = await db.execute(stmt_phone)
            existing_phone = res_phone.scalar_one_or_none()
            if existing_phone is not None:
                stmt_pos = select(func.count(WaitlistEntry.id)).where(
                    WaitlistEntry.created_at <= existing_phone.created_at
                )
                pos_res = await db.execute(stmt_pos)
                pos = pos_res.scalar_one() or 1
                return False, "This WhatsApp number is already on the waitlist.", pos

        # 2. Check if email already exists for this type (if provided)
        if email_normalized:
            stmt_email = select(WaitlistEntry).where(
                WaitlistEntry.email_normalized == email_normalized,
                WaitlistEntry.type == payload.type,
            )
            res_email = await db.execute(stmt_email)
            existing_email = res_email.scalar_one_or_none()
            if existing_email is not None:
                stmt_pos = select(func.count(WaitlistEntry.id)).where(
                    WaitlistEntry.created_at <= existing_email.created_at
                )
                pos_res = await db.execute(stmt_pos)
                pos = pos_res.scalar_one() or 1
                return False, "This email is already on the waitlist.", pos

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
            return True, "You have successfully joined the waitlist.", position
        except IntegrityError:
            await db.rollback()
            logger.info("Concurrent registration duplicate caught by unique constraint")
            if phone_normalized:
                return False, "This WhatsApp number is already on the waitlist.", 1
            return False, "This email is already on the waitlist.", 1

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

