"""
Heart domain and infrastructure components.
"""

import time
from collections import deque
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

DEFAULT_USER = "default"


def time_of_day_bucket(ts: float | None = None) -> str:
    ts = ts or time.time()
    hour = time.localtime(ts).tm_hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


class HeartStateDTO(BaseModel):
    user_id: str | None = None
    bpm: float
    zone: str | None = None
    mood: str | None = None
    timestamp: float
    playlist_hint: str | None = None
    hrv_ms: float | None = None
    workout_type: str | None = None
    resting_hr: float | None = None
    time_of_day: str | None = None


@dataclass
class HeartState:
    bpm: float
    user_id: str = DEFAULT_USER
    mood: str | None = None
    hrv_ms: float | None = None
    workout_type: str | None = None
    resting_hr: float | None = None
    time_of_day: str | None = None
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

    def to_dto(self) -> HeartStateDTO:
        return HeartStateDTO(
            user_id=self.user_id,
            bpm=self.bpm,
            zone=self.zone(),
            mood=self.mood,
            timestamp=self.timestamp,
            playlist_hint=None,
            hrv_ms=self.hrv_ms,
            workout_type=self.workout_type,
            resting_hr=self.resting_hr,
            time_of_day=self.time_of_day,
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

    def push(
        self,
        bpm: float,
        mood: str | None,
        user_id: str,
        hrv_ms: float | None = None,
        workout_type: str | None = None,
        resting_hr: float | None = None,
        time_of_day: str | None = None,
    ) -> HeartState | None:
        ts = time.time()
        self._samples.append(HeartRateSample(ts, bpm))

        smoothed = self._smoothed_bpm()
        candidate = HeartState(
            bpm=smoothed,
            mood=mood,
            timestamp=ts,
            user_id=user_id,
            hrv_ms=hrv_ms,
            workout_type=workout_type,
            resting_hr=resting_hr,
            time_of_day=time_of_day,
        )

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
    user_id: str | None = Field(None, description="User id to keep samples scoped to one person.")
    hrv_ms: float | None = Field(None, description="Heart rate variability (SDNN in ms).")
    workout_type: str | None = Field(None, description="Optional workout/activity label (running, cycling, walking, hiit, strength, sedentary, unknown).")
    resting_hr: float | None = Field(None, description="Resting heart rate baseline if available.")
    time_of_day: str | None = Field(None, description="Client-provided time of day bucket.")


class HeartStateRepository:
    """In-memory store"""

    def __init__(self) -> None:
        self._latest: HeartState | None = None

    def save(self, state: HeartState) -> None:
        self._latest = state

    def latest(self) -> HeartState | None:
        return self._latest


@dataclass
class HeartUserContext:
    repo: HeartStateRepository
    stabilizer: HeartRateStabilizer


class HeartService:
    """Coordinates repository + stabilizer, encapsulates domain logic per user."""

    def __init__(self, stabilizer_config: HeartStabilizerConfig) -> None:
        self._config = stabilizer_config
        self._contexts: dict[str, HeartUserContext] = {}

    def _context(self, user_id: str) -> HeartUserContext:
        ctx = self._contexts.get(user_id)
        if ctx:
            return ctx
        ctx = HeartUserContext(
            repo=HeartStateRepository(),
            stabilizer=HeartRateStabilizer(self._config),
        )
        self._contexts[user_id] = ctx
        return ctx

    async def ingest(self, data: HeartIngestRequest) -> HeartStateDTO:
        user_id = data.user_id or DEFAULT_USER
        tod = data.time_of_day or time_of_day_bucket()
        ctx = self._context(user_id)
        state = ctx.stabilizer.push(
            data.bpm,
            data.mood,
            user_id,
            data.hrv_ms,
            data.workout_type,
            data.resting_hr,
            tod,
        )

        # If the stabilizer filtered the sample, surface the current stable state.
        if state is None:
            latest = ctx.stabilizer.latest() or ctx.repo.latest()
            if latest:
                return latest.to_dto()
            state = HeartState(
                bpm=data.bpm,
                mood=data.mood,
                user_id=user_id,
                hrv_ms=data.hrv_ms,
                workout_type=data.workout_type,
                resting_hr=data.resting_hr,
                time_of_day=tod,
            )

        ctx.repo.save(state)
        return state.to_dto()

    def latest(self, user_id: str | None = None) -> HeartStateDTO | None:
        ctx = self._contexts.get(user_id or DEFAULT_USER)
        if not ctx:
            return None
        stable = ctx.stabilizer.latest() or ctx.repo.latest()
        if stable:
            return stable.to_dto()
        return None


# Singleton for app-wide sharing
heart_service = HeartService(HeartStabilizerConfig())
