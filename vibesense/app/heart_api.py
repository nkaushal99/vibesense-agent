"""Heart-facing API router: ingest signals and fetch suggestions."""

import json
import logging
import os
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List

from vibesense.agent import generate_agent_suggestion
from vibesense.app.heart_core import HeartIngestRequest, HeartStateDTO, heart_service, time_of_day_bucket

logger = logging.getLogger(__name__)

router = APIRouter(tags=["heart"])

# =============================================================================
# Online Evaluation Client (fire-and-forget)
# =============================================================================
_eval_client = None

def _get_eval_client():
    """Lazy-load the evaluation client if configured."""
    global _eval_client
    eval_url = os.getenv("EVAL_SERVICE_URL")
    if not eval_url:
        return None
    if _eval_client is None:
        try:
            from agent_evaluation_client import OnlineEvalClient
            _eval_client = OnlineEvalClient(eval_url, timeout=0.1)
            logger.info(f"[Eval] Client initialized: {eval_url}")
        except ImportError:
            logger.warning("[Eval] agent_evaluation_client not installed, skipping evaluation")
    return _eval_client


def _evaluate_suggestion(state: HeartStateDTO, suggestion: dict) -> None:
    """Fire-and-forget evaluation of agent suggestion."""
    client = _get_eval_client()
    if not client:
        return
    
    # Format input/output for evaluation
    input_summary = f"bpm={state.bpm}, zone={state.zone}, workout={state.workout_type}, mood_override={state.mood}"
    output_summary = json.dumps(suggestion, default=str)
    
    logger.info(f"[Eval] Sending evaluation: user={state.user_id}, bpm={state.bpm}, zone={state.zone}")
    
    try:
        client.evaluate(
            agent_id="vibesense-agent",
            input=input_summary,
            output=output_summary,
            session_id=state.user_id,
            metadata={"bpm": state.bpm, "zone": state.zone},
            validation_criteria=[
                "Suggestion mood should match the physiological state",
                "Intensity should be appropriate for the heart rate zone",
                "Search query should incorporate user preferences if available",
            ]
        )
        logger.debug(f"[Eval] Event queued for evaluation")
    except Exception as e:
        logger.error(f"[Eval] Failed to send evaluation: {e}")


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
        _evaluate_suggestion(state, suggestion)  # Fire-and-forget evaluation
    return HeartIngestResponse(status="ok", state=state, suggestion=suggestion, state_changed=changed)


# =============================================================================
# Direct Suggestion Endpoint (bypasses smoothing - for evaluation/testing)
# =============================================================================

class DirectSuggestionRequest(BaseModel):
    """Request for direct suggestion without smoothing."""
    bpm: float = Field(..., description="Heart rate in BPM (used directly, no smoothing)")
    zone: Optional[str] = Field(None, description="Heart rate zone (rest, light, moderate, hard, peak)")
    hrv_ms: Optional[float] = Field(None, description="Heart rate variability in ms")
    workout_type: Optional[str] = Field(None, description="Workout type (running, hiit, sedentary, etc.)")
    resting_hr: Optional[float] = Field(None, description="Resting heart rate baseline")
    time_of_day: Optional[str] = Field(None, description="Time of day (morning, afternoon, evening, night)")
    mood: Optional[str] = Field(None, description="Explicit mood override")
    playlist_hint: Optional[str] = Field(None, description="Playlist preference hint")
    user_id: Optional[str] = Field(None, description="User ID")
    # User preferences (can be passed directly for evaluation)
    preferred_genres: Optional[List[str]] = Field(None, description="Preferred music genres")
    avoid_genres: Optional[List[str]] = Field(None, description="Genres to avoid")
    favorite_artists: Optional[List[str]] = Field(None, description="Favorite artists")
    notes: Optional[str] = Field(None, description="User notes (e.g., 'no explicit content')")


def _compute_zone(bpm: float) -> str:
    """Compute heart rate zone from BPM."""
    if bpm < 60:
        return "rest"
    if bpm < 90:
        return "light"
    if bpm < 120:
        return "moderate"
    if bpm < 150:
        return "hard"
    if bpm < 180:
        return "peak"
    if bpm < 200:
        return "redline"
    return "supra"


@router.post("/suggest")
async def direct_suggest(body: DirectSuggestionRequest):
    """
    Get a music suggestion directly from the agent WITHOUT smoothing.
    
    This endpoint bypasses the HeartRateStabilizer and passes the exact
    input values to the agent. Use this for:
    - Evaluation/testing (each request is independent)
    - One-off queries where you want exact control
    
    For production use with continuous heart rate streaming, use /ingest instead.
    """
    # Build state directly from input (no smoothing)
    zone = body.zone or _compute_zone(body.bpm)
    tod = body.time_of_day or time_of_day_bucket()
    
    state = HeartStateDTO(
        user_id=body.user_id or "default",
        bpm=body.bpm,  # Exact value, no smoothing!
        zone=zone,
        mood=body.mood,
        timestamp=time.time(),
        playlist_hint=body.playlist_hint,
        hrv_ms=body.hrv_ms,
        workout_type=body.workout_type,
        resting_hr=body.resting_hr,
        time_of_day=tod,
        # Pass preferences directly to agent (for evaluation/testing)
        preferred_genres=body.preferred_genres,
        avoid_genres=body.avoid_genres,
        favorite_artists=body.favorite_artists,
        notes=body.notes,
    )
    
    # Debug: Log what we're sending to the agent
    print(f"[/suggest] State for agent: bpm={state.bpm}, zone={state.zone}, workout={state.workout_type}, genres={state.preferred_genres}")
    
    suggestion = await generate_agent_suggestion(state)
    _evaluate_suggestion(state, suggestion)  # Fire-and-forget evaluation
    
    return {
        "status": "ok",
        "state": state,
        "suggestion": suggestion,
    }


@router.post("/reset")
async def reset_state(user_id: str | None = None):
    """
    Reset the stabilizer state for a user. 
    
    Use this between evaluation test cases to ensure each test starts fresh.
    """
    uid = user_id or "default"
    heart_service.reset(uid)
    return {"status": "ok", "message": f"State reset for user '{uid}'"}


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
