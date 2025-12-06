"""
Heart domain and infrastructure components.
"""

import asyncio
import time
from collections import deque
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
        if bpm < 180:
            return "peak"
        if bpm < 200:
            return "redline"
        return "supra"

    def inferred_mood(self) -> str:
        zones = {
            "rest": "chill",
            "light": "focus",
            "moderate": "upbeat",
            "hard": "hype",
            "peak": "intense",
            "redline": "max-energy",
            "supra": "steady-intense",
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
            "redline": "hard EDM or rock bangers",
            "supra": "sustain intensity without abrupt shifts",
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


@dataclass
class HeartStabilizerConfig:
    smoothing_window: int = 5
    min_bpm_delta: float = 5.0
    min_seconds_between_updates: float = 8.0
    min_zone_dwell: float = 20.0
    fast_zone_delta: float = 12.0


@dataclass
class HeartRateSample:
    ts: float
    bpm: float


class HeartRateStabilizer:
    """
    Smooths heart-rate inputs and only emits when a meaningful change occurs.

    - Rolling average across a small window to absorb jitter.
    - Hysteresis on zone changes to avoid flapping.
    - Minimum spacing between events so playback does not thrash.
    """

    def __init__(self, config: HeartStabilizerConfig) -> None:
        self._config = config
        self._samples: deque[HeartRateSample] = deque(maxlen=self._config.smoothing_window)
        self._latest: HeartState | None = None
        self._last_publish_ts: float = 0.0

    def _smoothed_bpm(self) -> float:
        if not self._samples:
            return 0.0
        return sum(sample.bpm for sample in self._samples) / len(self._samples)

    def _record(self, state: HeartState, ts: float) -> HeartState:
        self._latest = state
        self._last_publish_ts = ts
        return state

    def push(self, bpm: float, mood: str | None) -> HeartState | None:
        ts = time.time()
        self._samples.append(HeartRateSample(ts, bpm))

        smoothed = self._smoothed_bpm()
        candidate = HeartState(bpm=smoothed, mood=mood, timestamp=ts)

        if self._latest is None:
            return self._record(candidate, ts)

        prev = self._latest
        delta = abs(candidate.bpm - prev.bpm)
        same_zone = candidate.zone() == prev.zone()
        time_since_last = ts - self._last_publish_ts
        zone_changed = not same_zone

        # Ignore small jitter inside the same zone.
        if same_zone and delta < self._config.min_bpm_delta:
            return None

        # Prevent thrashing when updates arrive very fast.
        if time_since_last < self._config.min_seconds_between_updates:
            # Allow large, obvious jumps through.
            if not (zone_changed and delta >= self._config.fast_zone_delta):
                return None

        # Require dwell time for mild zone changes so playlists do not flip-flop.
        if zone_changed and delta < self._config.fast_zone_delta and time_since_last < self._config.min_zone_dwell:
            return None

        return self._record(candidate, ts)

    def latest(self) -> HeartState | None:
        return self._latest


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

    def __init__(
        self,
        repo: HeartStateRepository,
        bus: HeartEventBus,
        stabilizer: HeartRateStabilizer,
    ) -> None:
        self._repo = repo
        self._bus = bus
        self._stabilizer = stabilizer

    async def ingest(self, data: HeartIngestRequest) -> HeartStateDTO:
        state = self._stabilizer.push(data.bpm, data.mood)

        # If the stabilizer filtered the sample, surface the current stable state.
        if state is None:
            latest = self._stabilizer.latest() or self._repo.latest()
            if latest:
                return latest.to_dto()
            state = HeartState(bpm=data.bpm, mood=data.mood)

        self._repo.save(state)
        payload = state.to_dto()
        await self._bus.push(payload)
        return payload

    def latest(self) -> HeartStateDTO | None:
        stable = self._stabilizer.latest() or self._repo.latest()
        if stable:
            return stable.to_dto()
        return None


# Singletons for app-wide sharing
event_bus = HeartEventBus()
heart_service = HeartService(HeartStateRepository(), event_bus, HeartRateStabilizer(HeartStabilizerConfig()))
