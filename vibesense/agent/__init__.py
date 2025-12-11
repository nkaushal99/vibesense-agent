"""Agent package exposing fast-agent helpers."""

from .fast_agent_client import ensure_agent_ready, generate_agent_suggestion

__all__ = ["generate_agent_suggestion", "ensure_agent_ready"]
