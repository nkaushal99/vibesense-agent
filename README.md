# Vibe Sense (HeartStreamer backend)

Backend responsibilities are narrowed: receive heart-rate/context signals and return a structured mood suggestion the iOS app can act on. Spotify authentication, search, and playback now live entirely on the device (PKCE).

Key code paths:
- `vibesense/app/heart_core.py`: heart-rate smoothing + domain logic.
- `vibesense/app/heart_api.py`: heart ingest + suggestion router (no DB concerns).
- `vibesense/app/db_api.py`: preferences router for DB-backed settings.
- `vibesense/app/api.py`: assembles the FastAPI app from the separate routers.
- `vibesense/db/backend.py`: database backend abstraction (default: SQLite via `VIBE_SENSE_BACKEND=sqlite`).
- `vibesense/db/context_store.py`: context persistence (last action/query/reason).
- `vibesense/db/preferences_store.py`: preferences persistence (genres/artists/energy).
- `vibesense/db/profile_store.py`: aggregates context + preferences for tools.
- `vibesense/agent/fast_agent_client.py`: FastAgent wiring and suggestion generation.
- `vibesense/tools/database.py`: fastmcp server exposing user profile/context tools.
- `vibesense/agent/fastagent.config.yaml`: model + MCP server configuration.

## DB backend
- Default backend is SQLite; future adapters can be swapped via `VIBE_SENSE_BACKEND` (or `configure_backend(...)` in code).
- The public `vibesense.db` functions (`get_context`, `set_context`, `get_preferences`, `set_preferences`, `get_user_profile`) route through the configured backend, keeping callers agnostic of storage.

## Quick start
- Install deps: `uv pip install -r requirements.txt`
- Run the ingest API (boots FastAgent too): `python -m vibesense.main`  
  - Override host/port with `HOST` / `PORT` env vars.
- Run the MCP tools server (stdio by default): `python -m vibesense.tools.database`
- The agent client uses `fast-agent-mcp` for suggestions (see `vibesense/agent/fastagent.config.yaml` for provider configuration and MCP wiring).

## API
- `POST /ingest`
  - Body: `{"bpm": 82, "mood": "focused", "user_id": "abc"}`
  - Returns: latest stabilized heart state + a mood suggestion.
- `GET /suggestion?user_id=abc`
  - Returns the most recent suggestion for that user (or derives one from the latest heart state).
- `GET /health?user_id=abc`
  - Returns status plus latest heart state and suggestion if available.
- `POST /preferences`
  - Body: `{"user_id": "abc", "preferred_genres": ["lofi"], "avoid_genres": ["metal"], "favorite_artists": [], "notes": "no explicit"}`
  - Persists user-level preferences the agent can fetch via its DB tool.
- `GET /preferences?user_id=abc`
  - Returns the stored context + preferences for that user.

## Suggestion contract
Responses use:
```json
{
  "user_id": "abc",
  "mood": "focus",
  "intensity": 0.35,
  "suggested_action": "play_playlist",
  "search_query": "lofi steady focus beats",
  "reason": "82 bpm in light zone → focus vibe",
  "generated_at": 1730000000.0,
  "heart": { "...": "original heart snapshot" }
}
```
`search_query` is ready for Spotify search on-device; the backend never handles tokens or playback.

## Agent behavior
- User context and preferences are stored in `data/vibe_sense.db` (SQLite, override with `VIBE_SENSE_DB`) via `vibesense.db.profile_store`. Preferences are optional but help ground suggestions (`preferred_genres`, `avoid_genres`, `favorite_artists`, `dislikes`, `energy_profile`, `notes`).
- `vibesense.agent.generate_agent_suggestion` is async and uses fast-agent with a `get_user_profile` tool (reads the DB) to ground responses.
- `vibesense/agent/prompts.yaml` instructs the LLM to emit only the JSON suggestion per heart update. The FastAgent runtime no longer connects to Spotify MCP; the iOS app owns auth and playback.
- Env toggles: `FAST_AGENT_MODEL` / `FAST_AGENT_TEMPERATURE` to override defaults.
