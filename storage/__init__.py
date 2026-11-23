"""Public, lazily imported interfaces for the CaspianX Storage package.

Public exports are resolved on first access to avoid import-time side effects.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ConversationRepository",
    "EventStore",
    "ObservationCache",
    "SessionLeaseRepository",
    "SessionRepository",
]

_EXPORTS = {
    "ConversationRepository": "conversation_repository",
    "EventStore": "event_store",
    "ObservationCache": "observation_cache",
    "SessionLeaseRepository": "session_lease",
    "SessionRepository": "repositories",
}


def __getattr__(name: str) -> Any:
    """Resolve an explicitly exported symbol on first access.

    Args:
        name: Name of the requested public export.

    Returns:
        The symbol defined by the corresponding package submodule.

    Raises:
        AttributeError: If the requested name is not public.

    """
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
