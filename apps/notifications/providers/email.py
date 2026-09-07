import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.notifications.providers.base import (
    BaseNotificationProvider,
    NotificationResult,
)
from apps.system_config.services import (
    get_bool_config,
    get_config,
    get_int_config,
)

logger = logging.getLogger(__name__)


class EmailNotificationProvider(BaseNotificationProvider):
    """Email notification provider leveraging dynamic SystemConfig and Django mail backends."""

    channel_name = "email"

    def get_mail_connection(self, **kwargs: Any):
        """Build Django email connection dynamically from SystemConfig or settings."""
        backend = kwargs.get(
            "backend",
            get_config(
                "EMAIL_BACKEND",
                default=getattr(
                    settings,
                    "EMAIL_BACKEND",
                    "django.core.mail.backends.smtp.EmailBackend",
                ),
            ),
        )
        host = kwargs.get(
            "host",
            get_config(
                "EMAIL_HOST",
                default=getattr(settings, "EMAIL_HOST", "localhost"),
            ),
        )
        port = kwargs.get(
            "port",
            get_int_config(
                "EMAIL_PORT",
                default=getattr(settings, "EMAIL_PORT", 25),
            ),
        )
        username = kwargs.get(
            "username",
            get_config(
                "EMAIL_HOST_USER",
                default=getattr(settings, "EMAIL_HOST_USER", ""),
            ),
        )
        password = kwargs.get(
            "password",
            get_config(
                "EMAIL_HOST_PASSWORD",
                default=getattr(settings, "EMAIL_HOST_PASSWORD", ""),
            ),
        )
        use_tls = kwargs.get(
            "use_tls",
            get_bool_config(
                "EMAIL_USE_TLS",
                default=getattr(settings, "EMAIL_USE_TLS", False),
            ),
        )
        use_ssl = kwargs.get(
            "use_ssl",
            get_bool_config(
                "EMAIL_USE_SSL",
                default=getattr(settings, "EMAIL_USE_SSL", False),
            ),
        )
        timeout = kwargs.get(
            "timeout",
            get_int_config(
                "EMAIL_TIMEOUT",
                default=getattr(settings, "EMAIL_TIMEOUT", 10),
            ),
        )

        return get_connection(
            backend=backend,
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=timeout,
        )

    def is_configured(self) -> bool:
        """Check whether email delivery is configured in SystemConfig or settings."""
        host = get_config("EMAIL_HOST", default=getattr(settings, "EMAIL_HOST", ""))
        backend = get_config(
            "EMAIL_BACKEND", default=getattr(settings, "EMAIL_BACKEND", "")
        )
        return bool(host or backend)

    def send(
        self,
        recipient: str,
        subject: str,
        body: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> NotificationResult:
        from_email = kwargs.get(
            "from_email",
            get_config(
                "DEFAULT_FROM_EMAIL",
                default=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
            ),
        )
        is_html = kwargs.get("is_html", "<html" in body.lower() or "<p" in body.lower())
        connection = self.get_mail_connection(**kwargs)

        try:
            if is_html:
                # Send multipart email (plain text fallback + HTML body)
                plain_text = kwargs.get("plain_text", body)
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_text,
                    from_email=from_email,
                    to=[recipient],
                    connection=connection,
                )
                msg.attach_alternative(body, "text/html")
                sent_count = msg.send(fail_silently=False)
            else:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[recipient],
                    connection=connection,
                )
                sent_count = msg.send(fail_silently=False)

            if sent_count > 0:
                return NotificationResult(
                    success=True,
                    provider_message_id=f"email-{recipient}",
                )
            return NotificationResult(
                success=False,
                error="Email backend returned 0 sent messages.",
            )
        except Exception as e:
            logger.exception("Failed to send email to %s: %s", recipient, e)
            return NotificationResult(
                success=False,
                error=str(e),
            )
