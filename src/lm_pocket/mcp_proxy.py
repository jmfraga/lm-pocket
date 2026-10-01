"""MCP stdio server: a thin proxy to the running LM-Pocket Local.

The MCP client launches this process with a fixed --profile. It holds no
keys and no data: every call is forwarded to the daemon, which enforces the
profile, audits, and answers "locked" when the pocket is locked or unplugged.

Tool names use underscores (not `pocket.search_memories` as in SPEC § 12):
several clients reject dots in tool names. See docs/spec-conflicts.md #1.
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import Context, FastMCP

from . import runtime


class PocketUnavailable(Exception):
    pass


def _client_name(ctx: Context | None) -> str | None:
    try:
        info = ctx.session.client_params.clientInfo
        return f"{info.name}/{info.version}" if info.version else info.name
    except Exception:
        return None


def build_server(profile: str) -> FastMCP:
    mcp = FastMCP(
        "lm-pocket",
        instructions=(
            "LM-Pocket is the user's own long-term memory, stored on a device they control. "
            f"This connection uses the '{profile}' permission profile: you can only read the spaces it allows. "
            "Use search_memories or get_context before answering questions that depend on the user's history "
            "or preferences, and cite memory ids when you rely on them. "
            "propose_memory only creates a candidate: the user reviews it before it becomes part of their memory. "
            "Propose only things the user actually said or clearly confirmed; mark inferences as type "
            "'interpretation' with low confidence. If a call says the pocket is locked, tell the user."
        ),
    )

    def forward(tool: str, args: dict, ctx: Context | None):
        info = runtime.read()
        if not info:
            raise PocketUnavailable("LM-Pocket is not open on this computer (run `lm-pocket open <folder>`).")
        try:
            r = httpx.post(
                f"http://127.0.0.1:{info['port']}/api/v1/call",
                headers={"Authorization": f"Bearer {info['api_token']}", "Host": f"127.0.0.1:{info['port']}"},
                json={"profile": profile, "tool": tool, "args": args, "client": _client_name(ctx)},
                timeout=15,
            )
        except httpx.HTTPError as exc:
            raise PocketUnavailable("LM-Pocket is not running (the app was closed).") from exc
        body = r.json()
        if not body.get("ok"):
            err = body.get("error", {})
            raise PocketUnavailable(f"{err.get('code', 'error')}: {err.get('message', '')}".strip())
        return body["result"]

    @mcp.tool()
    def get_profile(ctx: Context) -> dict:
        """What this connection may do: readable spaces and where proposals go."""
        return forward("get_profile", {}, ctx)

    @mcp.tool()
    def list_spaces(ctx: Context) -> list:
        """Spaces of the user's memory that this profile can read."""
        return forward("list_spaces", {}, ctx)

    @mcp.tool()
    def search_memories(query: str, ctx: Context, limit: int = 10, space: str | None = None) -> list:
        """Full-text search over the user's durable memories (accent-insensitive). Empty query = most recent.
        Each result includes provenance: who stated it, how and when."""
        return forward("search_memories", {"query": query, "limit": limit, "space": space}, ctx)

    @mcp.tool()
    def get_memory(id: str, ctx: Context) -> dict:
        """One memory by id."""
        return forward("get_memory", {"id": id}, ctx)

    @mcp.tool()
    def get_context(ctx: Context, topic: str = "", purpose: str = "", max_tokens: int = 800) -> dict:
        """A compact, budgeted context package about a topic, grouped by preferences, history, goals and
        inferences. Prefer this at the start of a task."""
        return forward("get_context", {"topic": topic, "purpose": purpose, "max_tokens": max_tokens}, ctx)

    @mcp.tool()
    def get_recent_context(ctx: Context, limit: int = 10) -> list:
        """The most recently updated durable memories this profile can read."""
        return forward("get_recent_context", {"limit": limit}, ctx)

    @mcp.tool()
    def get_policies(ctx: Context) -> dict:
        """Read-only view of this profile's rules."""
        return forward("get_policies", {}, ctx)

    @mcp.tool()
    def propose_memory(
        content: str,
        ctx: Context,
        type: str = "fact",
        confidence: float = 0.5,
        tags: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict:
        """Propose a new memory about the user. It is saved as a CANDIDATE that the user must approve.
        type: fact | preference | event | interpretation | skill | decision | relationship | goal.
        Use 'interpretation' for anything inferred. provider/model: identify yourself for provenance."""
        args = {"content": content, "type": type, "confidence": confidence, "tags": tags or [],
                "provider": provider, "model": model}
        return forward("propose_memory", args, ctx)

    return mcp


def run(profile: str) -> None:
    build_server(profile).run("stdio")
