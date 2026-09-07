from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class NotificationResult:
    """Result returned by a notification provider dispatch."""

    success: bool
    provider_message_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


class BaseNotificationProvider(ABC):
    """Abstract base class for all notification channel providers."""

    channel_name: str = ""

    @abstractmethod
    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> NotificationResult:
        """
        Send a notification to recipient.

        :param recipient: destination address (email, phone, telegram chat_id).
        :param subject: subject or title of message.
        :param body: rendered message body (text or HTML).
        :param context: optional context dictionary used in rendering.
        :return: NotificationResult instance.
        """
        raise NotImplementedError

    def is_configured(self) -> bool:
        """Check whether this provider has all required credentials configured."""
        return True
