from __future__ import annotations

import logging
from typing import Optional
from app.core.config import settings
from app.services.email.base import BaseEmailProvider
from app.services.email.console import ConsoleEmailProvider
from app.services.email.smtp import SMTPEmailProvider
from app.services.email.resend import ResendEmailProvider
from app.services.email.sendgrid import SendGridEmailProvider
from app.services.email.templates import (
    render_confirmation_html,
    render_confirmation_text,
)

logger = logging.getLogger("waitlist.email")


class EmailService:
    """
    High-level email service with pluggable provider backends.
    Allows easy switching between Console (dev/test), SMTP, Resend, and SendGrid.
    """

    def __init__(self, provider: Optional[BaseEmailProvider] = None):
        self._custom_provider = provider

    @property
    def provider(self) -> BaseEmailProvider:
        """Dynamically resolves the active email provider based on configuration."""
        if self._custom_provider:
            return self._custom_provider

        backend = settings.EMAIL_PROVIDER.lower().strip()
        if backend == "smtp":
            return SMTPEmailProvider()
        elif backend == "resend":
            return ResendEmailProvider()
        elif backend == "sendgrid":
            return SendGridEmailProvider()
        else:
            return ConsoleEmailProvider()

    async def send_confirmation_email(
        self,
        to_email: str,
        name: Optional[str] = None,
        user_type: str = "tenant",
        phone: Optional[str] = None,
        areas: Optional[str] = None,
        role: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> bool:
        """
        Sends waitlist confirmation email to recipient.
        Executes safely without raising exceptions to protect background task workers.
        """
        if not settings.SEND_CONFIRMATION_EMAIL:
            logger.debug(f"Email notifications disabled; skipping confirmation for {to_email}")
            return False

        try:
            if subject is None:
                if user_type == "agent":
                    subject = f"{settings.PRODUCT_NAME} Partner Invite Request Received 🏢"
                else:
                    subject = settings.EMAIL_SUBJECT or f"You're on the {settings.PRODUCT_NAME} early list! 🏠"

            text_content = render_confirmation_text(
                recipient_email=to_email,
                product_name=settings.PRODUCT_NAME,
                company_name=settings.COMPANY_NAME,
                user_type=user_type,
                name=name,
                phone=phone,
                areas=areas,
                role=role,
            )
            html_content = render_confirmation_html(
                recipient_email=to_email,
                product_name=settings.PRODUCT_NAME,
                company_name=settings.COMPANY_NAME,
                user_type=user_type,
                name=name,
                phone=phone,
                areas=areas,
                role=role,
            )

            success = await self.provider.send_email(
                to_email=to_email,
                subject=subject,
                text_content=text_content,
                html_content=html_content,
            )
            if success:
                logger.info(f"Confirmation email successfully sent via '{settings.EMAIL_PROVIDER}'")
            return success
        except Exception as exc:
            logger.error(
                f"Failed to send confirmation email via '{settings.EMAIL_PROVIDER}': {exc}",
                extra={
                    "event": "email_send_failure",
                    "provider": settings.EMAIL_PROVIDER,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            return False


email_service = EmailService()
