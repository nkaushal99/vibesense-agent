"""DB-related dataclasses and helpers independent of SQLite plumbing."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List

import sqlite3


@dataclass
class AgentContext:
    last_action: str = "keep_current"
    last_query: str = ""
    last_reason: str = ""
    last_intensity: float = 0.0
    last_action_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row | None) -> "AgentContext":
        if not row:
            return cls()
        return cls(
            last_action=str(row["last_action"]),
            last_query=str(row["last_query"]),
            last_reason=str(row["last_reason"]),
            last_intensity=float(row["last_intensity"]),
            last_action_at=float(row["last_action_at"]),
        )


@dataclass
class UserPreferences:
    preferred_genres: List[str] | None = None
    avoid_genres: List[str] | None = None
    favorite_artists: List[str] | None = None
    dislikes: List[str] | None = None
    notes: str = ""
    energy_profile: str = ""

    def __post_init__(self) -> None:
        # Ensure list defaults are not shared across instances.
        self.preferred_genres = list(self.preferred_genres or [])
        self.avoid_genres = list(self.avoid_genres or [])
        self.favorite_artists = list(self.favorite_artists or [])
        self.dislikes = list(self.dislikes or [])

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row | None) -> "UserPreferences":
        if not row:
            return cls()
        return cls(
            preferred_genres=_load_list(row["preferred_genres"]),
            avoid_genres=_load_list(row["avoid_genres"]),
            favorite_artists=_load_list(row["favorite_artists"]),
            dislikes=_load_list(row["dislikes"]),
            notes=str(row["notes"]),
            energy_profile=str(row["energy_profile"]),
        )


def _dump_list(values: Iterable[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def _load_list(raw: str | None) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        return []
    return []


__all__ = ["AgentContext", "UserPreferences", "_dump_list", "_load_list"]
