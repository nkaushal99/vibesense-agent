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

        hrv = state.hrv_ms or 0.0
        resting = state.resting_hr or 60.0
        workout = (state.workout_type or "unknown").lower()
        is_workout = workout not in ("unknown", "sedentary", "rest", "none")
        high_bpm_for_rest = state.bpm > max(90, resting + 15)
        low_hrv = hrv > 0 and hrv < 45
        recovered = hrv >= 65 or (state.zone in ("rest", "light") and state.bpm <= resting + 5)
        stressed = (not is_workout) and (low_hrv or high_bpm_for_rest) and state.zone not in ("hard", "peak", "redline")

        if stressed:
            mood = "calm"
            action = "play_playlist"
            intensity = 0.2
            query = "calming ambient instrumental"
            reason = f"{state.bpm:.0f} bpm w/ low HRV ({hrv:.0f} ms) and no workout → calming"
        elif recovered:
            mood = "focus"
            action = "play_playlist"
            intensity = 0.35
            query = "deep focus beats"
            reason = f"Recovered (HRV {hrv:.0f} ms, {state.zone} zone) → focus music"
        elif is_workout:
            mood = state.mood or defaults["mood"]
            action = defaults["action"]
            intensity = defaults["intensity"]
            query = self._build_query(defaults["query"], workout)
            reason = f"Workout: {workout} in {state.zone} zone at {state.bpm:.0f} bpm → keep energy"
        else:
            mood = state.mood or defaults["mood"]
            action = defaults["action"]
            intensity = defaults["intensity"]
            query = self._build_query(defaults["query"], state.playlist_hint)
            reason = f"{state.bpm:.0f} bpm in {state.zone} zone → {mood} vibe"

        if state.time_of_day:
            reason = f"{reason} [{state.time_of_day}]"

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
