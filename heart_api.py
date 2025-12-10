"""FastAPI server to ingest heart-rate updates and surface mood suggestions via the agent."""

from fastapi import FastAPI, HTTPException

from agent_client import generate_agent_suggestion
from heart_core import DEFAULT_USER, HeartIngestRequest, heart_service


app = FastAPI(title="Heart Ingest", docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/ingest")
async def ingest(body: HeartIngestRequest):
    """Ingest a heart-rate sample and return the latest mood suggestion from the agent."""

    state = await heart_service.ingest(body)
    suggestion = generate_agent_suggestion(state)
    print(f"Suggestion: {suggestion}")
    return {"status": "ok", "state": state, "suggestion": suggestion}


@app.get("/health")
async def health(user_id: str | None = None):
    state = heart_service.latest(user_id)
    return {"status": "ok", "state": state, "suggestion": None}


@app.get("/suggestion")
async def latest_suggestion(user_id: str | None = None):
    """Derive a suggestion on demand via the agent."""

    state = heart_service.latest(user_id or DEFAULT_USER)
    if not state:
        raise HTTPException(status_code=404, detail="No heart data available for that user.")

    return generate_agent_suggestion(state)


if __name__ == "__main__":
    # Run without uvicorn's loop_factory helper so debuggers that patch asyncio.run keep working.
    import asyncio
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
