from typing import Any

from rest_framework import authentication, exceptions

from apps.api_keys.models import APIKey


def get_client_ip(request: Any) -> str | None:
    """Extract client IP from request headers or remote address."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authentication backend for Developer API Keys.

    Supports:
    - Header `X-API-Key: <key>`
    - Header `Authorization: Api-Key <key>`
    - Header `Authorization: ApiKey <key>`
    """

    keyword = "api-key"

    def authenticate_header(self, request: Any) -> str:
        return "Api-Key"

    def authenticate(self, request: Any) -> tuple[Any, APIKey] | None:
        raw_key = self.get_raw_key(request)
        if not raw_key:
            return None

        # Format: djc_{type}_{prefix}_{secret}
        parts = raw_key.split("_")
        if len(parts) < 4 or parts[0] != "djc":
            raise exceptions.AuthenticationFailed("Malformed API key format.")

        prefix = parts[2]

        try:
            api_key = APIKey.objects.select_related("user").get(
                prefix=prefix,
                is_deleted=False,
            )
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.") from None

        if not api_key.verify_key(raw_key):
            raise exceptions.AuthenticationFailed("Invalid API key.")

        if not api_key.is_active:
            raise exceptions.AuthenticationFailed("API key is inactive.")

        if api_key.is_expired:
            raise exceptions.AuthenticationFailed("API key has expired.")

        client_ip = get_client_ip(request)
        if not api_key.check_ip(client_ip):
            raise exceptions.PermissionDenied(
                "Client IP is not permitted for this API key."
            )

        if not api_key.user.is_active or api_key.user.is_deleted:
            raise exceptions.AuthenticationFailed("User account is inactive.")

        # Record usage audit metadata
        api_key.record_usage(client_ip)

        return api_key.user, api_key

    def get_raw_key(self, request: Any) -> str | None:
        """Extract raw key from headers."""
        # 1. Check X-API-Key header
        header_key = request.META.get("HTTP_X_API_KEY")
        if header_key:
            return header_key.strip()

        # 2. Check Authorization header
        auth_header = authentication.get_authorization_header(request).split()
        if not auth_header:
            return None

        if len(auth_header) == 2:
            prefix = auth_header[0].decode("utf-8", errors="ignore").lower()
            if prefix in ("api-key", "apikey"):
                try:
                    return auth_header[1].decode("utf-8").strip()
                except UnicodeError:
                    raise exceptions.AuthenticationFailed(
                        "Invalid API key encoding."
                    ) from None

        return None
