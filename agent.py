import asyncio
import contextlib

from dotenv import load_dotenv
from fast_agent import FastAgent

from agent_runtime import HeartEventForwarder, HeartServerRunner
from prompt_loader import load_instruction

load_dotenv()

fast = FastAgent("Vibe Sense")

@fast.agent(
    model="google.gemini-2.5-flash",
    instruction=load_instruction()
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
