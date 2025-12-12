"""Preferences persistence helpers (genres/artists/energy/etc.)."""

from __future__ import annotations

import time
from typing import Any, Dict

from vibesense.db.connection import db_lock, get_conn, init_db
from vibesense.db.models import UserPreferences, _dump_list


def get_preferences(user_id: str) -> UserPreferences:
    init_db()
    with db_lock, get_conn() as conn:
        row = conn.execute(
            """
            SELECT preferred_genres, avoid_genres, favorite_artists, dislikes, notes, energy_profile
            FROM user_preferences WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return UserPreferences.from_row(row)


def set_preferences(user_id: str, preferences: UserPreferences | Dict[str, Any]) -> UserPreferences:
    init_db()
    pref = preferences if isinstance(preferences, UserPreferences) else UserPreferences(**preferences)
    now = time.time()
    with db_lock, get_conn() as conn:
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


__all__ = ["get_preferences", "set_preferences"]
