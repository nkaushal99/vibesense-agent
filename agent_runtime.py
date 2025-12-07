"""Agent orchestration helpers"""

from __future__ import annotations

import asyncio
import contextlib
from asyncio import Task
from dataclasses import dataclass
from typing import Optional

import uvicorn
from fast_agent.core import AgentApp
from uvicorn import Server

from heart_api import app as heart_app
from heart_core import HeartStateDTO, event_bus


@dataclass
class HeartServerRunner:
    host: str = "0.0.0.0"
    port: int = 8765
    log_level: str = "warning"

    def start(self) -> tuple[Task[None], Server]:
        config = uvicorn.Config(heart_app, host=self.host, port=self.port, log_level=self.log_level)
        server = uvicorn.Server(config)
        return asyncio.create_task(server.serve(), name="heart-server"), server


class HeartEventForwarder:
    """Listens to heart events and injects them into the agent conversation."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None

    async def _loop(self, agent_app: AgentApp) -> None:
        last_ts: dict[str, float] = {}
        while True:
            event: HeartStateDTO = await event_bus.poll()
            user_id = event.user_id or "default"
            ts = float(event.timestamp)
            if ts <= last_ts.get(user_id, 0.0):
                continue
            last_ts[user_id] = ts

            bpm = event.bpm
            zone = event.zone
            mood = event.mood
            hint = event.playlist_hint

            summary = (
                f"Heart update for user '{user_id}': {bpm} bpm (zone={zone}, mood={mood}, hint={hint}). "
                "Return one JSON suggestion only (no prose) so the iOS app can search/play locally."
            )
            try:
                await agent_app.send(summary)
            except Exception:
                # If the chat is closed or errors, keep listening for new events
                pass

    def start(self, agent_app: AgentApp) -> None:
        self._task = asyncio.create_task(self._loop(agent_app), name="heart-forwarder")

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with contextlib.suppress(Exception):
            await self._task
