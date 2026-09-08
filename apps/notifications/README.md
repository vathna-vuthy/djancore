# Multi-Channel Notifications & Scheduling (`apps.notifications`)

The `apps.notifications` package delivers a modular multi-channel notification dispatch system with dynamic templating, scheduled delivery, retry engines, background workers, and audit tracking.

---

## Architecture & Providers

### Provider Registry (`apps.notifications.providers`)
- **`BaseNotificationProvider`**: Abstract interface for notification dispatchers (`send(recipient, subject, body, **kwargs)`).
- **`EmailProvider`**: Multipart HTML + plaintext fallback with `django.core.mail` and local `smtp4dev` integration.
- **`TelegramProvider`**: Direct dispatch via Telegram Bot API with Markdown/HTML formatting.
- **`ProviderRegistry`**: Dynamic registration of custom providers (e.g. SMS, Slack, WebPush).

### Notification Templates (`NotificationTemplate`)
- Reusable templates supporting Jinja2/Django variable interpolation (`{{ username }}`, `{{ amount }}`).
- Multi-channel content variants.

### Scheduled Notifications Engine
- Support for delayed or scheduled delivery (`scheduled_for`).
- Lifecycle management: `/cancel/`, `/reschedule/`, `/retry/`.
- **Concurrency-safe background worker** with `select_for_update(skip_locked=True)`.

---

## Background Notification Worker

Run the worker daemon or cron task:

```bash
# Single execution run
uv run python manage.py process_scheduled_notifications

# Continuous background daemon (polls every 10 seconds)
uv run python manage.py process_scheduled_notifications --daemon --interval 10
```

---

## Python Dispatch Usage

```python
from apps.notifications.services import NotificationService

# Direct dispatch
NotificationService.send(
    provider_name="email",
    recipient="customer@example.com",
    subject="Welcome to Djancore",
    body="Your account is now ready.",
    user=user,
)

# Template dispatch with scheduling
NotificationService.send_template(
    template_code="WELCOME_EMAIL",
    recipient="customer@example.com",
    context={"username": "Alice", "plan": "Pro"},
    scheduled_for=timezone.now() + timedelta(hours=1),
)
```

---

## API Endpoints (`/api/v1/notifications/`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/notifications/send/` | Send direct or scheduled notification |
| `POST` | `/api/v1/notifications/send-template/` | Send template-based notification |
| `GET` | `/api/v1/notifications/providers/` | List available channel providers & status |
| `GET/POST` | `/api/v1/notifications/templates/` | Manage notification templates (Staff) |
| `GET/PUT/PATCH/DEL` | `/api/v1/notifications/templates/{id}/` | Notification template details & soft-delete |
| `GET` | `/api/v1/notifications/logs/` | List delivery logs (users see theirs, staff sees all) |
| `GET` | `/api/v1/notifications/logs/{id}/` | Inspect delivery attempt & error diagnostics |
| `POST` | `/api/v1/notifications/logs/{id}/cancel/` | Cancel pending scheduled notification |
| `POST` | `/api/v1/notifications/logs/{id}/reschedule/` | Reschedule pending notification |
| `POST` | `/api/v1/notifications/logs/{id}/retry/` | Retry failed/cancelled notification |
