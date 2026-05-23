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
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from memclaw_mcp import (  # noqa: E402
    DASHBOARD_AGENT_ID,
    fetch_insights,
    fetch_tenant_stats,
    list_tenant_memories,
    open_mcp,
    register_dashboard_agent,
    semantic_recall,
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
  .mem-badge  { display: inline-block; font-size: 0.65rem;
                padding: 0 4px; margin-left: 4px; opacity: 0.75;
                vertical-align: middle; }
  .mem-recall { display: inline-block; font-size: 0.65rem;
                background: rgba(255,193,7,0.18); color: #8a6500;
                border-radius: 4px; padding: 0 5px; margin-left: 6px; }
  @keyframes pulse-recall {
    0%   { box-shadow: 0 0 0 0 rgba(255,193,7,0.55); }
    50%  { box-shadow: 0 0 14px 3px rgba(255,193,7,0.35); }
    100% { box-shadow: 0 0 0 0 rgba(255,193,7,0); }
  }
  .mem-card.pulse { animation: pulse-recall 1.5s ease-in-out; }
  .feed-header { padding: 10px 14px; border-radius: 10px;
                 font-weight: 700; font-size: 1rem;
                 background: rgba(120,80,200,0.10);
                 border: 1px solid #7850c8; color: #5a3aa3;
                 margin-bottom: 12px; }
  .kpi        { border: 1px solid rgba(120,80,200,0.25); border-radius: 10px;
                padding: 8px 14px; background: rgba(120,80,200,0.04); }
  .kpi .val   { font-size: 1.6rem; font-weight: 700; color: #5a3aa3;
                line-height: 1.1; }
  .kpi .lab   { font-size: 0.72rem; color: #666; margin-top: 2px; }
  .kpi-sub    { font-size: 0.72rem; color: #555; margin-top: 4px;
                line-height: 1.45; }
  a.inline-refresh { font-size: 1rem; text-decoration: none; color: #888;
                     cursor: pointer; margin-left: 10px;
                     transition: color 0.15s; vertical-align: middle; }
  a.inline-refresh:hover { color: #222; }
  /* Narrow the sidebar — defaults to ~330px, drop to ~240. */
  section[data-testid="stSidebar"] { width: 240px !important;
                                     min-width: 240px !important; }
  .section-h  { font-size: 1.4rem; font-weight: 700; margin: 8px 0 4px 0; }
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


def _run_mcp(cfg: MemclawConfig, coro_factory):
    """Open one MCP session, run the supplied coroutine, return its result
    or wrap exceptions into the helper's ``(value, error_str)`` shape."""
    async def gather():
        async with open_mcp(cfg) as session:
            return await coro_factory(session)
    try:
        return asyncio.run(gather())
    except Exception as e:
        return None, str(e)


def fetch_recall(cfg: MemclawConfig, query: str, top_k: int = 10) -> tuple[list[dict], str]:
    result = _run_mcp(cfg, lambda s: semantic_recall(s, query=query, top_k=top_k))
    return result if result[0] is not None else ([], result[1])


def fetch_insights_sync(cfg: MemclawConfig, focus: str) -> tuple[dict, str]:
    result = _run_mcp(cfg, lambda s: fetch_insights(s, focus=focus, scope="all"))
    return result if result[0] is not None else ({}, result[1])


def fetch_stats_sync(cfg: MemclawConfig) -> tuple[dict, str]:
    result = _run_mcp(cfg, lambda s: fetch_tenant_stats(s, scope="all"))
    return result if result[0] is not None else ({}, result[1])


# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Chorus config")
    api_url = st.text_input("memclaw URL", value=_env_defaults.api_url)
    api_key = st.text_input("API key", value=_env_defaults.api_key, type="password")
    tenant_id = st.text_input("Tenant ID", value=_env_defaults.tenant_id)
    fleet_id = st.text_input("Fleet ID", value=_env_defaults.fleet_id)

    auto_refresh = st.toggle(
        "Auto-refresh feed (30s)",
        value=False,
        key="auto_refresh",
        help="Re-fetches the memory feed every 30 seconds. Cards pulse when their recall_count changes between polls.",
    )

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


cfg = MemclawConfig(
    api_url=api_url, api_key=api_key, tenant_id=tenant_id, fleet_id=fleet_id
)


# ── Data fetch + pulse tracking ─────────────────────────────────────
def do_full_refresh() -> None:
    """Re-fetch memories + stats; diff recall_count against the previous
    fetch so the feed can pulse cards whose recall_count just increased."""
    new_memories = fetch_memories(api_url, api_key, tenant_id, fleet_id)
    if isinstance(new_memories, list):
        prev_recalls = st.session_state.get("prev_recalls", {})
        new_recalls = {
            m.get("id"): m.get("recall_count", 0) for m in new_memories if m.get("id")
        }
        st.session_state["pulsed_ids"] = {
            mid
            for mid, rc in new_recalls.items()
            if mid in prev_recalls and prev_recalls[mid] != rc
        }
        st.session_state["prev_recalls"] = new_recalls
    st.session_state["memories"] = new_memories
    stats, _ = fetch_stats_sync(cfg)
    st.session_state["stats"] = stats


if "memories" not in st.session_state:
    do_full_refresh()


# ── Render helpers ──────────────────────────────────────────────────
def render_stats_strip() -> None:
    stats = st.session_state.get("stats") or {}
    mems_raw = st.session_state.get("memories", [])
    mems_local = mems_raw if isinstance(mems_raw, list) else []

    total = stats.get("total")
    if total is None:
        total = len(mems_local)
    by_agent: dict = dict(stats.get("by_agent") or {})
    if not by_agent and mems_local:
        for m in mems_local:
            aid = m.get("agent_id")
            if aid:
                by_agent[aid] = by_agent.get(aid, 0) + 1
    last_write = format_relative(mems_local[0].get("created_at", "")) if mems_local else "never"

    # Per-surface breakdown inside the memories KPI
    breakdown_lines: list[str] = []
    known_ids = {i["agent_id"] for i in AGENT_IDENTITIES}
    for ident in AGENT_IDENTITIES:
        count = by_agent.get(ident["agent_id"], 0)
        if count > 0:
            breakdown_lines.append(
                f'<div class="kpi-sub">'
                f'<span style="color:{ident["color"]}">{ident["emoji"]} {ident["display"]}</span>'
                f' · {count}</div>'
            )
    other_count = sum(v for k, v in by_agent.items() if k not in known_ids)
    if other_count > 0:
        breakdown_lines.append(
            f'<div class="kpi-sub" style="color:#888">other · {other_count}</div>'
        )
    breakdown_html = "".join(breakdown_lines)

    c1, c2 = st.columns([2, 1])
    c1.markdown(
        f'<div class="kpi"><div class="val">{total}</div>'
        f'<div class="lab">memories</div>'
        f'{breakdown_html}</div>',
        unsafe_allow_html=True,
    )
    c2.markdown(
        f'<div class="kpi"><div class="val">{last_write}</div>'
        f'<div class="lab">last write</div></div>',
        unsafe_allow_html=True,
    )


def render_agent_card(ident: dict) -> None:
    mems_local = st.session_state.get("memories") or []
    if not isinstance(mems_local, list):
        mems_local = []
    writer_mems = [m for m in mems_local if m.get("__written_by") == ident["agent_id"]]
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


def render_recall_section() -> None:
    with st.expander("🔍 Semantic recall  ·  `memclaw_recall`", expanded=False):
        st.caption(
            "Natural-language query against the tenant. Hybrid semantic + "
            "keyword retrieval with graph-enhanced expansion (up to 2 hops)."
        )
        query = st.text_input(
            "Query",
            key="recall_query_input",
            placeholder="What does memclaw know about… ?",
            label_visibility="collapsed",
        )
        cols = st.columns([3, 1, 1])
        if cols[1].button("Search", type="primary", use_container_width=True, key="recall_btn"):
            if query.strip():
                results, err = fetch_recall(cfg, query.strip())
                st.session_state["recall_result"] = (results, err, query.strip())
        if cols[2].button("Clear", use_container_width=True, key="recall_clear"):
            st.session_state.pop("recall_result", None)

        result_tuple = st.session_state.get("recall_result")
        if not result_tuple:
            return
        results, err, last_q = result_tuple
        if err:
            st.error(f"Recall failed: {err}")
            return
        if not results:
            st.info(f"No matches for '{last_q}'.")
            return
        st.caption(f"Top {len(results)} for **'{last_q}'**")
        for r in results:
            sim = r.get("similarity") or r.get("score") or 0.0
            writer = r.get("__written_by") or r.get("agent_id") or ""
            ident = _ident(writer)
            color = ident["color"] if ident else "#888"
            display_writer = (ident["display"] if ident else writer) or "unknown"
            when = format_relative(r.get("created_at", ""))
            title = r.get("title") or (r.get("content") or "")[:80]
            sim_pct = f"{sim*100:.0f}%" if sim else "—"
            st.markdown(
                f'<div class="mem-card" style="border-left-color:{color}">'
                f'<div class="mem-writer" style="color:{color}">{display_writer} '
                f'<span style="opacity:0.6;font-weight:400">· {when}</span> '
                f'<span class="mem-recall">match {sim_pct}</span></div>'
                f'<div class="mem-title">{title}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_insights_section() -> None:
    with st.expander("🧠 Insights  ·  `memclaw_insights`", expanded=False):
        st.caption(
            "Run reflective analyses across the tenant. Findings are also "
            "persisted as `insight`-type memories (Karpathy Loop)."
        )
        focus = st.selectbox(
            "Focus",
            ["contradictions", "patterns", "stale", "divergence", "failures", "discover"],
            key="insights_focus",
        )
        if st.button("Analyze", type="primary", use_container_width=True, key="insights_btn"):
            result, err = fetch_insights_sync(cfg, focus)
            st.session_state["insights_result"] = (result, err, focus)

        result_tuple = st.session_state.get("insights_result")
        if not result_tuple:
            return
        result, err, last_focus = result_tuple
        if err:
            st.error(f"Insights failed: {err}")
            return
        st.caption(f"Focus: **{last_focus}**")
        findings = (
            result.get("findings")
            or result.get("insights")
            or result.get("results")
            or []
        )
        if findings and isinstance(findings, list):
            for f in findings:
                if not isinstance(f, dict):
                    st.markdown(f"- {f}")
                    continue
                with st.container(border=True):
                    t = f.get("title") or f.get("summary") or "(insight)"
                    d = f.get("detail") or f.get("description") or f.get("content") or ""
                    st.markdown(f"**{t}**")
                    if d:
                        st.markdown(d)
                    keys = {"title", "summary", "detail", "description", "content"}
                    rest = {k: v for k, v in f.items() if k not in keys}
                    if rest:
                        with st.expander("evidence", expanded=False):
                            st.json(rest)
        else:
            st.json(result)


def render_memory_card(m: dict, pulsed_ids: set) -> None:
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
    visibility = m.get("visibility") or "scope_team"
    recall_count = m.get("recall_count") or 0
    memory_id = m.get("id", "")

    viz_label = {
        "scope_agent": "🔒 private",
        "scope_team": "",
        "scope_org": "🌐 org",
    }.get(visibility, "")
    viz_html = (
        f'<span class="mem-badge" title="visibility: {visibility}">{viz_label}</span>'
        if viz_label
        else ""
    )

    pii = bool(
        meta.get("pii_detected")
        or meta.get("pii_flagged")
        or any("pii" in str(k).lower() for k in meta.keys())
    )
    pii_html = (
        '<span class="mem-badge" style="color:#c33" title="PII detected">⚠ PII</span>'
        if pii
        else ""
    )

    recall_html = (
        f'<span class="mem-recall" title="recalled {recall_count} time(s)">↻ {recall_count}</span>'
        if recall_count > 0
        else ""
    )

    pulse_class = " pulse" if memory_id in pulsed_ids else ""

    inner: list[str] = []
    if ident:
        inner.append(
            f'<div class="mem-writer" style="color:{color}">'
            f'{ident["emoji"]} {ident["display"]}{viz_html}{pii_html}{recall_html} '
            f'<span style="opacity:0.5;font-weight:400">· {when}</span></div>'
        )
    else:
        writer_label = writer or "—"
        inner.append(
            f'<div class="mem-writer" style="color:#888">'
            f'unknown ({writer_label}){viz_html}{pii_html}{recall_html} '
            f'<span style="opacity:0.5;font-weight:400">· {when}</span></div>'
        )
    inner.append(f'<div class="mem-title">{title}</div>')
    if mtype:
        inner.append(f'<div style="font-size:0.7rem;opacity:0.6">{mtype}</div>')
    if summary:
        inner.append(f'<div style="opacity:0.85;margin-top:1px">{summary}</div>')
    if tags:
        inner.append("".join(f'<span class="mem-tag">#{t}</span>' for t in tags))

    st.markdown(
        f'<div class="mem-card{pulse_class}" style="border-left-color:{color};'
        f'background:{bg}">{"".join(inner)}</div>',
        unsafe_allow_html=True,
    )
    with st.expander("details", expanded=False):
        st.markdown(f"**Content**\n\n{m.get('content') or '(no content)'}")
        if summary:
            st.markdown(f"**Summary**\n\n{summary}")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Type", mtype or "—")
        weight = m.get("weight")
        d2.metric("Weight", f"{weight:.2f}" if isinstance(weight, (int, float)) else "—")
        d3.metric("Status", m.get("status") or "—")
        d4.metric("Recalls", recall_count)
        st.caption(
            f"`{memory_id}` · visibility=`{visibility}` · created {when}"
            + (
                f" · last recalled {format_relative(m.get('last_recalled_at', ''))}"
                if m.get("last_recalled_at")
                else ""
            )
        )
        if tags:
            st.markdown("**Tags:** " + " ".join(f"`#{t}`" for t in tags))
        if meta:
            st.markdown("**Raw metadata**")
            st.json(meta)


def render_memory_feed() -> None:
    """Just the feed body — caption + cards. The section header and
    refresh button live in main_panel so the layout owns its structure."""
    mems_raw = st.session_state.get("memories", [])
    mems_local = mems_raw if isinstance(mems_raw, list) else []
    fetch_error = mems_raw.get("error") if isinstance(mems_raw, dict) else None
    pulsed_ids = st.session_state.get("pulsed_ids") or set()

    if fetch_error:
        st.error(f"Could not fetch memories: {fetch_error}")
        return
    if not mems_local:
        st.info(
            "No memories yet. Configure a native surface (see sidebar) and "
            "write one — it'll appear here on next refresh."
        )
        return

    for m in mems_local:
        render_memory_card(m, pulsed_ids)


# ── Layout ──────────────────────────────────────────────────────────
@st.fragment(run_every=30 if st.session_state.get("auto_refresh") else None)
def main_panel() -> None:
    # Manual refresh triggered by the inline link in the Memories header.
    # The link's href carries a fresh ms-timestamp nonce on every render,
    # so a click yields a URL Streamlit will treat as new; we dedup on
    # the token so a stale URL replay doesn't re-fire the fetch.
    token = st.query_params.get("refresh")
    if token and token != st.session_state.get("last_refresh_token"):
        st.session_state["last_refresh_token"] = token
        do_full_refresh()

    if st.session_state.get("auto_refresh"):
        do_full_refresh()

    surfaces_col, memories_col, exploration_col = st.columns([1, 2, 1.5])

    # ── Surfaces (left) ──
    with surfaces_col:
        st.markdown('<div class="section-h">Surfaces</div>', unsafe_allow_html=True)
        st.caption("Native LLM clients wired to this tenant.")
        for ident in AGENT_IDENTITIES:
            render_agent_card(ident)

    # ── Memories (center) ──
    with memories_col:
        nonce = int(time.time() * 1000)
        st.markdown(
            f'<div class="section-h">Memories'
            f'<a class="inline-refresh" href="?refresh={nonce}" '
            f'title="Refresh feed + stats">🔄</a></div>',
            unsafe_allow_html=True,
        )
        render_stats_strip()
        st.write("")
        render_memory_feed()

    # ── Exploration (right) ──
    with exploration_col:
        st.markdown('<div class="section-h">Exploration</div>', unsafe_allow_html=True)
        st.caption("Query and analyze the memory store.")
        render_recall_section()
        render_insights_section()


main_panel()
