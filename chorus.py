"""Chorus — memclaw observability dashboard for a multi-surface AI agent fleet.

Per-surface activity cards on the left + a live memory feed on the
right. Memories arrive from native surfaces (Claude Desktop, ChatGPT)
you've wired into the shared caura-memclaw tenant.

Setup docs for native surfaces:
    docs/claude-desktop-setup.md, docs/openai-setup.md.

Run:
    streamlit run chorus.py
"""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from memclaw_mcp import (  # noqa: E402
    DASHBOARD_AGENT_ID,
    list_tenant_memories,
    open_mcp,
    register_dashboard_agent,
)
from config import MemclawConfig  # noqa: E402

_env_defaults = MemclawConfig.from_env()


st.set_page_config(page_title="Chorus · caura-memclaw", page_icon="🎼", layout="wide")


# ── Agent identities (one entry per native surface Chorus knows about) ──
AGENT_IDENTITIES: list[dict] = [
    {
        "agent_id": "claude-desktop",
        "display": "Claude Desktop",
        "subtitle": "Anthropic · desktop app",
        "emoji": "🟠",
        "color": "#D97757",
        "bg_tint": "rgba(217,119,87,0.10)",
        "setup_doc": "docs/claude-desktop-setup.md",
    },
    {
        "agent_id": "chatgpt",
        "display": "ChatGPT",
        "subtitle": "OpenAI · Custom GPT",
        "emoji": "🟢",
        "color": "#10A37F",
        "bg_tint": "rgba(16,163,127,0.10)",
        "setup_doc": "docs/openai-setup.md",
    },
]


def _ident(agent_id: str) -> dict | None:
    return next((i for i in AGENT_IDENTITIES if i["agent_id"] == agent_id), None)


