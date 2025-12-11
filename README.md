# Vibe Sense (HeartStreamer backend)

Backend responsibilities are narrowed: receive heart-rate/context signals and return a structured mood suggestion the iOS app can act on. Spotify authentication, search, and playback now live entirely on the device (PKCE).

## Quick start
- Install deps: `uv pip install -r requirements.txt`
- Run the ingest API: `uvicorn heart_api:app --host 0.0.0.0 --port 8765`
- The agent client uses `fast-agent-mcp` for suggestions (see `fastagent.config.yaml` for provider configuration).

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
- User context and preferences are stored in `data/vibe_sense.db` (SQLite, override with `VIBE_SENSE_DB`). Preferences are optional but help ground suggestions (`preferred_genres`, `avoid_genres`, `favorite_artists`, `dislikes`, `energy_profile`, `notes`).
- `agent_client.generate_agent_suggestion` is async and uses fast-agent with a `get_user_profile` tool (reads the DB) to ground responses.
- `prompts.yaml` instructs the LLM to emit only the JSON suggestion per heart update. The FastAgent runtime no longer connects to Spotify MCP; the iOS app owns auth and playback.
- Env toggles: `FAST_AGENT_MODEL` / `FAST_AGENT_TEMPERATURE` to override defaults.
