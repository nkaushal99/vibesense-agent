"""FastAgent integration kept separate from the API surface."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException
from dotenv import load_dotenv

from vibesense.app.heart_core import HeartStateDTO
from vibesense.agent.prompt_loader import load_instruction
from vibesense.db import AgentContext, set_context
from vibesense.tools import UserProfileTool

load_dotenv()

MODEL = os.getenv("FAST_AGENT_MODEL", "google.gemini-2.5-flash")
TEMPERATURE = float(os.getenv("FAST_AGENT_TEMPERATURE", "0.3"))

try:
    from fast_agent.core.fastagent import FastAgent  # type: ignore
    from fast_agent.core.prompt import Prompt  # type: ignore
    from fast_agent.types import RequestParams  # type: ignore
except Exception as exc:  # pragma: no cover - import-time guard
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
    state_json = json.dumps(state.model_dump(), ensure_ascii=False)
    return f""" 
            Tooling: call get_user_profile(user_id) to pull the latest stored context and preferences before finalizing.
            Current user_id: {user_id}
            
            [STATE]
            {state_json}
            
            Return only the JSON object described in RESPONSE FORMAT, no prose.
            """


_FAST_AGENT = _build_fast_agent()


def ensure_agent_ready() -> None:
    """No-op helper to force FastAgent construction at startup."""

    _ = _FAST_AGENT


def _clean_result(result: str) -> dict[str, Any]:
    result = result.replace("```json\n", "")
    result = result.replace("\n```", "")
    return json.loads(result)


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


def _finalize_suggestion(raw: dict, user_id: str) -> dict:
    suggestion = dict(raw)
    suggestion.setdefault("user_id", user_id)
    suggestion.setdefault("generated_at", time.time())
    suggestion.setdefault("reason", "")
    set_context(
        user_id,
        AgentContext(
            last_action=str(suggestion.get("suggested_action", "keep_current")),
            last_query=str(suggestion.get("search_query", "")),
            last_reason=str(suggestion.get("reason", "")),
            last_intensity=float(suggestion.get("intensity", 0.0) or 0.0),
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
