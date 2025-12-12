"""High-level helpers to aggregate context + preferences."""

from __future__ import annotations

from typing import Any, Dict

from vibesense.db.backend import get_backend
from vibesense.db.models import AgentContext, UserPreferences


def get_user_profile(user_id: str) -> Dict[str, Any]:
    """Fetch aggregated state/preferences for agent tools."""
    return get_backend().get_user_profile(user_id)


def get_context(user_id: str) -> AgentContext:
    return get_backend().get_context(user_id)


def set_context(user_id: str, context: AgentContext) -> None:
    get_backend().set_context(user_id, context)


def get_preferences(user_id: str) -> UserPreferences:
    return get_backend().get_preferences(user_id)


def set_preferences(user_id: str, preferences: UserPreferences | Dict[str, Any]) -> UserPreferences:
    return get_backend().set_preferences(user_id, preferences)


__all__ = [
    "AgentContext",
    "UserPreferences",
    "get_context",
    "set_context",
    "get_preferences",
    "set_preferences",
    "get_user_profile",
]
