"""FastAPI server to ingest heart-rate updates and surface mood suggestions via the agent."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from vibesense.app.heart_core import DEFAULT_USER, HeartIngestRequest, heart_service
from vibesense.agent import generate_agent_suggestion
from vibesense.db import (
    UserPreferences,
    get_context,
    get_preferences,
    set_preferences,
)


app = FastAPI(title="Heart Ingest", docs_url=None, redoc_url=None, openapi_url=None)


class PreferencesRequest(BaseModel):
    user_id: str | None = Field(None, description="Target user to update (defaults to 'default').")
    preferred_genres: list[str] = Field(default_factory=list)
    avoid_genres: list[str] = Field(default_factory=list)
    favorite_artists: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    notes: str | None = ""
    energy_profile: str | None = ""


@app.post("/ingest")
async def ingest(body: HeartIngestRequest):
    """Ingest a heart-rate sample and return the latest mood suggestion from the agent."""

    state = await heart_service.ingest(body)
    suggestion = await generate_agent_suggestion(state)
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

    return await generate_agent_suggestion(state)


@app.post("/preferences")
async def update_preferences(body: PreferencesRequest):
    """Persist user-level music preferences so the agent can fetch them via its DB tool."""

    user_id = body.user_id or DEFAULT_USER
    prefs = UserPreferences(
        preferred_genres=body.preferred_genres,
        avoid_genres=body.avoid_genres,
        favorite_artists=body.favorite_artists,
        dislikes=body.dislikes,
        notes=body.notes or "",
        energy_profile=body.energy_profile or "",
    )
    saved = set_preferences(user_id, prefs)
    return {"status": "ok", "user_id": user_id, "preferences": saved.to_dict()}


@app.get("/preferences")
async def read_preferences(user_id: str | None = None):
    user_id = user_id or DEFAULT_USER
    return {
        "status": "ok",
        "user_id": user_id,
        "context": get_context(user_id).to_dict(),
        "preferences": get_preferences(user_id).to_dict(),
    }


if __name__ == "__main__":
    # Run without uvicorn's loop_factory helper so debuggers that patch asyncio.run keep working.
    import asyncio
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
