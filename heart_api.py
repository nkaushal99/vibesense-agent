"""FastAPI server to ingest heart-rate updates and push them to a queue.

Run:
  uv run heart_api.py

Send data (simulating HealthKit):
  curl -X POST http://127.0.0.1:8765/ingest \
       -H 'Content-Type: application/json' \
       -d '{"bpm": 82, "mood": "focused"}'

The agent imports `event_queue` to react to new events.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
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


state: HeartState | None = None
event_queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()


app = FastAPI(title="Heart Ingest", docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/ingest")
async def ingest(body: HeartIn):
    """Ingest a heart-rate sample from an external source and push to queue."""

    global state
    state = HeartState(bpm=body.bpm, mood=body.mood, source=body.source)

    payload = state.to_dict()
    try:
        event_queue.put_nowait(payload)
    except asyncio.QueueFull:  # pragma: no cover - default queue is unbounded
        pass

    return {"status": "ok", "stored": payload}


@app.get("/health")
async def health():
    return {"status": "ok", "has_state": state is not None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
