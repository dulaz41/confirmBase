from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings
from app.services.email.base import BaseEmailProvider

logger = logging.getLogger("waitlist.email.smtp")


class SMTPEmailProvider(BaseEmailProvider):
    """
    Standard RFC SMTP provider using Python's built-in smtplib.
    Supports STARTTLS, SSL, and standard credential authentication.
    Runs synchronously in an asyncio thread pool to keep the event loop non-blocking.
    """

    def _send_sync(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM_ADDRESS))
        msg["To"] = to_email

        # Attach text fallback and HTML body
        part_text = MIMEText(text_content, "plain", "utf-8")
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        host = settings.SMTP_HOST
        port = settings.SMTP_PORT

        if settings.SMTP_SSL:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)

        try:
            if settings.SMTP_TLS and not settings.SMTP_SSL:
                server.starttls()

            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            server.send_message(msg)
            logger.info("Email successfully dispatched via SMTP")
            return True
        finally:
            try:
                server.quit()
            except Exception:
                pass

    async def send_email(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        return await asyncio.to_thread(
            self._send_sync,
            to_email,
            subject,
            text_content,
            html_content,
        )
