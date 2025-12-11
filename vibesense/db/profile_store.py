"""Persistence layer for user context and preferences."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("VIBE_SENSE_DB", ROOT_DIR / "data" / "vibe_sense.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_lock = Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_context (
                user_id TEXT PRIMARY KEY,
                last_action TEXT NOT NULL,
                last_query TEXT NOT NULL,
                last_reason TEXT NOT NULL,
                last_intensity REAL NOT NULL,
                last_action_at REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferred_genres TEXT NOT NULL,
                avoid_genres TEXT NOT NULL,
                favorite_artists TEXT NOT NULL,
                dislikes TEXT NOT NULL,
                notes TEXT NOT NULL,
                energy_profile TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )


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
    preferred_genres: List[str] = None
    avoid_genres: List[str] = None
    favorite_artists: List[str] = None
    dislikes: List[str] = None
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


def get_context(user_id: str) -> AgentContext:
    _init_db()
    with _lock, _get_conn() as conn:
        row = conn.execute(
            "SELECT last_action, last_query, last_reason, last_intensity, last_action_at "
            "FROM user_context WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return AgentContext.from_row(row)


def set_context(user_id: str, context: AgentContext) -> None:
    _init_db()
    now = time.time()
    last_action_at = context.last_action_at or now
    context.last_action_at = last_action_at
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_context (
                user_id, last_action, last_query, last_reason, last_intensity, last_action_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_action=excluded.last_action,
                last_query=excluded.last_query,
                last_reason=excluded.last_reason,
                last_intensity=excluded.last_intensity,
                last_action_at=excluded.last_action_at,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                context.last_action,
                context.last_query,
                context.last_reason,
                float(context.last_intensity),
                float(last_action_at),
                now,
                now,
            ),
        )


def get_preferences(user_id: str) -> UserPreferences:
    _init_db()
    with _lock, _get_conn() as conn:
        row = conn.execute(
            """
            SELECT preferred_genres, avoid_genres, favorite_artists, dislikes, notes, energy_profile
            FROM user_preferences WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return UserPreferences.from_row(row)


def set_preferences(user_id: str, preferences: UserPreferences | Dict[str, Any]) -> UserPreferences:
    _init_db()
    pref = preferences if isinstance(preferences, UserPreferences) else UserPreferences(**preferences)
    now = time.time()
    with _lock, _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                user_id, preferred_genres, avoid_genres, favorite_artists, dislikes, notes, energy_profile, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_genres=excluded.preferred_genres,
                avoid_genres=excluded.avoid_genres,
                favorite_artists=excluded.favorite_artists,
                dislikes=excluded.dislikes,
                notes=excluded.notes,
                energy_profile=excluded.energy_profile,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                _dump_list(pref.preferred_genres),
                _dump_list(pref.avoid_genres),
                _dump_list(pref.favorite_artists),
                _dump_list(pref.dislikes),
                pref.notes,
                pref.energy_profile,
                now,
                now,
            ),
        )
    return pref


def get_user_profile(user_id: str) -> Dict[str, Any]:
    """Fetch aggregated state/preferences for agent tools."""

    return {
        "context": get_context(user_id).to_dict(),
        "preferences": get_preferences(user_id).to_dict(),
    }


__all__ = [
    "AgentContext",
    "UserPreferences",
    "get_context",
    "set_context",
    "get_preferences",
    "set_preferences",
    "get_user_profile",
]
