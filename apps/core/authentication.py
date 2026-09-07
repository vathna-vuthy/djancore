from rest_framework.authentication import TokenAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class BearerOrTokenAuthentication(TokenAuthentication):
    """
    Flexible token authentication supporting:
    - `Authorization: Token <token_key>`
    - `Authorization: Bearer <token_key>`
    - `Authorization: <token_key>` (raw 40-char token as entered in Swagger apiKey field)
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth:
            return None

        if len(auth) == 1:
            token_key = auth[0].decode("utf-8", errors="ignore")
            # If a raw 40-char token key is passed
            if len(token_key) == 40:
                return self.authenticate_credentials(token_key)
            return None

        if len(auth) == 2:
            prefix = auth[0].decode("utf-8", errors="ignore").lower()
            if prefix in ("token", "bearer"):
                try:
                    token_key = auth[1].decode("utf-8")
                except UnicodeError:
                    raise AuthenticationFailed(
                        "Invalid token header. Token string should not contain invalid characters."
                    ) from None
                return self.authenticate_credentials(token_key)

        return None
