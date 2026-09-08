# Throttling & Abuse Prevention (`apps.throttling`)

The `apps.throttling` package provides high-performance, multi-dimensional dynamic rate limiting, token bucket burst allowances, sliding window counters, and IP blocklist defense backed by Django's cache framework (`CACHES['default']`).

---

## Core Features

1. **Sliding Window Counter Algorithm (`SlidingWindowRateLimiter`)**:
   - Rolling sub-second precision rate calculation eliminating fixed-window boundary spike vulnerabilities.
   - Works natively with any Django cache backend (`LocMemCache`, `RedisCache`).
2. **Multi-Dimensional Scope Dimensions**:
   - **`IP`**: Per client IP address (ideal for public / auth routes).
   - **`USER`**: Per authenticated user account.
   - **`ORGANIZATION`**: Per multi-tenant workspace quota.
   - **`API_KEY`**: Per developer API key limit.
   - **`GLOBAL`**: Across entire platform traffic.
3. **Database-Driven Dynamic Rules (`ThrottlingRule`)**:
   - Adjust rates, periods, burst limits, and URL regex/wildcard paths (`path_pattern`) at runtime with zero redeployment.
   - Zero-latency caching layer with automatic admin invalidation.
4. **IP Blacklist & Abuse Defense (`IPBlocklist`)**:
   - Early-drop blocked IPs in `ThrottlingMiddleware` with HTTP 403 `IP_BLOCKED`.
   - Supports permanent bans or automated timed expirations.
5. **IETF Draft Standard Response Headers**:
   - `RateLimit-Limit`: Maximum permitted requests.
   - `RateLimit-Remaining`: Remaining requests in rolling window.
   - `RateLimit-Reset`: Seconds until window reset.
   - `Retry-After`: Seconds to wait when throttled (HTTP 429).

---

## API Endpoints (`/api/v1/throttling/`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/throttling/usage/` | Inspect current rate limit quota usage and remaining allowance | No |
| `GET/POST` | `/api/v1/throttling/rules/` | List and create dynamic rate limiting rules | Yes (Admin) |
| `GET/PATCH/DEL` | `/api/v1/throttling/rules/{id}/` | Inspect, update, or soft-delete rate limit rule | Yes (Admin) |
| `POST` | `/api/v1/throttling/rules/{id}/restore/` | Restore soft-deleted throttling rule | Yes (Admin) |
| `GET/POST` | `/api/v1/throttling/blocklist/` | List and add IP addresses to blocklist | Yes (Admin) |
| `POST` | `/api/v1/throttling/blocklist/block/` | Quick block IP with optional duration expiration | Yes (Admin) |
| `POST` | `/api/v1/throttling/blocklist/{id}/unblock/` | Unblock IP address | Yes (Admin) |
