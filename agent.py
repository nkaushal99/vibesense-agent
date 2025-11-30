import asyncio
from pathlib import Path

import yaml
from fast_agent import FastAgent

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
    instruction=load_instruction(),
    servers=["spotify"]
)
async def main():
    async with fast.run() as agent:
        await agent.interactive()

if __name__ == "__main__":
    asyncio.run(main())
