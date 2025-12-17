"""SQLite connection + initialization utilities."""

import os
import sqlite3
from pathlib import Path
from threading import Lock


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.getenv("VIBE_SENSE_DB", ROOT_DIR / "data" / "vibe_sense.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db_lock = Lock()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
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


__all__ = ["DB_PATH", "db_lock", "get_conn", "init_db"]
