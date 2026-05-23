# Chorus

> Many surfaces. One memory.

A **memclaw observability dashboard** for a multi-surface AI agent fleet.
Native LLM clients (Claude Desktop, ChatGPT) write into a shared
caura-memclaw tenant; Chorus polls the tenant and renders each writer's
activity on a colored card alongside a live feed of every memory.

Chorus does not run any LLM itself. It's read-only — the agents live in
their native runtimes; memclaw is the shared substrate.

```
   ┌────────────────────────┐
   │     Claude Desktop     │ ──┐
   │ agent_id="claude-desktop" │
   └────────────────────────┘   │
                                ▼
                        ┌──────────────────┐         ┌─────────────────┐
                        │  caura-memclaw   │  poll   │  Chorus (this   │
                        │  (shared tenant) │ ◀────── │  Streamlit UI)  │
                        └──────────────────┘         └─────────────────┘
                                ▲
   ┌────────────────────────┐   │
   │        ChatGPT         │ ──┘
   │   agent_id="chatgpt"   │
   │     (Custom GPT)       │
   └────────────────────────┘
```

## Layout

| File | What it is |
| --- | --- |
| `chorus.py` | The Streamlit dashboard — fleet cards + live memory feed + erase-all |
| `memclaw_mcp.py` | MCP session + helpers for `memclaw_list` / `memclaw_write` against the shared tenant |
| `config.py` | `MemclawConfig` dataclass with `from_env()` loader |
| `smoke_test.py` | Pure MCP round-trip — verifies wiring without spending any LLM tokens |
| `requirements.txt` | Three deps: `mcp`, `python-dotenv`, `streamlit` |
| `.env.example` | The four `MEMCLAW_*` vars the dashboard reads |
| `LICENSE` | Apache 2.0 |
| `docs/claude-desktop-setup.md` | Wire Claude Desktop to write as `agent_id="claude-desktop"` |
| `docs/openai-setup.md` | Wire a ChatGPT Custom GPT to write as `agent_id="chatgpt"` |
| `docs/gemini-setup.md` | Dormant — kept for when Gemini comes back into the lineup |
| `docs/INFOGRAPHIC.md` | Design brief for the blackboard / dashboard infographic |
| `docs/blackboard.svg` | Rendered infographic — matches `INFOGRAPHIC.md` |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in MEMCLAW_API_KEY (mc_...) and MEMCLAW_TENANT_ID
```

You only need:

1. **caura-memclaw** reachable at `MEMCLAW_API_URL` (default `https://memclaw.net`).
2. A tenant `mc_` API key and the tenant id it belongs to.

No Anthropic/OpenAI/Google keys — the dashboard doesn't call any LLM.

### Trust elevation (automatic)

Chorus reads the tenant with `scope="all"`, which requires
`trust_level ≥ 2` on the `chorus-dashboard` agent. The dashboard
handles both setup steps itself on first run:

1. **Bootstrap:** if the agent doesn't exist yet, writes one marker
   memory so caura-memclaw materialises the row (default trust = 1).
2. **Elevation:** if a feed fetch comes back FORBIDDEN at the trust
   gate, PATCHes the agent to trust = 2 and retries the fetch.

Both calls are idempotent. If auto-elevation fails (typically because
the tenant key isn't authorized for the configured tenant), the
dashboard surfaces the underlying error in the feed banner.

## Run the dashboard

```bash
streamlit run chorus.py
```

The sidebar has the config fields (pre-filled from `.env`), an
**Erase all memories** button (two-click confirm — wipes every memory
in the tenant via `DELETE /api/v1/memories`), and links to the setup
docs for each native surface.

## Verify the wiring

```bash
python smoke_test.py
```

Pure MCP round-trip — no LLM, no token spend. One canary write, one
recall under a different `agent_id` but the same `fleet_id`. Exits 0 on
success. Run this first whenever something looks broken.

## Wire a native surface

Each surface gets pinned to a stable `agent_id` so the dashboard can
color-code its writes:

- **Claude Desktop / Claude Code** → `agent_id="claude-desktop"` →
  see [`docs/claude-desktop-setup.md`](docs/claude-desktop-setup.md).
- **ChatGPT (Custom GPT)** → `agent_id="chatgpt"` →
  see [`docs/openai-setup.md`](docs/openai-setup.md).

Writes from any other `agent_id` still appear in the feed, just as
grey-bordered "unknown writer" cards instead of getting a colored fleet
card.

## Adding a new surface

Edit `AGENT_IDENTITIES` in `chorus.py` — one new dict with `agent_id`,
`display`, `subtitle`, `emoji`, `color`, `bg_tint`, `setup_doc`. The
fleet card and color attribution pick up automatically. Then write a
new `<surface>-setup.md` that tells users how to configure that surface
to pass `agent_id="<your-new-id>"` on every memclaw call.

## What memclaw is, briefly

`caura-memclaw` is a shared persistent memory service. Any LLM client
with the right MCP or REST credentials can write facts there under an
`agent_id`, and later recall them by semantic similarity — across
sessions, surfaces, and machines. The blackboard pattern, applied to
modern LLM agents: independent specialists post to and read from a
central board, coordinating through what's on the board rather than by
direct messaging.

The agent doesn't live in any runtime. It lives in memclaw. Chorus is
the window.
