from typing import Any, Self

from rest_framework import status
from rest_framework.response import Response


class ApiResponse(Response):
    """
    Standardized API response envelope for all REST endpoints in Djancore.

    Envelope Structure:
    {
        "success": bool,
        "message": str (optional),
        "data": Any (optional),
        "meta": dict (optional),
        "errors": Any (optional, on error),
        "code": str (optional, on error)
    }
    """

    def __init__(
        self,
        data: Any = None,
        message: str = "",
        success: bool = True,
        status: int = status.HTTP_200_OK,
        meta: dict[str, Any] | None = None,
        errors: Any = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        payload: dict[str, Any] = {
            "success": success,
        }
        if message:
            payload["message"] = message
        if data is not None:
            payload["data"] = data
        if meta is not None:
            payload["meta"] = meta
        if errors is not None:
            payload["errors"] = errors
        if code is not None:
            payload["code"] = code

        super().__init__(data=payload, status=status, headers=headers, **kwargs)

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "",
        meta: dict[str, Any] | None = None,
        status: int = status.HTTP_200_OK,
        headers: dict[str, str] | None = None,
    ) -> Self:
        """Construct a successful 200 OK API response."""
        return cls(
            data=data,
            message=message,
            success=True,
            status=status,
            meta=meta,
            headers=headers,
        )

    @classmethod
    def created(
        cls,
        data: Any = None,
        message: str = "Created successfully.",
        meta: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Self:
        """Construct a 201 Created API response."""
        return cls(
            data=data,
            message=message,
            success=True,
            status=status.HTTP_201_CREATED,
            meta=meta,
            headers=headers,
        )

    @classmethod
    def error(
        cls,
        message: str = "An error occurred.",
        errors: Any = None,
        code: str | None = None,
        status: int = status.HTTP_400_BAD_REQUEST,
        headers: dict[str, str] | None = None,
    ) -> Self:
        """Construct an error API response."""
        return cls(
            message=message,
            success=False,
            status=status,
            errors=errors,
            code=code,
            headers=headers,
        )

    @classmethod
    def not_found(
        cls,
        message: str = "Resource not found.",
        code: str = "NOT_FOUND",
        headers: dict[str, str] | None = None,
    ) -> Self:
        """Construct a 404 Not Found API response."""
        return cls.error(
            message=message,
            code=code,
            status=status.HTTP_404_NOT_FOUND,
            headers=headers,
        )

    @classmethod
    def forbidden(
        cls,
        message: str = "Permission denied.",
        code: str = "FORBIDDEN",
        headers: dict[str, str] | None = None,
    ) -> Self:
        """Construct a 403 Forbidden API response."""
        return cls.error(
            message=message,
            code=code,
            status=status.HTTP_403_FORBIDDEN,
            headers=headers,
        )

    @classmethod
    def unauthorized(
        cls,
        message: str = "Authentication credentials were not provided or are invalid.",
        code: str = "UNAUTHORIZED",
        headers: dict[str, str] | None = None,
    ) -> Self:
        """Construct a 401 Unauthorized API response."""
        return cls.error(
            message=message,
            code=code,
            status=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
        )
