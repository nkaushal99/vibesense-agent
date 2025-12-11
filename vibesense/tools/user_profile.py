"""Tool to fetch user profile (context + preferences) from the DB."""

from __future__ import annotations

from typing import Any, Dict

from vibesense.db import get_user_profile


class UserProfileTool:
    name = "get_user_profile"
    description = "Fetch stored context + preferences for a user so music suggestions stay personalized."
    parameters_schema = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "ID of the user to load (defaults to 'default')."},
        },
        "required": ["user_id"],
    }

    def __call__(self, user_id: str) -> Dict[str, Any]:
        return get_user_profile(user_id or "default")
