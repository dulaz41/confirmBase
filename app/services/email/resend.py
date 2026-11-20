from __future__ import annotations

import logging
import httpx
from app.core.config import settings
from app.services.email.base import BaseEmailProvider

logger = logging.getLogger("waitlist.email.resend")


class ResendEmailProvider(BaseEmailProvider):
    """
    Modern transactional email delivery via the Resend HTTP API.
    Docs: https://resend.com/docs/api-reference/emails/send-email
    """

    API_URL = "https://api.resend.com/emails"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        api_key = settings.RESEND_API_KEY
        if not api_key:
            raise ValueError("RESEND_API_KEY environment variable is not configured.")

        from_header = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
        payload = {
            "from": from_header,
            "to": [to_email],
            "subject": subject,
            "text": text_content,
            "html": html_content,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.API_URL, json=payload, headers=headers)
            if response.status_code not in (200, 201):
                logger.error(f"Resend API error {response.status_code}: {response.text}")
                raise RuntimeError(f"Resend delivery failed with status {response.status_code}")

        logger.info("Email successfully dispatched via Resend API")
        return True