# ── Styling ──────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  .tagline    { color: #888; font-style: italic; font-size: 0.95rem;
                margin-top: -10px; margin-bottom: 4px; }
  .subtagline { color: #555; font-size: 0.82rem; margin-bottom: 16px; }
  .agent-card { border: 1px solid; border-radius: 10px;
                padding: 12px 14px; margin-bottom: 10px; }
  .agent-card .name { font-weight: 700; font-size: 1.05rem; }
  .agent-card .sub  { font-size: 0.72rem; opacity: 0.75; margin-top: 2px; }
  .agent-card .stats { font-size: 0.72rem; margin-top: 8px; color: #555; }
  .mem-card   { border: 1px solid rgba(125,125,125,0.2);
                border-left: 4px solid #888; border-radius: 8px;
                padding: 4px 10px; margin: 3px 4px; font-size: 0.85rem;
                line-height: 1.25; }
  .mem-writer { font-size: 0.7rem; font-weight: 600; opacity: 0.85; }
  .mem-title  { font-weight: 600; margin-top: 0; }
  .mem-tag    { display: inline-block; font-size: 0.68rem;
                background: rgba(120,200,150,0.15); border-radius: 4px;
                padding: 1px 6px; margin: 2px 4px 0 0; }
  .feed-header { padding: 10px 14px; border-radius: 10px;
                 font-weight: 700; font-size: 1rem;
                 background: rgba(120,80,200,0.10);
                 border: 1px solid #7850c8; color: #5a3aa3;
                 margin-bottom: 12px; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Helpers ─────────────────────────────────────────────────────────
def elevate_dashboard_trust(
    api_url: str, api_key: str, tenant_id: str, agent_id: str = DASHBOARD_AGENT_ID
) -> tuple[bool, str]:
    """PATCH the dashboard agent's trust_level to 2 so scope='all' reads
    succeed. Idempotent — setting trust=2 when already 2 is a no-op.
    Returns (ok, message). Requires the key's tenant to match ``tenant_id``."""
    url = (
        f"{api_url.rstrip('/')}/api/v1/agents/{agent_id}/trust"
        f"?tenant_id={tenant_id}"
    )
    req = urllib.request.Request(
        url,
        method="PATCH",
        headers={
            "X-API-Key": api_key,
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json",
        },
        data=b'{"trust_level": 2}',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
    except Exception as e:
        return False, repr(e)


def fetch_memories(
    api_url: str, api_key: str, tenant_id: str, fleet_id: str
) -> list[dict] | dict:
    """Fetch the live memory feed. Self-heals two first-run conditions:
    the dashboard agent not being registered yet (one bootstrap write),
    and its trust_level being too low for scope='all' (one PATCH). On
    other errors, returns ``{"error": "..."}`` so the caller can render
    a banner."""
    cfg = MemclawConfig(
        api_url=api_url, api_key=api_key, tenant_id=tenant_id, fleet_id=fleet_id
    )

    async def gather() -> tuple[list[dict], str]:
        async with open_mcp(cfg) as session:
            rows, err = await list_tenant_memories(session)
            # First-run bootstrap: if the dashboard agent isn't registered
            # yet, write a marker memory so the row exists, then retry.
            if err and "is not registered" in err:
                await register_dashboard_agent(session, fleet_id=fleet_id)
                rows, err = await list_tenant_memories(session)
            return rows, err

    try:
        rows, err = asyncio.run(gather())
    except Exception as e:
        return {"error": str(e)}

    # Auto-elevate trust on the dashboard agent if the list call was
    # rejected at the trust gate. scope='all' requires trust ≥ 2;
    # newly registered agents default to 1. The PATCH is idempotent.
    if err and "trust_level=" in err and "required 2" in err:
        ok, msg = elevate_dashboard_trust(api_url, api_key, tenant_id)
        if not ok:
            return {"error": f"auto trust-elevation failed: {msg}"}
        try:
            rows, err = asyncio.run(gather())
        except Exception as e:
            return {"error": str(e)}

    if err:
        return {"error": err}
    return rows


def erase_all_memories(api_url: str, api_key: str, tenant_id: str) -> tuple[bool, str]:
    """Soft-delete every memory in the tenant via DELETE /api/v1/memories.

    Server-side bulk delete — one round-trip, no need to enumerate IDs
    first. Returns (ok, message). Soft-delete preserves the rows with
    deleted_at set; full purge would require a separate hard-delete
    path."""
    url = f"{api_url.rstrip('/')}/api/v1/memories?tenant_id={tenant_id}"
    req = urllib.request.Request(
        url,
        method="DELETE",
        headers={
            "X-API-Key": api_key,
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
    except Exception as e:
        return False, repr(e)


def format_relative(iso_str: str) -> str:
    if not iso_str:
        return "never"
    try:
        # Python 3.11+ fromisoformat handles trailing Z natively.
        secs = int((datetime.now(timezone.utc) - datetime.fromisoformat(iso_str)).total_seconds())
    except Exception:
        return "unknown"
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Chorus config")
    api_url = st.text_input("memclaw URL", value=_env_defaults.api_url)
    api_key = st.text_input("API key", value=_env_defaults.api_key, type="password")
    tenant_id = st.text_input("Tenant ID", value=_env_defaults.tenant_id)
    fleet_id = st.text_input("Fleet ID", value=_env_defaults.fleet_id)

    st.divider()
    # Two-click confirm so a stray click can't nuke the tenant.
    if st.session_state.get("confirm_erase"):
        st.warning(
            f"⚠ Soft-delete EVERY memory in tenant `{tenant_id}`? "
            "This includes writes from all surfaces, not just Chorus."
        )
        c_yes, c_no = st.columns(2)
        if c_yes.button("🔥 Yes, erase", use_container_width=True, type="primary"):
            ok, msg = erase_all_memories(api_url, api_key, tenant_id)
            st.session_state["confirm_erase"] = False
            if ok:
                st.session_state["memories"] = []
                st.toast("Memories erased.")
                st.rerun()
            else:
                st.error(f"Erase failed: {msg}")
        if c_no.button("Cancel", use_container_width=True):
            st.session_state["confirm_erase"] = False
            st.rerun()
    else:
        if st.button("🔥 Erase all memories", use_container_width=True):
            st.session_state["confirm_erase"] = True
            st.rerun()

    st.divider()
    st.markdown(
        "### Native surfaces\n"
        "Configure your native LLM clients to write into this tenant. "
        "Then watch the activity stream.\n\n"
        "- `docs/claude-desktop-setup.md` — 🟠 Claude Desktop\n"
        "- `docs/openai-setup.md` — 🟢 ChatGPT"
    )


# ── Header ───────────────────────────────────────────────────────────
st.markdown("# 🎼 Chorus")
st.markdown(
    '<div class="tagline">Many surfaces. Many agents. One memory.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtagline">The memclaw observability dashboard for a multi-surface AI agent fleet.</div>',
    unsafe_allow_html=True,
)


# ── Bail if creds incomplete ─────────────────────────────────────────
if not api_key or not tenant_id:
    st.warning("Set memclaw API key + tenant ID in the sidebar to start.")
    st.stop()


# ── Memory fetch (once per render unless invalidated) ───────────────
if "memories" not in st.session_state:
    st.session_state["memories"] = fetch_memories(
        api_url, api_key, tenant_id, fleet_id
    )

mems_raw = st.session_state["memories"]
mems: list[dict] = mems_raw if isinstance(mems_raw, list) else []
fetch_error = mems_raw.get("error") if isinstance(mems_raw, dict) else None


# ── Dashboard ───────────────────────────────────────────────────────
def render_agent_card(ident: dict) -> None:
    writer_mems = [m for m in mems if m.get("__written_by") == ident["agent_id"]]
    count = len(writer_mems)
    last_seen = format_relative(writer_mems[0].get("created_at", "")) if writer_mems else "never"

    st.markdown(
        f'<div class="agent-card" style="border-color:{ident["color"]};'
        f'background:{ident["bg_tint"]}">'
        f'<div class="name" style="color:{ident["color"]}">'
        f'{ident["emoji"]} {ident["display"]}'
        f'</div>'
        f'<div class="sub">{ident["subtitle"]}</div>'
        f'<div class="stats"><b>{count}</b> recent writes · '
        f'last seen {last_seen}</div>'
        f'<div class="stats" style="margin-top:4px;opacity:0.6">'
        f'setup: <code>{ident["setup_doc"]}</code></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_memory_feed() -> None:
    header_col, button_col = st.columns([5, 1])
    with header_col:
        st.markdown(
            '<div class="feed-header">🧠 caura-memclaw — live memory feed</div>',
            unsafe_allow_html=True,
        )
    with button_col:
        if st.button("🔄 Refresh", use_container_width=True, key="dash_refresh"):
            st.session_state["memories"] = fetch_memories(
                api_url, api_key, tenant_id, fleet_id
            )
            st.rerun()

    if fetch_error:
        st.error(f"Could not fetch memories: {fetch_error}")
        return
    if not mems:
        st.info(
            "No memories yet. Configure a native surface (see sidebar) and "
            "write one — it'll appear here on next refresh."
        )
        return

    counts = {ident["agent_id"]: 0 for ident in AGENT_IDENTITIES}
    for m in mems:
        if m.get("__written_by") in counts:
            counts[m["__written_by"]] += 1
    summary_parts = [f"{_ident(k)['display']}: {v}" for k, v in counts.items() if v]
    plural = "y" if len(mems) == 1 else "ies"
    summary_tail = ("  ·  " + "  ·  ".join(summary_parts)) if summary_parts else ""
    st.caption(
        f"**{len(mems)} memor{plural}** across tenant "
        f"`{tenant_id}` (all fleets){summary_tail}"
    )

    for m in mems:
        writer = m.get("__written_by", "")
        ident = _ident(writer)
        color = ident["color"] if ident else "#888"
        bg = ident["bg_tint"] if ident else "rgba(125,125,125,0.05)"

        meta = m.get("metadata") or {}
        title = m.get("title") or (m.get("content") or "")[:60] or "(untitled)"
        summary = m.get("summary") or meta.get("summary") or ""
        tags = m.get("tags") or meta.get("tags") or []
        mtype = m.get("memory_type") or m.get("type") or ""
        when = format_relative(m.get("created_at", ""))

        inner = []
        if ident:
            inner.append(
                f'<div class="mem-writer" style="color:{color}">'
                f'{ident["emoji"]} {ident["display"]} '
                f'<span style="opacity:0.5;font-weight:400">· {when}</span></div>'
            )
        else:
            inner.append(
                f'<div class="mem-writer" style="color:#888">unknown writer · {when}</div>'
            )
        inner.append(f'<div class="mem-title">{title}</div>')
        if mtype:
            inner.append(f'<div style="font-size:0.7rem;opacity:0.6">{mtype}</div>')
        if summary:
            inner.append(f'<div style="opacity:0.85;margin-top:1px">{summary}</div>')
        if tags:
            inner.append("".join(f'<span class="mem-tag">#{t}</span>' for t in tags))
        st.markdown(
            f'<div class="mem-card" style="border-left-color:{color};'
            f'background:{bg}">{"".join(inner)}</div>',
            unsafe_allow_html=True,
        )


left, right = st.columns([1, 2])

with left:
    st.markdown("### Surfaces")
    for ident in AGENT_IDENTITIES:
        render_agent_card(ident)

with right:
    render_memory_feed()
