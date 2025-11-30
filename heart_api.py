"""FastAPI server to ingest heart-rate updates and push them to a queue.

Run:
  uv run heart_api.py

Send data (simulating HealthKit):
  curl -X POST http://127.0.0.1:8765/ingest \
       -H 'Content-Type: application/json' \
       -d '{"bpm": 82, "mood": "focused"}'

The agent imports the shared event bus to react to new events.
"""

from fastapi import FastAPI

from heart_core import HeartIn, heart_service


app = FastAPI(title="Heart Ingest", docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/ingest")
async def ingest(body: HeartIn):
    """Ingest a heart-rate sample from an external source and push to queue."""

    payload = await heart_service.ingest(body)
    return {"status": "ok", "stored": payload}


@app.get("/health")
async def health():
    return {"status": "ok", "state": heart_service.latest().to_dict()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
