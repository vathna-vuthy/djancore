import contextvars
from typing import Any

# Context variable to hold the active Organization for the current request thread/task
_current_organization: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "current_organization", default=None
)


def set_current_organization(organization: Any | None) -> None:
    """Set the active organization for the current execution thread/task."""
    _current_organization.set(organization)


def clear_organization_context() -> None:
    """Reset the active organization context variable back to None."""
    _current_organization.set(None)


def get_current_organization() -> Any | None:
    """Retrieve the active organization from contextvars."""
    return _current_organization.get()
