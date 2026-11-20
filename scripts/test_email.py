"""
Quick CLI utility to verify email delivery configuration (Resend, SMTP, etc.).

Usage:
    .venv/bin/python scripts/test_email.py recipient@example.com
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure root waitlist package is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.email.service import email_service


async def main():
    recipient = sys.argv[1] if len(sys.argv) > 1 else None
    if not recipient:
        print("Error: Please provide a recipient email address.")
        print("Usage: .venv/bin/python scripts/test_email.py user@example.com")
        sys.exit(1)

    print("=" * 60)
    print("ConfirmBase Email Delivery Test")
    print("=" * 60)
    print(f"Provider:           {settings.EMAIL_PROVIDER}")
    print(f"From:               {settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>")
    print(f"Recipient:          {recipient}")
    print(f"Emails Enabled:     {settings.SEND_CONFIRMATION_EMAIL}")
    if settings.EMAIL_PROVIDER.lower() == "resend":
        key = settings.RESEND_API_KEY or ""
        masked_key = f"{key[:7]}...{key[-4:]}" if len(key) > 12 else "(not set)"
        print(f"Resend API Key:     {masked_key}")
    print("=" * 60)
    print("Sending test waitlist confirmation email...")

    try:
        success = await email_service.send_confirmation_email(
            to_email=recipient,
            name="Test User",
            user_type="tenant",
            phone="08012345678",
            areas="Arab road, Kubwa",
        )
        if success:
            print(f"SUCCESS: Email was accepted by {settings.EMAIL_PROVIDER} and dispatched to {recipient}!")
            print("Check your inbox (and spam/junk folder).")
        else:
            print("FAILED: send_confirmation_email returned False. Check application logs above.")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
