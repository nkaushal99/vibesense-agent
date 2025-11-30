import asyncio
import contextlib
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fast_agent import FastAgent
from fast_agent.core import AgentApp

from heart_mcp import event_queue, server as heart_server

load_dotenv()


PROMPTS_FILE = Path(__file__).parent / "prompts.yaml"


def load_instruction() -> str:
    prompts_data = yaml.safe_load(PROMPTS_FILE.read_text(encoding="utf-8")) or {}

    if isinstance(prompts_data, dict) and "instruction" in prompts_data:
        return str(prompts_data["instruction"])

    if isinstance(prompts_data, str):
        return prompts_data

    raise ValueError(f"Instruction not found in {PROMPTS_FILE}")

# Create the application
fast = FastAgent("Vibe Sense")

@fast.agent(
    model="google.gemini-2.0-flash-lite",
    instruction=load_instruction(),
    servers=["spotify"]
)
async def main():
    # Start heart MCP HTTP server in-process so /ingest can push to the shared queue
    heart_server.settings.host = "127.0.0.1"
    heart_server.settings.port = 8765
    heart_server_task = asyncio.create_task(heart_server.run_streamable_http_async())

    async def forward_heart_events(agent_app: AgentApp) -> None:
        last_ts = 0.0
        while True:
            event = await event_queue.get()
            ts = float(event.get("timestamp", 0.0))
            if ts <= last_ts:
                continue
            last_ts = ts

            bpm = event.get("bpm")
            zone = event.get("zone")
            mood = event.get("mood")
            hint = event.get("playlist_hint")
            source = event.get("source")

            summary = (
                f"Heart update: {bpm} bpm (zone={zone}, mood={mood}, hint={hint}, source={source}). "
                "Pick or adjust music accordingly."
            )
            try:
                await agent_app.send(summary)
            except Exception:
                # If the chat is closed or errors, keep listening for new events
                pass

    async with fast.run() as agent:
        forward_task = asyncio.create_task(forward_heart_events(agent))
        try:
            await agent.interactive()
        finally:
            forward_task.cancel()
            heart_server_task.cancel()
            with contextlib.suppress(Exception):
                await heart_server_task
                await forward_task

if __name__ == "__main__":
    asyncio.run(main())
