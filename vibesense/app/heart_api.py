"""Heart-facing API router: ingest signals and fetch suggestions."""

from fastapi import APIRouter, HTTPException

from vibesense.agent import generate_agent_suggestion
from vibesense.app.heart_core import DEFAULT_USER, HeartIngestRequest, heart_service


router = APIRouter(tags=["heart"])


@router.post("/ingest")
async def ingest(body: HeartIngestRequest):
    """Ingest a heart-rate sample and return the latest mood suggestion from the agent."""

    state = await heart_service.ingest(body)
    suggestion = await generate_agent_suggestion(state)
    print(f"Suggestion: {suggestion}")
    return {"status": "ok", "state": state, "suggestion": suggestion}


@router.get("/health")
async def health(user_id: str | None = None):
    state = heart_service.latest(user_id)
    return {"status": "ok", "state": state, "suggestion": None}


@router.get("/suggestion")
async def latest_suggestion(user_id: str | None = None):
    """Derive a suggestion on demand via the agent."""

    state = heart_service.latest(user_id or DEFAULT_USER)
    if not state:
        raise HTTPException(status_code=404, detail="No heart data available for that user.")

    return await generate_agent_suggestion(state)


__all__ = ["router"]
