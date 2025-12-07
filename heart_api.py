"""FastAPI server to ingest heart-rate updates and surface mood suggestions."""

from fastapi import FastAPI, HTTPException

from heart_core import DEFAULT_USER, HeartIngestRequest, heart_service
from suggestions import suggestion_service


app = FastAPI(title="Heart Ingest", docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/ingest")
async def ingest(body: HeartIngestRequest):
    """Ingest a heart-rate sample and return the latest mood suggestion."""

    state = await heart_service.ingest(body)
    suggestion = suggestion_service.suggest(state)
    print(f"Suggestion: {suggestion}")
    return {"status": "ok", "state": state, "suggestion": suggestion}


@app.get("/health")
async def health(user_id: str | None = None):
    state = heart_service.latest(user_id)
    suggestion = suggestion_service.latest(user_id) if state else None
    return {"status": "ok", "state": state, "suggestion": suggestion}


@app.get("/suggestion")
async def latest_suggestion(user_id: str | None = None):
    """Fetch the most recent suggestion; derive one from heart state if needed."""

    existing = suggestion_service.latest(user_id)
    if existing:
        return existing

    state = heart_service.latest(user_id or DEFAULT_USER)
    if not state:
        raise HTTPException(status_code=404, detail="No heart data available for that user.")

    return suggestion_service.suggest(state)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
