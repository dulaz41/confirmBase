from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmailProvider(ABC):
    """Abstract interface for transactional email delivery backends."""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        """
        Sends an email message to the specified recipient.
        Returns True on success, or raises an Exception / returns False on failure.
        """
        pass
