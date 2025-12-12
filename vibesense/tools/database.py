"""Expose user profile/context as MCP tools via fastmcp."""

from typing import Any, Dict

from fastmcp import FastMCP

from vibesense.db import get_context, get_user_profile

server = FastMCP(
    name="database",
    instructions="Provide user profile and context for VibeSense personalization.",
)


@server.tool(
    name="get_user_profile",
    description="Fetch stored context + preferences for a user so music suggestions stay personalized.",
)
async def tool_get_user_profile(user_id: str = "default") -> Dict[str, Any]:
    return get_user_profile(user_id or "default")


@server.tool(
    name="get_user_context",
    description="Fetch only the last context (action/query/reason) for a user.",
)
async def tool_get_user_context(user_id: str = "default") -> Dict[str, Any]:
    return get_context(user_id or "default").to_dict()


@server.tool(
    name="get_user_preferences",
    description="Fetch only the preferences for a user.",
)
async def tool_get_user_context(user_id: str = "default") -> Dict[str, Any]:
    return get_context(user_id or "default").to_dict()


def run() -> None:
    """Run the MCP server. Defaults to stdio transport."""

    server.run(transport='stdio')


if __name__ == "__main__":
    run()
