import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings

from apps.notifications.providers.base import (
    BaseNotificationProvider,
    NotificationResult,
)
from apps.system_config.services import get_config

logger = logging.getLogger(__name__)


class TelegramNotificationProvider(BaseNotificationProvider):
    """Telegram Bot notification provider using Telegram Bot API and SystemConfig."""

    channel_name = "telegram"

    def get_bot_token(self) -> str:
        """Retrieve bot token from SystemConfig or settings."""
        token = get_config("TELEGRAM_BOT_TOKEN")
        if not token:
            token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        return str(token).strip()

    def get_api_url(self) -> str:
        """Retrieve Telegram API base URL from SystemConfig or settings."""
        url = get_config("TELEGRAM_API_URL")
        if not url:
            url = getattr(settings, "TELEGRAM_API_URL", "https://api.telegram.org")
        return str(url).rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.get_bot_token())

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> NotificationResult:
        bot_token = self.get_bot_token()
        if not bot_token:
            return NotificationResult(
                success=False,
                error="TELEGRAM_BOT_TOKEN is not configured in SystemConfig or settings.",
            )

        chat_id = recipient.strip()
        # Compose message text with optional subject header
        text = f"*{subject}*\n\n{body}" if subject else body
        default_parse_mode = get_config("TELEGRAM_PARSE_MODE", default="HTML")
        parse_mode = kwargs.get("parse_mode", default_parse_mode)

        api_url = self.get_api_url()
        url = f"{api_url}/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": kwargs.get("disable_preview", True),
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                if resp_data.get("ok"):
                    msg_id = str(resp_data.get("result", {}).get("message_id", ""))
                    return NotificationResult(
                        success=True,
                        provider_message_id=msg_id,
                        raw_response=resp_data,
                    )
                return NotificationResult(
                    success=False,
                    error=resp_data.get("description", "Unknown Telegram error"),
                    raw_response=resp_data,
                )
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else str(e)
            logger.error("Telegram API HTTP error %d: %s", e.code, err_body)
            return NotificationResult(
                success=False,
                error=f"Telegram API HTTP error {e.code}: {err_body}",
            )
        except Exception as e:
            logger.exception("Failed to send Telegram message to %s: %s", chat_id, e)
            return NotificationResult(
                success=False,
                error=str(e),
            )
