"""MCP server for heart-rate ingestion and retrieval.

Run locally:
  uv run heart_mcp.py

Send heart rate (simulating HealthKit):
  curl -X POST http://127.0.0.1:8765/ingest \
       -H 'Content-Type: application/json' \
       -d '{"bpm": 82, "mood": "focused"}'

The Fast Agent can call the `get_current_heart_state` tool via MCP
to drive playback choices.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from mcp.server import FastMCP
from fastapi import Request
from fastapi.responses import JSONResponse, Response


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


state: HeartState | None = None
event_queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()

server = FastMCP(name="heart-backend", instructions="Provides current heart rate and mood hints")


@server.custom_route("/ingest", methods=["POST"])
async def ingest(request: Request) -> Response:
    """Ingest a heart-rate sample from an external source."""

    try:
        payload = await request.json()
    except Exception:  # pragma: no cover - defensive
        return JSONResponse({"error": "invalid json"}, status_code=400)

    bpm = payload.get("bpm")
    if bpm is None:
        return JSONResponse({"error": "bpm is required"}, status_code=400)
    try:
        bpm_val = float(bpm)
    except (TypeError, ValueError):
        return JSONResponse({"error": "bpm must be a number"}, status_code=400)

    mood = payload.get("mood")
    source = payload.get("source")
    global state
    state = HeartState(bpm=bpm_val, mood=mood, source=source)

    # Push to in-process queue for agents that subscribe to updates
    try:
        event_queue.put_nowait(state.to_dict())
    except asyncio.QueueFull:  # pragma: no cover - default queue is unbounded
        pass

    return JSONResponse({"status": "ok", "stored": state.to_dict()})


@server.tool(name="get_current_heart_state", description="Return latest heart rate, zone, mood hint, and playlist suggestion")
async def get_current_heart_state() -> dict[str, Any]:
    if state is None:
        return {
            "available": False,
            "message": "No heart-rate data ingested yet",
        }
    return {
        "available": True,
        "data": state.to_dict(),
    }


if __name__ == "__main__":
    # streamable-http enables both MCP and the /ingest route over HTTP
    server.run(transport="streamable-http")
