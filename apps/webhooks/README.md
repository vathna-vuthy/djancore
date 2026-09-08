# Outbound Webhooks & Event Dispatcher (`apps.webhooks`)

The `apps.webhooks` package provides a robust outbound webhook dispatcher with HMAC-SHA256 payload signing, anti-replay timestamp protection, event pattern subscriptions, exponential retry backoff, latency tracking, and delivery logs.

---

## Core Features

1. **HMAC-SHA256 Cryptographic Signing**:
   - Outbound requests include header: `X-Djancore-Signature: t={timestamp},v1={hex_signature}`.
   - Prevents payload tampering and protects receiver endpoints against replay attacks.
2. **Flexible Event Subscriptions**:
   - Supports wildcard subscriptions (`*`), pattern namespaces (`user.*`, `invoice.*`), or exact event names (`user.created`).
3. **Automated Retry Backoff & Delivery Tracking (`WebhookDelivery`)**:
   - Records request headers, request payload, response status code, response body, latency in ms, and error details.
   - Automated exponential backoff retry scheduling for failed attempts.
4. **Interactive Connectivity Ping (`/ping/`)**:
   - Instant verification of endpoint reachability without triggering business events.
5. **Signing Secret Rotation (`/rotate-secret/`)**:
   - Rotate endpoint signing secret with one API call.

---

## Dispatching Webhooks in Python

```python
from apps.webhooks.services import WebhookDispatcher

# Dispatch an event to all matching active subscriber endpoints
WebhookDispatcher.dispatch(
    event="user.created",
    payload={
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
    },
)
```

---

## API Endpoints (`/api/v1/webhooks/`)

| Method | Endpoint | Description |
|---|---|---|
| `GET/POST` | `/api/v1/webhooks/endpoints/` | List and register webhook target endpoints |
| `GET/PATCH/DEL` | `/api/v1/webhooks/endpoints/{id}/` | Inspect, update, or soft-delete target endpoint |
| `POST` | `/api/v1/webhooks/endpoints/{id}/ping/` | Dispatch test ping to destination endpoint |
| `POST` | `/api/v1/webhooks/endpoints/{id}/rotate-secret/` | Rotate HMAC-SHA256 signing secret |
| `GET` | `/api/v1/webhooks/deliveries/` | List outbound delivery attempt audit logs |
| `GET` | `/api/v1/webhooks/deliveries/{id}/` | Inspect detailed delivery attempt with headers & body |
| `POST` | `/api/v1/webhooks/deliveries/{id}/retry/` | Manually retry a failed delivery attempt |
