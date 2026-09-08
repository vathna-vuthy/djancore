import contextvars
from typing import Any

# Context variables for tracking the executing request context across threads/tasks
_current_actor: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "current_actor", default=None
)
_current_actor_repr: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_actor_repr", default="System"
)
_current_ip: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_ip", default=None
)
_current_user_agent: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_user_agent", default=""
)
_current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_id", default=None
)


def set_audit_context(
    actor: Any | None = None,
    actor_repr: str = "System",
    ip_address: str | None = None,
    user_agent: str = "",
    request_id: str | None = None,
) -> None:
    """Set the audit context for the current execution thread/task."""
    _current_actor.set(actor)
    _current_actor_repr.set(actor_repr)
    _current_ip.set(ip_address)
    _current_user_agent.set(user_agent)
    _current_request_id.set(request_id)


def clear_audit_context() -> None:
    """Reset the audit context variables back to default."""
    _current_actor.set(None)
    _current_actor_repr.set("System")
    _current_ip.set(None)
    _current_user_agent.set("")
    _current_request_id.set(None)


def get_current_actor() -> Any | None:
    return _current_actor.get()


def get_current_actor_repr() -> str:
    return _current_actor_repr.get()


def get_current_ip() -> str | None:
    return _current_ip.get()


def get_current_user_agent() -> str:
    return _current_user_agent.get()


def get_current_request_id() -> str | None:
    return _current_request_id.get()
