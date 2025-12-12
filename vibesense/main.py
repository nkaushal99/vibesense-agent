"""Facade to start the FastAPI server and ensure FastAgent is initialized."""

from __future__ import annotations

import asyncio
import os

import uvicorn

from vibesense.agent import ensure_agent_ready
from vibesense.app.api import app


def run() -> None:
    # Ensure the FastAgent tooling is constructed before serving requests.
    ensure_agent_ready()

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8765"))
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


if __name__ == "__main__":
    run()
