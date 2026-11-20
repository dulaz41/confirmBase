from __future__ import annotations

import logging
from app.services.email.base import BaseEmailProvider

logger = logging.getLogger("waitlist.email.console")


class ConsoleEmailProvider(BaseEmailProvider):
    """
    Console email provider that logs outgoing emails to the application logger.
    Useful for local development, staging environments, and integration tests.
    """

    async def send_email(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        logger.info(
            f"[EMAIL CONSOLE] Sent confirmation email to {to_email} with subject '{subject}'"
        )
        return True
