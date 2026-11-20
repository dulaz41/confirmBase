from __future__ import annotations

import logging
import httpx
from app.core.config import settings
from app.services.email.base import BaseEmailProvider

logger = logging.getLogger("waitlist.email.sendgrid")


class SendGridEmailProvider(BaseEmailProvider):
    """
    Transactional email delivery via the Twilio SendGrid v3 Mail Send API.
    Docs: https://docs.sendgrid.com/api-reference/mail-send/mail-send
    """

    API_URL = "https://api.sendgrid.com/v3/mail/send"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        api_key = settings.SENDGRID_API_KEY
        if not api_key:
            raise ValueError("SENDGRID_API_KEY environment variable is not configured.")

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {
                "email": settings.EMAIL_FROM_ADDRESS,
                "name": settings.EMAIL_FROM_NAME,
            },
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.API_URL, json=payload, headers=headers)
            if response.status_code not in (200, 202):
                logger.error(f"SendGrid API error {response.status_code}: {response.text}")
                raise RuntimeError(f"SendGrid delivery failed with status {response.status_code}")

        logger.info("Email successfully dispatched via SendGrid API")
        return True
