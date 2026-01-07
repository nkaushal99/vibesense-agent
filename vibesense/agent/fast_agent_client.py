"""FastAgent integration kept separate from the API surface."""

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException

from vibesense.agent.prompt_loader import load_instruction
from vibesense.app.heart_core import HeartStateDTO
from vibesense.db import AgentContext, set_context

load_dotenv()

MODEL = os.getenv("FAST_AGENT_MODEL", "google.gemini-2.5-flash")
TEMPERATURE = float(os.getenv("FAST_AGENT_TEMPERATURE", "0.3"))

try:
    from fast_agent.core.fastagent import FastAgent
    from fast_agent.core.prompt import Prompt
    from fast_agent.types import RequestParams
except Exception as exc:
    raise RuntimeError("fast-agent-mcp is required for suggestions") from exc


def _build_fast_agent() -> FastAgent:
    """Create the FastAgent instance at application startup."""
    config_path = Path(__file__).with_name("fastagent.config.yaml")
    fast = FastAgent("VibeSense Agent", config_path=str(config_path))

    @fast.agent(
        name="vibe_suggester",
        instruction=load_instruction(),
        model=MODEL,
        servers=['database'],
        request_params=RequestParams(temperature=TEMPERATURE),
    )
    async def run_agent() -> Any:
        return None  # Body unused; send() drives work.

    return fast


def _build_fast_agent_prompt(state: HeartStateDTO, user_id: str) -> str:
    state_dict = state.model_dump()
    state_json = json.dumps(state_dict, ensure_ascii=False, indent=2)
    
    # Extract key values for emphasis
    bpm = state_dict.get("bpm")
    zone = state_dict.get("zone")
    workout_type = state_dict.get("workout_type")
    mood_override = state_dict.get("mood")
    hrv = state_dict.get("hrv_ms")
    resting_hr = state_dict.get("resting_hr")
    
    # Extract preferences if provided directly
    preferred_genres = state_dict.get("preferred_genres") or []
    avoid_genres = state_dict.get("avoid_genres") or []
    favorite_artists = state_dict.get("favorite_artists") or []
    notes = state_dict.get("notes")
    
    # Build preferences section if any are provided
    has_direct_prefs = preferred_genres or avoid_genres or favorite_artists or notes
    prefs_section = ""
    if has_direct_prefs:
        prefs_section = f"""
═══════════════════════════════════════════════════════════════════════════════
[USER PREFERENCES] - Use these in your search_query
═══════════════════════════════════════════════════════════════════════════════
- Preferred Genres: {preferred_genres if preferred_genres else "None specified"}
- Avoid Genres: {avoid_genres if avoid_genres else "None"} (NEVER include these in search_query)
- Favorite Artists: {favorite_artists if favorite_artists else "None"}
- Notes: {notes if notes else "None"}

IMPORTANT: Your search_query MUST incorporate preferred_genres when available.
"""
    else:
        prefs_section = """
═══════════════════════════════════════════════════════════════════════════════
[USER PREFERENCES] - Call get_user_profile to fetch
═══════════════════════════════════════════════════════════════════════════════
No preferences provided directly. Call get_user_profile(user_id="{user_id}") to fetch stored preferences.
"""
    
    # Compute expected intensity range based on state
    intensity_hint = ""
    if mood_override:
        intensity_hint = f"Mood override '{mood_override}' takes priority."
    elif workout_type and workout_type not in ("sedentary", "unknown", None):
        if zone in ("peak", "redline", "supra") or (bpm and bpm >= 160):
            intensity_hint = f"HIGH INTENSITY expected (>0.8): peak workout at {bpm} bpm"
        elif zone == "hard" or (bpm and bpm >= 140):
            intensity_hint = f"MODERATE-HIGH intensity expected (0.7-0.9): hard workout at {bpm} bpm"
        elif zone == "moderate" or (bpm and bpm >= 100):
            intensity_hint = f"MODERATE intensity expected (0.5-0.7): moderate activity at {bpm} bpm"
    elif hrv and hrv < 45 and resting_hr and bpm and bpm > resting_hr + 15:
        intensity_hint = f"STRESS DETECTED: Low HRV ({hrv}ms) + elevated HR while sedentary. Suggest calming music (intensity < 0.3)"
    
    prompt = f"""
IMPORTANT: You MUST use the EXACT values from the [STATE] block below. Do NOT invent or hallucinate different values.

{"Step 1: Analyze preferences below." if has_direct_prefs else f'Step 1: Call get_user_profile(user_id="{user_id}") to fetch stored preferences.'}
Step 2: Analyze the [STATE] data (these are the CURRENT readings from the user's device).
Step 3: Return ONLY a valid JSON object with double quotes (no markdown, no prose).

═══════════════════════════════════════════════════════════════════════════════
[STATE] - CURRENT PHYSIOLOGICAL DATA (use these EXACT values)
═══════════════════════════════════════════════════════════════════════════════
{state_json}

KEY VALUES TO USE IN YOUR RESPONSE:
- Current BPM: {bpm} (use this exact number, NOT 75 or any other value)
- Current Zone: {zone}
- Workout Type: {workout_type}
- HRV: {hrv} ms
- Resting HR: {resting_hr}
- Mood Override: {mood_override if mood_override else "None - infer from physiology"}
{prefs_section}
═══════════════════════════════════════════════════════════════════════════════
[INTENSITY GUIDANCE]
═══════════════════════════════════════════════════════════════════════════════
{intensity_hint if intensity_hint else f"Infer from BPM={bpm}, zone={zone}, workout={workout_type}"}

{"CRITICAL: User has set mood=" + str(mood_override) + ". This OVERRIDES all physiological inference. Honor this mood regardless of BPM/zone." if mood_override else ""}

Your "reason" field MUST include the actual bpm={bpm} and zone={zone} values to prove you read the state correctly.

Return ONLY the JSON object as specified in RESPONSE FORMAT. Use double quotes for all strings.
"""
    return prompt


