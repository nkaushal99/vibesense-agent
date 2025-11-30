"""
Heart domain and infrastructure components.
"""

import asyncio
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class HeartStateDTO(BaseModel):
    bpm: float
    zone: str
    mood: str
    timestamp: float
    playlist_hint: str


@dataclass
class HeartState:
    bpm: float
    mood: str | None = None
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

    def to_dto(self) -> HeartStateDTO:
        return HeartStateDTO(
            bpm=self.bpm,
            zone=self.zone(),
            mood=self.inferred_mood(),
            timestamp=self.timestamp,
            playlist_hint=self.playlist_hint()
        )


class HeartIngestRequest(BaseModel):
    bpm: float = Field(..., description="Heart rate in BPM")
    mood: str | None = Field(None, description="Optional user mood override")


class HeartStateRepository:
    """In-memory store"""

    def __init__(self) -> None:
        self._latest: HeartState | None = None

    def save(self, state: HeartState) -> None:
        self._latest = state

    def latest(self) -> HeartState | None:
        return self._latest


class HeartEventBus:
    """Simple async queue; can be replaced with a broker without changing callers."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[HeartStateDTO] = asyncio.Queue()

    async def push(self, payload: HeartStateDTO) -> None:
        await self._queue.put(payload)

    async def poll(self) -> HeartStateDTO:
        return await self._queue.get()


class HeartService:
    """Coordinates repository + bus, encapsulates domain logic."""

    def __init__(self, repo: HeartStateRepository, bus: HeartEventBus) -> None:
        self._repo = repo
        self._bus = bus

    async def ingest(self, data: HeartIngestRequest) -> HeartStateDTO:
        state = HeartState(bpm=data.bpm, mood=data.mood)
        self._repo.save(state)
        payload = state.to_dto()
        await self._bus.push(payload)
        return payload

    def latest(self) -> HeartStateDTO | None:
        return self._repo.latest().to_dto()


# Singletons for app-wide sharing
event_bus = HeartEventBus()
heart_service = HeartService(HeartStateRepository(), event_bus)
