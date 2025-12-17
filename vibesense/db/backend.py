"""Database backend abstraction with a default SQLite implementation.

The public db facade delegates to the configured backend so we can swap
storage (e.g., Postgres) via configuration later without touching callers.
"""

import os
from typing import Any, Protocol, runtime_checkable

from . import context_store, preferences_store
from .models import AgentContext, UserPreferences


@runtime_checkable
class DatabaseBackend(Protocol):
    """Minimal contract for storing and fetching user state."""

    def get_context(self, user_id: str) -> AgentContext: ...

    def set_context(self, user_id: str, context: AgentContext) -> None: ...

    def get_preferences(self, user_id: str) -> UserPreferences: ...

    def set_preferences(self, user_id: str, preferences: UserPreferences | dict[str, Any]) -> UserPreferences: ...

    def get_user_profile(self, user_id: str) -> dict[str, Any]: ...


class SQLiteBackend:
    """Thin adapter over the existing SQLite helpers."""

    def get_context(self, user_id: str) -> AgentContext:
        return context_store.get_context(user_id)

    def set_context(self, user_id: str, context: AgentContext) -> None:
        context_store.set_context(user_id, context)

    def get_preferences(self, user_id: str) -> UserPreferences:
        return preferences_store.get_preferences(user_id)

    def set_preferences(self, user_id: str, preferences: UserPreferences | dict[str, Any]) -> UserPreferences:
        return preferences_store.set_preferences(user_id, preferences)

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        return {
            "context": self.get_context(user_id).to_dict(),
            "preferences": self.get_preferences(user_id).to_dict(),
        }


_backend: DatabaseBackend | None = None


# def configure_backend(backend: DatabaseBackend) -> None:
#     """Override the current backend (useful for tests or future adapters)."""
#
#     global _backend
#     _backend = backend


def _default_backend_name() -> str:
    return os.getenv("VIBE_SENSE_BACKEND", "sqlite").lower()


def get_backend(name: str | None = None) -> DatabaseBackend:
    global _backend
    if _backend is not None:
        return _backend

    backend_name = name or _default_backend_name()
    if backend_name == "sqlite":
        _backend = SQLiteBackend()
        return _backend

    raise ValueError(f"Unsupported database backend: {backend_name}")


__all__ = [
    "DatabaseBackend",
    "SQLiteBackend",
    "get_backend",
]
