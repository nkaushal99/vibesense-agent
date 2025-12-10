from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class AgentContext:
    last_action: str = "keep_current"
    last_query: str = ""
    last_reason: str = ""
    last_intensity: float = 0.0
    last_action_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_store: Dict[str, AgentContext] = {}


def get_context(user_id: str) -> AgentContext:
    return _store.get(user_id, AgentContext())


def set_context(user_id: str, context: AgentContext) -> None:
    context.last_action_at = time.time()
    _store[user_id] = context
