"""Preferences/DB management API router."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from vibesense.app.heart_core import DEFAULT_USER
from vibesense.db import UserPreferences, get_context, get_preferences, set_preferences


router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesRequest(BaseModel):
    user_id: str | None = Field(None, description="Target user to update (defaults to 'default').")
    preferred_genres: list[str] = Field(default_factory=list)
    avoid_genres: list[str] = Field(default_factory=list)
    favorite_artists: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    notes: str | None = ""
    energy_profile: str | None = ""


@router.post("")
async def update_preferences(body: PreferencesRequest):
    """Persist user-level music preferences so the agent can fetch them via its DB tool."""

    user_id = body.user_id or DEFAULT_USER
    prefs = UserPreferences(
        preferred_genres=body.preferred_genres,
        avoid_genres=body.avoid_genres,
        favorite_artists=body.favorite_artists,
        dislikes=body.dislikes,
        notes=body.notes or "",
        energy_profile=body.energy_profile or "",
    )
    saved = set_preferences(user_id, prefs)
    return {"status": "ok", "user_id": user_id, "preferences": saved.to_dict()}


@router.get("")
async def read_preferences(user_id: str | None = None):
    user_id = user_id or DEFAULT_USER
    return {
        "status": "ok",
        "user_id": user_id,
        "context": get_context(user_id).to_dict(),
        "preferences": get_preferences(user_id).to_dict(),
    }


__all__ = ["router"]
