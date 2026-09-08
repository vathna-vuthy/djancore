import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from django.db.models import QuerySet
from django.utils import timezone

from apps.webhooks.models import WebhookDelivery, WebhookEndpoint, WebhookStatus

logger = logging.getLogger(__name__)


class WebhookSignature:
    """
    Cryptographic HMAC-SHA256 signature generator and validator for outbound webhooks.
    Follows modern header format: 't={timestamp},v1={signature}' to prevent replay attacks.
    """

    @classmethod
    def compute_signature(
        cls, payload_bytes: bytes, secret: str, timestamp: int
    ) -> str:
        """Compute HMAC-SHA256 signature for a raw payload at a given UNIX timestamp."""
        signed_payload = f"{timestamp}.".encode() + payload_bytes
        mac = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        return mac

    @classmethod
    def generate_header(cls, payload_bytes: bytes, secret: str) -> tuple[str, int]:
        """Generate the complete signature header string along with the timestamp used."""
        timestamp = int(time.time())
        signature = cls.compute_signature(payload_bytes, secret, timestamp)
        header_value = f"t={timestamp},v1={signature}"
        return header_value, timestamp

    @classmethod
    def verify_signature(
        cls,
        payload_bytes: bytes,
        secret: str,
        header_value: str,
        tolerance_seconds: int = 300,
    ) -> bool:
        """
        Verify an incoming or recorded webhook signature.
        Ensures signature matches and timestamp is within tolerance window.
        """
        try:
            parts = dict(item.split("=", 1) for item in header_value.split(","))
            timestamp_str = parts.get("t")
            signature = parts.get("v1")
            if not timestamp_str or not signature:
                return False

            timestamp = int(timestamp_str)
            current_time = int(time.time())

            # Check timestamp freshness to guard against replay attacks
            if abs(current_time - timestamp) > tolerance_seconds:
                return False

            expected_signature = cls.compute_signature(payload_bytes, secret, timestamp)
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False


class WebhookDispatcher:
    """
    Orchestration service for dispatching, signing, and executing outbound webhook deliveries.
    """

    @classmethod
    def dispatch_event(
        cls,
        event_type: str,
        payload: dict[str, Any],
        user: Any | None = None,
    ) -> list[WebhookDelivery]:
        """
        Dispatch an event to all matching, active webhook endpoints.
        If user is provided, filters to endpoints owned by that user.
        """
        query: QuerySet[WebhookEndpoint] = WebhookEndpoint.objects.filter(
            is_active=True
        )
        if user is not None:
            query = query.filter(user=user)

        deliveries: list[WebhookDelivery] = []
        for endpoint in query:
            if endpoint.matches_event(event_type):
                delivery = WebhookDelivery.objects.create(
                    endpoint=endpoint,
                    event_type=event_type,
                    payload=payload,
                    status=WebhookStatus.PENDING,
                )
                cls.deliver_webhook(delivery)
                deliveries.append(delivery)

        return deliveries

    @classmethod
    def ping_endpoint(cls, endpoint: WebhookEndpoint) -> WebhookDelivery:
        """Send a test ping event to verify endpoint connectivity."""
        delivery = WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type="system.ping",
            payload={
                "message": "Test webhook connectivity from Djancore",
                "endpoint_id": str(endpoint.id),
                "timestamp": timezone.now().isoformat(),
            },
            status=WebhookStatus.PENDING,
        )
        return cls.deliver_webhook(delivery)

    @classmethod
    def deliver_webhook(cls, delivery: WebhookDelivery) -> WebhookDelivery:
        """
        Execute the HTTP POST request to the webhook endpoint, sign the payload,
        and update the delivery record with response details.
        """
        endpoint = delivery.endpoint
        target_url = endpoint.target_url

        # Validate URL scheme
        parsed_url = urlparse(target_url)
        if parsed_url.scheme not in ("http", "https"):
            delivery.mark_failure(
                error_message=f"Invalid URL scheme: '{parsed_url.scheme}'. Must be http or https."
            )
            return delivery

        # Construct standard webhook envelope
        envelope = {
            "id": str(delivery.event_id),
            "event": delivery.event_type,
            "created_at": (delivery.created_at or timezone.now()).isoformat(),
            "data": delivery.payload,
        }
        body_bytes = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )

        # Generate HMAC-SHA256 signature header
        signature_header, _ = WebhookSignature.generate_header(
            body_bytes, endpoint.secret
        )

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Djancore-Webhook/1.0",
            "X-Djancore-Signature": signature_header,
            "X-Djancore-Event": delivery.event_type,
            "X-Djancore-Delivery": str(delivery.event_id),
        }

        # Merge custom endpoint headers if present
        if isinstance(endpoint.custom_headers, dict):
            for k, v in endpoint.custom_headers.items():
                headers[str(k)] = str(v)

        req = urllib.request.Request(
            target_url,
            data=body_bytes,
            headers=headers,
            method="POST",
        )

        start_time = time.monotonic()
        try:
            with urllib.request.urlopen(
                req, timeout=endpoint.timeout_seconds
            ) as response:
                duration_ms = int((time.monotonic() - start_time) * 1000)
                status_code = response.status
                resp_body = response.read().decode("utf-8", errors="replace")
                resp_headers = dict(response.headers.items())

                if 200 <= status_code < 300:
                    delivery.mark_success(
                        status_code=status_code,
                        headers=resp_headers,
                        body=resp_body,
                        duration_ms=duration_ms,
                    )
                else:
                    retry_delay = 2**delivery.attempt * 10
                    delivery.mark_failure(
                        error_message=f"HTTP status {status_code}",
                        status_code=status_code,
                        headers=resp_headers,
                        body=resp_body,
                        duration_ms=duration_ms,
                        retry_delay_seconds=retry_delay,
                    )
        except urllib.error.HTTPError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            err_headers = dict(exc.headers.items()) if exc.headers else {}
            retry_delay = 2**delivery.attempt * 10

            delivery.mark_failure(
                error_message=f"HTTP {exc.code}: {exc.reason}",
                status_code=exc.code,
                headers=err_headers,
                body=err_body,
                duration_ms=duration_ms,
                retry_delay_seconds=retry_delay,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            retry_delay = 2**delivery.attempt * 10
            error_reason = str(exc)

            delivery.mark_failure(
                error_message=f"Network error: {error_reason}",
                duration_ms=duration_ms,
                retry_delay_seconds=retry_delay,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.exception("Unexpected error during webhook delivery: %s", exc)
            delivery.mark_failure(
                error_message=f"Internal error: {exc}",
                duration_ms=duration_ms,
            )

        return delivery

    @classmethod
    def retry_delivery(cls, delivery: WebhookDelivery) -> WebhookDelivery:
        """Retry a previously failed webhook delivery."""
        delivery.attempt += 1
        delivery.status = WebhookStatus.PENDING
        delivery.save(update_fields=["attempt", "status", "updated_at"])
        return cls.deliver_webhook(delivery)