_FAST_AGENT = _build_fast_agent()


def ensure_agent_ready() -> None:
    """No-op helper to force FastAgent construction at startup."""

    _ = _FAST_AGENT


def _clean_result(result: str) -> dict[str, Any]:
    """Clean and parse agent response, handling common formatting issues."""
    # Remove markdown code blocks
    result = result.replace("```json\n", "").replace("```json", "")
    result = result.replace("\n```", "").replace("```", "")
    result = result.strip()
    
    # Try to parse as-is first
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        pass
    
    # Handle Python dict format (single quotes) by converting to JSON
    # This fixes the common issue where the agent returns Python dict syntax
    try:
        import ast
        parsed = ast.literal_eval(result)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass
    
    # Try to fix common JSON issues: single quotes to double quotes
    try:
        # Replace single quotes with double quotes (careful with apostrophes)
        fixed = result.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    raise json.JSONDecodeError("Could not parse agent response", result, 0)


def _extract_suggestion(result: Any) -> dict | None:
    result = _clean_result(result)
    if result is None:
        return None
    if isinstance(result, dict):
        for key in ("suggestion", "output", "response", "result"):
            maybe = result.get(key)
            if isinstance(maybe, dict):
                return maybe
        return result
    if hasattr(result, "output"):
        out = getattr(result, "output")
        if isinstance(out, dict):
            return out
    return None


async def _call_fast_agent(prompt: str) -> dict:
    try:
        async with _FAST_AGENT.run() as agent:
            result = await agent.vibe_suggester.send(Prompt.user(prompt))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"fast-agent failed: {exc}") from exc

    suggestion = _extract_suggestion(result)
    if suggestion:
        return suggestion
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            pass
    raise HTTPException(status_code=502, detail="fast-agent returned unsupported format")


VALID_MOODS = {"chill", "focus", "upbeat", "hype", "intense", "sad", "balanced"}
VALID_ACTIONS = {"play_playlist", "play_track", "keep_current"}


def _validate_suggestion(suggestion: dict) -> dict:
    """Validate and normalize the agent's suggestion output."""
    # Ensure mood is valid
    mood = str(suggestion.get("mood", "balanced")).lower()
    if mood not in VALID_MOODS:
        # Try to map common variations
        mood_map = {
            "steady upbeat": "upbeat",
            "calm": "chill",
            "relaxed": "chill",
            "energetic": "upbeat",
            "pumped": "hype",
        }
        mood = mood_map.get(mood, "balanced")
    suggestion["mood"] = mood
    
    # Ensure intensity is a float in range 0-1
    try:
        intensity = float(suggestion.get("intensity", 0.5))
        suggestion["intensity"] = max(0.0, min(1.0, intensity))
    except (TypeError, ValueError):
        suggestion["intensity"] = 0.5
    
    # Ensure suggested_action is valid
    action = str(suggestion.get("suggested_action", "keep_current")).lower()
    if action not in VALID_ACTIONS:
        suggestion["suggested_action"] = "keep_current"
    else:
        suggestion["suggested_action"] = action
    
    # Ensure search_query is a string
    suggestion["search_query"] = str(suggestion.get("search_query", "") or "")
    
    # Ensure reason is a string
    suggestion["reason"] = str(suggestion.get("reason", "") or "")
    
    return suggestion


def _finalize_suggestion(raw: dict, user_id: str) -> dict:
    suggestion = _validate_suggestion(dict(raw))
    suggestion["user_id"] = user_id
    suggestion["generated_at"] = time.time()
    
    set_context(
        user_id,
        AgentContext(
            last_action=suggestion["suggested_action"],
            last_query=suggestion["search_query"],
            last_reason=suggestion["reason"],
            last_intensity=suggestion["intensity"],
            last_action_at=time.time(),
        ),
    )
    return suggestion


async def generate_agent_suggestion(state: HeartStateDTO) -> dict:
    user = state.user_id or "default"
    prompt = _build_fast_agent_prompt(state, user)
    suggestion = await _call_fast_agent(prompt)
    return _finalize_suggestion(suggestion, user)


__all__ = ["generate_agent_suggestion"]
