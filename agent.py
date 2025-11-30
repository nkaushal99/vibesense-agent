import asyncio
import contextlib
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fast_agent import FastAgent

from agent_runtime import HeartEventForwarder, HeartServerRunner

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
    model="google.gemini-2.5-flash",
    instruction=load_instruction(),
    servers=["spotify"]
)
async def main():
    heart_runner = HeartServerRunner()
    heart_server_task, heart_server = heart_runner.start()
    heart_forwarder = HeartEventForwarder()

    async with fast.run() as agent:
        heart_forwarder.start(agent)
        try:
            await agent.interactive()
        finally:
            await heart_forwarder.stop()
            heart_server.should_exit = True
            with contextlib.suppress(Exception):
                await heart_server_task

if __name__ == "__main__":
    asyncio.run(main())
