"""Heart-facing API router: ingest signals and fetch suggestions."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from vibesense.agent import generate_agent_suggestion
from vibesense.app.heart_core import HeartIngestRequest, HeartStateDTO, heart_service


router = APIRouter(tags=["heart"])


class HeartIngestResponse(BaseModel):
    status: str = Field(default="ok")
    state: HeartStateDTO
    suggestion: dict | None = Field(default=None)
    state_changed: bool = Field(default=False)


@router.post("/ingest")
async def ingest(body: HeartIngestRequest):
    """Ingest a heart-rate sample and return the latest mood suggestion from the agent."""

    state, changed = await heart_service.ingest(body)
    suggestion = None
    if changed:
        suggestion = await generate_agent_suggestion(state)
        print(f"Suggestion: {suggestion}")
    return HeartIngestResponse(status="ok", state=state, suggestion=suggestion, state_changed=changed)


@router.get("/health")
async def health(user_id: str | None = None):
    state = heart_service.latest(user_id)
    return {"status": "ok", "state": state, "suggestion": None}


# @router.get("/suggestion")
# async def latest_suggestion(user_id: str | None = None):
#     """Derive a suggestion on demand via the agent."""
#
#     state = heart_service.latest(user_id or DEFAULT_USER)
#     if not state:
#         raise HTTPException(status_code=404, detail="No heart data available for that user.")
#
#     return await generate_agent_suggestion(state)


__all__ = ["router"]
