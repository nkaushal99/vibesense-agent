"""
Heart domain and infrastructure components.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


@dataclass
class HeartState:
    bpm: float
    mood: str | None = None
    source: str | None = None
    timestamp: float = field(default_factory=lambda: time.time())

    def zone(self) -> str:
        bpm = self.bpm
        if bpm < 60:
            return "rest"
        if bpm < 90:
            return "light"
        if bpm < 120:
            return "moderate"
        if bpm < 150:
            return "hard"
        return "peak"

    def inferred_mood(self) -> str:
        zones = {
            "rest": "chill",
            "light": "focus",
            "moderate": "upbeat",
            "hard": "hype",
            "peak": "intense",
        }
        if self.mood:
            return self.mood
        return zones.get(self.zone(), "chill")

    def playlist_hint(self) -> str:
        hints = {
            "rest": "calm acoustic or lo-fi",
            "light": "steady focus playlists",
            "moderate": "upbeat pop/indie",
            "hard": "high-energy workout",
            "peak": "max intensity anthems",
        }
        return hints.get(self.zone(), "chill")

    def to_dict(self) -> dict[str, Any]:
        return {
            "bpm": self.bpm,
            "zone": self.zone(),
            "mood": self.inferred_mood(),
            "source": self.source,
            "timestamp": self.timestamp,
            "playlist_hint": self.playlist_hint(),
            "cooldown_recommended": self.zone() in {"hard", "peak"},
        }


class HeartIn(BaseModel):
    bpm: float = Field(..., description="Heart rate in BPM")
    mood: str | None = Field(None, description="Optional user mood override")
    source: str | None = Field(None, description="Optional source identifier")


class HeartStateRepository:
    """In-memory store; swap with persistent repo if needed."""

    def __init__(self) -> None:
        self._latest: HeartState | None = None

    def save(self, state: HeartState) -> None:
        self._latest = state

    def latest(self) -> HeartState | None:
        return self._latest


class HeartEventBus:
    """Simple async queue; can be replaced with a broker without changing callers."""

    def __init__(self) -> None:
        self._queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()

    async def push(self, payload: dict[str, Any]) -> None:
        await self._queue.put(payload)

    async def poll(self) -> dict[str, Any]:
        return await self._queue.get()


class HeartService:
    """Coordinates repository + bus, encapsulates domain logic."""

    def __init__(self, repo: HeartStateRepository, bus: HeartEventBus) -> None:
        self.repo = repo
        self.bus = bus

    async def ingest(self, data: HeartIn) -> dict[str, Any]:
        state = HeartState(bpm=data.bpm, mood=data.mood, source=data.source)
        self.repo.save(state)
        payload = state.to_dict()

        await self.bus.push(payload)
        return payload

    def latest(self) -> HeartState | None:
        return self.repo.latest()


# Singletons for app-wide sharing
event_bus = HeartEventBus()
state_repo = HeartStateRepository()
heart_service = HeartService(state_repo, event_bus)
