"""Direct MCP round-trip — no LLM, no token spend, no Streamlit.

Verifies that the caura-memclaw tenant is wired up correctly:
  1. Agent A writes a uniquely-tagged canary memory under ``fleet_id``.
  2. Agent B (different agent_id, same fleet_id) recalls it by tag —
     proves cross-agent visibility in the shared fleet.

Run this whenever the dashboard "doesn't work" — it isolates whether
the problem is memclaw connectivity / credentials, or something
downstream (Streamlit, the surface integrations, the dashboard agent's
trust level, etc.).

Usage:
    python smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

from memclaw_mcp import call_memclaw_tool, open_mcp
from protocol import MemclawConfig

load_dotenv()


def _bail(msg: str, code: int = 1) -> int:
    print(f"❌ {msg}", file=sys.stderr)
    return code


def _ok(msg: str) -> None:
    print(f"✓ {msg}")


async def _round_trip(cfg: MemclawConfig) -> int:
    writer_id = "smoke-writer"
    reader_id = "smoke-reader"
    canary = uuid.uuid4().hex[:12]
    content = (
        f"SMOKE_TEST canary={canary} ts={datetime.now(timezone.utc).isoformat()} "
        f"— {writer_id} wrote this for {reader_id} to recall."
    )

    print(f"→ MCP endpoint: {cfg.mcp_url}")
    print(f"→ Tenant:       {cfg.tenant_id}")
    print(f"→ Fleet:        {cfg.fleet_id}")
    print(f"→ Canary:       {canary}\n")

    async with open_mcp(cfg) as session:
        _ok("MCP session initialized")

        listed = await session.list_tools()
        tool_names = {t.name for t in listed.tools}
        required = {"memclaw_write", "memclaw_recall"}
        missing = required - tool_names
        if missing:
            return _bail(
                f"server is missing required tools: {sorted(missing)}. "
                f"Available: {sorted(tool_names)}"
            )
        _ok(f"server exposes {len(tool_names)} tools (incl. memclaw_write + memclaw_recall)")

        write_text, write_err = await call_memclaw_tool(
            session,
            "memclaw_write",
            {"content": content, "agent_id": writer_id, "fleet_id": cfg.fleet_id},
        )
        if write_err:
            return _bail(f"memclaw_write failed as {writer_id}:\n{write_text}")
        _ok(f"{writer_id} wrote canary memory")
        print(f"   response: {write_text[:160]}{'…' if len(write_text) > 160 else ''}\n")

        recall_text, recall_err = await call_memclaw_tool(
            session,
            "memclaw_recall",
            {
                "query": f"SMOKE_TEST canary {canary}",
                "agent_id": reader_id,
                "fleet_id": cfg.fleet_id,
                "top_k": 10,
            },
        )
        if recall_err:
            return _bail(f"memclaw_recall failed as {reader_id}:\n{recall_text}")
        _ok(f"{reader_id} called memclaw_recall")

        if canary in recall_text:
            _ok(f"{reader_id} recalled {writer_id}'s canary ({canary}) — round-trip works")
            print("\n🎉 Smoke test passed.")
            return 0

        print("\n❌ Canary NOT found in reader's recall results.", file=sys.stderr)
        try:
            parsed = json.loads(recall_text)
            print(json.dumps(parsed, indent=2)[:2000], file=sys.stderr)
        except json.JSONDecodeError:
            print(recall_text[:2000], file=sys.stderr)
        print(
            "\nLikely causes:\n"
            "  • The two agent_ids aren't on the same fleet_id (check MEMCLAW_FLEET_ID).\n"
            "  • The memclaw server isn't returning fleet-scoped writes to recall.\n"
            "  • The write was async/indexed and the recall ran before indexing finished.",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    cfg = MemclawConfig.from_env()
    try:
        cfg.require()
    except RuntimeError as e:
        return _bail(str(e), code=2)
    try:
        return asyncio.run(_round_trip(cfg))
    except Exception as e:
        return _bail(f"round-trip threw an unexpected exception: {e!r}", code=1)


if __name__ == "__main__":
    raise SystemExit(main())
