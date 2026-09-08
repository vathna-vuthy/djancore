from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(
    exc: Exception, context: dict[str, Any]
) -> Response | None:
    """
    Transform all DRF and Django exceptions into the unified ApiResponse error envelope.

    Output format:
    {
        "success": false,
        "message": "Human readable error description",
        "code": "ERROR_CODE",
        "errors": { ... } | [ ... ] (optional detail)
    }
    """
    response = exception_handler(exc, context)

    if response is None:
        if isinstance(exc, Http404):
            response = Response(
                {"detail": "Resource not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        elif isinstance(exc, PermissionDenied):
            response = Response(
                {"detail": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN,
            )
        else:
            return None

    error_data = response.data
    message = "An error occurred."
    code = "ERROR"
    errors = None

    if isinstance(exc, exceptions.ValidationError):
        message = "Validation failed."
        code = "VALIDATION_ERROR"
        errors = error_data
    elif isinstance(
        exc, (exceptions.AuthenticationFailed, exceptions.NotAuthenticated)
    ):
        message = (
            error_data.get("detail", "Authentication required.")
            if isinstance(error_data, dict)
            else str(error_data)
        )
        code = "AUTHENTICATION_REQUIRED"
    elif isinstance(exc, exceptions.PermissionDenied):
        message = (
            error_data.get("detail", "Permission denied.")
            if isinstance(error_data, dict)
            else str(error_data)
        )
        code = "PERMISSION_DENIED"
    elif isinstance(exc, (exceptions.NotFound, Http404)):
        message = (
            error_data.get("detail", "Resource not found.")
            if isinstance(error_data, dict)
            else str(error_data)
        )
        code = "NOT_FOUND"
    elif isinstance(exc, exceptions.MethodNotAllowed):
        message = (
            error_data.get("detail", "Method not allowed.")
            if isinstance(error_data, dict)
            else str(error_data)
        )
        code = "METHOD_NOT_ALLOWED"
    elif isinstance(exc, exceptions.Throttled):
        message = (
            error_data.get("detail", "Request was throttled.")
            if isinstance(error_data, dict)
            else str(error_data)
        )
        code = "THROTTLED"
    elif isinstance(error_data, dict) and "detail" in error_data:
        message = str(error_data["detail"])
        code = getattr(exc, "default_code", "ERROR").upper()
    else:
        errors = error_data

    payload: dict[str, Any] = {
        "success": False,
        "message": message,
        "code": code,
    }
    if errors is not None:
        payload["errors"] = errors

    response.data = payload
    return response
