from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import AsyncGenerator, Iterable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry

# Characters that trigger formula execution in spreadsheet software (Excel, LibreOffice, Google Sheets)
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str) -> str:
    """
    Sanitizes cell value to prevent CSV Formula Injection (DDE / CSV Injection).
    If the value begins with a formula trigger character (=, +, -, @, \\t, \\r),
    prepends a single quote "'" to neutralize execution in Excel / Google Sheets.
    """
    if not value:
        return ""
    if value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def format_utc_timestamp(dt: datetime | None) -> str:
    """Formats datetime to consistent ISO 8601 UTC string: YYYY-MM-DDTHH:MM:SSZ."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class CSVExportService:
    @staticmethod
    def generate_csv_row(row_data: Iterable[str]) -> str:
        """Encodes a single row of data into a standard RFC 4180 CSV line."""
        output = io.StringIO()
        writer = csv.writer(output, dialect="excel", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
        writer.writerow([sanitize_csv_cell(cell) for cell in row_data])
        return output.getvalue()

    @staticmethod
    async def stream_waitlist_csv(
        db: AsyncSession,
        emails_only: bool = False,
        user_type: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Asynchronously streams ConfirmBase waitlist records formatted as CSV.
        When user_type is specified ('tenant' or 'agent'): streams only records matching that type.
        When emails_only=True: exports only entries with valid emails (email,name,type,created_at) for bulk mailers.
        When emails_only=False: exports all fields for full administration.
        Memory efficient for large datasets.
        """
        if emails_only:
            # Yield header for bulk email tools (Mailchimp, Resend, Brevo, SendGrid)
            yield CSVExportService.generate_csv_row(["email", "name", "type", "created_at"])

            stmt = select(
                WaitlistEntry.email,
                WaitlistEntry.name,
                WaitlistEntry.type,
                WaitlistEntry.created_at,
            ).where(
                WaitlistEntry.email.is_not(None),
                WaitlistEntry.email != "",
            )
            if user_type:
                stmt = stmt.where(WaitlistEntry.type == user_type)
            stmt = stmt.order_by(WaitlistEntry.created_at.asc())

            result = await db.stream(stmt)
            async for row in result:
                email, name, entry_type, created_at = row
                formatted_date = format_utc_timestamp(created_at)
                yield CSVExportService.generate_csv_row([
                    email or "",
                    name or "",
                    entry_type or "",
                    formatted_date,
                ])
            return

        # Full export with all ConfirmBase fields
        yield CSVExportService.generate_csv_row([
            "id",
            "type",
            "name",
            "phone",
            "email",
            "areas",
            "budget",
            "timing",
            "redflags",
            "taste",
            "role",
            "listings",
            "status",
            "created_at",
        ])

        # Stream records ordered by creation timestamp
        stmt = select(
            WaitlistEntry.id,
            WaitlistEntry.type,
            WaitlistEntry.name,
            WaitlistEntry.phone,
            WaitlistEntry.email,
            WaitlistEntry.areas,
            WaitlistEntry.budget,
            WaitlistEntry.timing,
            WaitlistEntry.redflags,
            WaitlistEntry.taste,
            WaitlistEntry.role,
            WaitlistEntry.listings,
            WaitlistEntry.status,
            WaitlistEntry.created_at,
        )
        if user_type:
            stmt = stmt.where(WaitlistEntry.type == user_type)
        stmt = stmt.order_by(WaitlistEntry.created_at.asc())

        result = await db.stream(stmt)

        async for row in result:
            (
                entry_id,
                entry_type,
                name,
                phone,
                email,
                areas,
                budget,
                timing,
                redflags,
                taste,
                role,
                listings,
                entry_status,
                created_at,
            ) = row
            formatted_date = format_utc_timestamp(created_at)
            yield CSVExportService.generate_csv_row([
                str(entry_id),
                entry_type or "",
                name or "",
                phone or "",
                email or "",
                areas or "",
                budget or "",
                timing or "",
                redflags or "",
                taste or "",
                role or "",
                listings or "",
                entry_status or "",
                formatted_date,
            ])

    @staticmethod
    async def export_to_string(
        db: AsyncSession,
        emails_only: bool = False,
        user_type: Optional[str] = None,
    ) -> str:
        """Exports waitlist records to a single CSV string (useful for snapshots/tests)."""
        chunks = []
        async for chunk in CSVExportService.stream_waitlist_csv(
            db, emails_only=emails_only, user_type=user_type
        ):
            chunks.append(chunk)
        return "".join(chunks)
