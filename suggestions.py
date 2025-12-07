"""
Mood suggestion builder for the iOS client.
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from pydantic import BaseModel, Field

from heart_core import DEFAULT_USER, HeartStateDTO


class MoodSuggestion(BaseModel):
    user_id: str = Field(default=DEFAULT_USER, description="User id the suggestion applies to.")
    mood: str = Field(..., description="High-level mood label to steer music selection.")
    intensity: float = Field(..., ge=0.0, le=1.0, description="0-1 scale of energy.")
    suggested_action: str = Field(..., description="play_playlist | play_track | keep_current")
    search_query: str = Field(..., description="Plain text query for Spotify search on the device.")
    reason: str = Field(..., description="Short explanation tied to heart-rate context.")
    generated_at: float = Field(..., description="Unix timestamp when the suggestion was produced.")
    heart: HeartStateDTO = Field(..., description="Heart snapshot that informed the suggestion.")


class SuggestionService:
    """Stores and generates mood suggestions from heart states."""

    _defaults = {
        "rest": {
            "mood": "relaxed",
            "intensity": 0.15,
            "action": "play_playlist",
            "query": "acoustic chill instrumental focus",
        },
        "light": {
            "mood": "focused",
            "intensity": 0.3,
            "action": "play_playlist",
            "query": "lofi steady focus beats",
        },
        "moderate": {
            "mood": "upbeat",
            "intensity": 0.55,
            "action": "play_playlist",
            "query": "upbeat pop indie groove",
        },
        "hard": {
            "mood": "hype",
            "intensity": 0.75,
            "action": "play_track",
            "query": "high energy workout bangers",
        },
        "peak": {
            "mood": "intense",
            "intensity": 0.9,
            "action": "play_track",
            "query": "max intensity edm anthems",
        },
        "redline": {
            "mood": "max-energy",
            "intensity": 0.95,
            "action": "play_track",
            "query": "hard rock edm sprint",
        },
        "supra": {
            "mood": "steady-intense",
            "intensity": 0.85,
            "action": "play_playlist",
            "query": "intense endurance mix",
        },
    }

    def __init__(self) -> None:
        self._latest: Dict[str, MoodSuggestion] = {}

    def _pick_defaults(self, zone: str) -> dict:
        return self._defaults.get(zone, self._defaults["rest"])

    def _build_query(self, base_query: str, hint: str | None) -> str:
        hint = (hint or "").strip()
        if not hint:
            return base_query
        return f"{hint} {base_query}"

    def suggest(self, state: HeartStateDTO) -> MoodSuggestion:
        user_id = state.user_id or DEFAULT_USER
        defaults = self._pick_defaults(state.zone)

        mood = state.mood or defaults["mood"]
        query = self._build_query(defaults["query"], state.playlist_hint)
        action = defaults["action"]
        intensity = defaults["intensity"]

        reason = f"{state.bpm:.0f} bpm in {state.zone} zone → {mood} vibe"
        suggestion = MoodSuggestion(
            user_id=user_id,
            mood=mood,
            intensity=float(intensity),
            suggested_action=action,
            search_query=query,
            reason=reason,
            generated_at=time.time(),
            heart=state,
        )

        self._latest[user_id] = suggestion
        return suggestion

    def latest(self, user_id: str | None = None) -> Optional[MoodSuggestion]:
        return self._latest.get(user_id or DEFAULT_USER)


# Shared singleton
suggestion_service = SuggestionService()
