"""Context persistence (action/query/intensity) isolated from preferences."""

from __future__ import annotations

import time

from vibesense.db.connection import db_lock, get_conn, init_db
from vibesense.db.models import AgentContext


def get_context(user_id: str) -> AgentContext:
    init_db()
    with db_lock, get_conn() as conn:
        row = conn.execute(
            "SELECT last_action, last_query, last_reason, last_intensity, last_action_at "
            "FROM user_context WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return AgentContext.from_row(row)


def set_context(user_id: str, context: AgentContext) -> None:
    init_db()
    now = time.time()
    last_action_at = context.last_action_at or now
    context.last_action_at = last_action_at
    with db_lock, get_conn() as conn:
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


__all__ = ["get_context", "set_context"]
