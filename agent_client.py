"""Lightweight client to invoke the Vibe Sense agent for a suggestion."""

from __future__ import annotations

import json
import os
import time
from functools import lru_cache

from fastapi import HTTPException
from langchain_google_genai import ChatGoogleGenerativeAI

from heart_core import HeartStateDTO
from agent_context import AgentContext, get_context, set_context
from prompt_loader import load_instruction

from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.3


def _build_prompt(state: HeartStateDTO, context: AgentContext) -> str:
    instruction = load_instruction()
    state_json = json.dumps(state.model_dump(), ensure_ascii=False)
    ctx_json = json.dumps(context.to_dict(), ensure_ascii=False)
    return f"""{instruction}

[STATE]
{state_json}

{{
  "context": {ctx_json}
}}

Return only the JSON object described in RESPONSE FORMAT, no prose."""


@lru_cache(maxsize=1)
def _build_llm(api_key: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=MODEL,
        api_key=api_key,
        temperature=TEMPERATURE,
    )


def _invoke_gemini(prompt: str) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set")

    llm = _build_llm(api_key)
    try:
        result = llm.invoke(prompt)
    except Exception as exc:  # pragma: no cover - network/LLM path
        raise HTTPException(status_code=502, detail="LLM call failed") from exc

    text = getattr(result, "content", None)
    if isinstance(text, list):
        text = " ".join(part for part in text if isinstance(part, str))
    if not isinstance(text, str):
        raise HTTPException(status_code=502, detail="Invalid response from LLM")
    try:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM did not return JSON") from exc


def generate_agent_suggestion(state: HeartStateDTO) -> dict:
    user = state.user_id or "default"
    context = get_context(user)
    prompt = _build_prompt(state, context)
    suggestion = _invoke_gemini(prompt)

    # Ensure required fields exist; agent isnt concerned with these
    suggestion.setdefault("user_id", user)
    suggestion.setdefault("generated_at", time.time())
    suggestion.setdefault("reason", "")
    # suggestion["heart"] = state.model_dump()
    # Update stored context for this user.
    set_context(
        user,
        AgentContext(
            last_action=str(suggestion.get("suggested_action", "keep_current")),
            last_query=str(suggestion.get("search_query", "")),
            last_reason=str(suggestion.get("reason", "")),
            last_intensity=float(suggestion.get("intensity", 0.0) or 0.0),
            last_action_at=time.time(),
        ),
    )
    return suggestion
