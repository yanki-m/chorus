"""MCP plumbing for the Chorus dashboard.

Opens a streamable-HTTP MCP session against `<api>/mcp/` and exposes
helpers the dashboard uses:

- `open_mcp(cfg)` — async context manager that yields a ready session.
- `call_memclaw_tool(...)` — wraps `session.call_tool` and flattens the
  result into `(text, is_error)`.
- `list_tenant_memories(...)` — `memclaw_list` with `scope='all'` so the
  dashboard sees every writer's memories under the tenant.
- `register_dashboard_agent(...)` — one bootstrap write so the
  `chorus-dashboard` agent row exists; trust elevation is a separate
  REST PATCH handled in `chorus.py`.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from protocol import MemclawConfig


@asynccontextmanager
async def open_mcp(cfg: MemclawConfig) -> AsyncIterator[ClientSession]:
    """Async context manager that yields a ready-to-use MCP ClientSession."""
    async with streamablehttp_client(cfg.mcp_url, headers=cfg.headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            yield session


def stringify(result: Any) -> tuple[str, bool]:
    """Flatten an MCP tool-call result into (text, is_error)."""
    text = "\n".join(getattr(b, "text", "") for b in (result.content or []))
    is_err = bool(getattr(result, "isError", False))
    return text or "(empty)", is_err


async def call_memclaw_tool(
    session: ClientSession, name: str, args: dict
) -> tuple[str, bool]:
    """Call a memclaw_* MCP tool and return its text + error flag."""
    result = await session.call_tool(name, args)
    return stringify(result)


DASHBOARD_AGENT_ID = "chorus-dashboard"


async def list_tenant_memories(
    session: ClientSession,
    *,
    agent_id: str = DASHBOARD_AGENT_ID,
    limit: int = 50,
) -> tuple[list[dict], str]:
    """List every writer's memories visible to the caller's tenant
    (scope='all'). Requires trust ≥ 2 on ``agent_id``.

    Returns ``(rows, error_text)``; ``error_text`` is empty on success.
    Each row is tagged ``__written_by`` from its ``agent_id`` so the
    dashboard can attribute writes from any surface — including ones
    that write with ``fleet_id=NULL`` (e.g., Claude Desktop's default
    mcp-remote config)."""
    text, is_err = await call_memclaw_tool(
        session,
        "memclaw_list",
        {
            "agent_id": agent_id,
            "scope": "all",
            "limit": limit,
            "sort": "created_at",
            "order": "desc",
        },
    )
    if is_err:
        return [], text or "unknown MCP error"
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return [], f"non-JSON response: {text[:200]}"
    if isinstance(body, dict):
        items = body.get("results") or body.get("items") or body.get("memories") or []
    elif isinstance(body, list):
        items = body
    else:
        items = []
    for m in items:
        m["__written_by"] = m.get("agent_id") or ""
    return items, ""


async def register_dashboard_agent(
    session: ClientSession,
    *,
    fleet_id: str,
    agent_id: str = DASHBOARD_AGENT_ID,
) -> tuple[str, bool]:
    """Write one bootstrap memory under ``agent_id`` so the agent row
    exists in ``agents``. caura-memclaw materialises the row on first
    write — without it, ``require_trust`` returns ``not_registered``.
    Trust elevation (≥ 2 for fleet reads) is a separate PATCH call."""
    return await call_memclaw_tool(
        session,
        "memclaw_write",
        {
            "agent_id": agent_id,
            "fleet_id": fleet_id,
            "content": "chorus-dashboard online",
        },
    )
