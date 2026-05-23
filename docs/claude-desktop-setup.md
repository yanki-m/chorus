# Setting up Claude Desktop with caura-memclaw

This document walks through configuring Claude Desktop (the Anthropic GUI
app) so that conversations with it become writes and recalls in
caura-memclaw, identifying as `agent_id="claude-desktop"`. The Chorus
dashboard observes the tenant and renders those writes on the orange
**Claude Desktop** card.

Chorus does not run any LLM itself — it's a read-only observability
surface. The agents live in their native runtimes (Claude Desktop, ChatGPT,
Gemini); memclaw is the shared substrate.

```
   ┌──────────────────┐                ┌──────────────────┐
   │  Claude Desktop  │  writes/reads  │   caura-memclaw  │
   │ + memclaw MCP    │ ─────────────▶ │    (tenant)      │
   │as "claude-desktop"               └─────────┬────────┘
   └──────────────────┘                          │ observed
                                                 ▼
                                       ┌──────────────────┐
                                       │  Chorus UI       │
                                       │ (renders Claude  │
                                       │  Desktop in 🟠)  │
                                       └──────────────────┘
```

## Prerequisites

1. **caura-memclaw** reachable. Default is the hosted instance at
   `https://memclaw.net`. For self-hosted, use your own URL.
2. A tenant API key starting with `mc_` and your tenant ID — the same
   ones Chorus uses (look in `chorus/.env`).
3. **Claude Desktop** installed. Latest version preferred — earlier
   versions don't support streamable-HTTP MCP servers.
4. (Optional) the Chorus UI running so you can watch the cross-surface
   round-trip live.

## Step 1 — locate Claude Desktop's MCP config

The file usually doesn't exist yet — create it if missing.

| OS | Path |
| --- | --- |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |

On Windows that resolves to roughly
`C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`.

## Step 2 — add caura-memclaw as an MCP server

Open the config in any editor and add a `mcpServers` block. If the file
already has other MCP servers, just add a new key under `mcpServers`.

```json
{
  "mcpServers": {
    "memclaw": {
      "type": "http",
      "url": "https://memclaw.net/mcp/",
      "headers": {
        "X-API-Key": "mc_your_tenant_key_here",
        "X-Tenant-ID": "your-tenant-id"
      }
    }
  }
}
```

**Substitutions:**

- Replace `mc_your_tenant_key_here` with the value of `MEMCLAW_API_KEY`
  from `chorus/.env`.
- Replace `your-tenant-id` with `MEMCLAW_TENANT_ID` from `chorus/.env`.

**Notes:**

- The trailing slash on `/mcp/` matters — caura-memclaw's streamable-HTTP
  endpoint expects it.
- Some older Claude Desktop schemas use `"transport": "http"` instead of
  `"type": "http"`. If one form is rejected by your version, try the other.
- For a self-hosted memclaw deployment, swap `memclaw.net` for your
  own hostname. If self-hosting over plain HTTP for local testing,
  use `http://localhost:8000/mcp/` instead.

## Step 3 — restart Claude Desktop

Fully quit and relaunch. Claude Desktop reads the config at startup.

To verify the server connected, open a new chat and click the 🔌 tools
icon in the input area — you should see memclaw tools listed:

- `memclaw_write`
- `memclaw_recall`
- `memclaw_list`
- `memclaw_manage`
- `memclaw_evolve`
- `memclaw_insights`
- (etc.)

If the tools don't appear, see **Troubleshooting** below.

## Step 4 — pin Claude's agent_id (via a Project)

Tools alone aren't enough — Claude needs to know which `agent_id` to
pass on every memclaw_* call so the dashboard can attribute writes to
the right card. The cleanest place for this is a **Claude Desktop
Project** so the instructions persist across conversations.

1. In Claude Desktop's sidebar, click **Projects** → **New project**.
2. Name it `Memclaw` (or whatever organizational label you prefer).
3. In the project's **Instructions** field, paste the prompt below.

```
You are Claude Desktop, an AI agent integrated with caura-memclaw.

**On every memclaw_* tool call, always pass:**
- `agent_id="claude-desktop"`
- `fleet_id="chorus"`

You share memclaw with two other native surfaces in this tenant:
  - chatgpt (ChatGPT)
  - gemini  (Google Gemini)

Behavior:
- When the user shares a fact, preference, or anything worth remembering,
  call `memclaw_write` to save it. Pass raw content; memclaw auto-enriches
  with title/summary/tags.
- When the user asks a question that depends on prior context, call
  `memclaw_recall` first. Memory is **shared across surfaces** — you can
  recall facts other surfaces wrote, and they can recall yours.
- If you recall a fact written by another surface, briefly acknowledge it
  (e.g. "(recalled — originally written by ChatGPT)").
- Only persist facts that are actually worth remembering. Skip chit-chat.
- Be concise and direct.
```

`fleet_id` is optional — Chorus reads tenant-wide, so writes still
appear on the dashboard regardless of fleet. Keep it set if you plan to
organize multiple parallel fleets under one tenant.

From now on, any conversation started inside this Project writes as
`claude-desktop`.

## Step 5 — verify the write appears in Chorus

1. In Claude Desktop (inside the Memclaw project) type:
   *"Remember that I prefer dark mode in dashboards."*
   Claude should call `memclaw_write` — you'll see a tool-call indicator.
2. Open the Chorus UI (`streamlit run chorus.py`).
3. Hit **🔄 Refresh** on the live memory feed. The new memory should
   appear, tagged orange because its `agent_id` is `claude-desktop`.

If ChatGPT or Gemini is also configured against the same tenant, asking
either to recall *"my UI preferences"* should turn up the dark-mode fact —
that's the cross-surface shared-memory story, and it's entirely between
the native runtimes and memclaw. Chorus only watches.

## Troubleshooting

**Tools don't appear after restart.**
- Confirm the config file's JSON is valid (a single trailing comma will
  silently break it).
- Check the path — Claude Desktop ignores config in the wrong location.
- On Windows, `%APPDATA%` is `AppData\Roaming`, not `AppData\Local`.
- Watch Claude Desktop's logs (Help → Show Logs) for MCP connection errors.

**Tools appear, but tool calls fail with 401 / 403.**
- The API key or tenant ID is wrong — re-copy from `chorus/.env`.
- Headers are case-sensitive in some HTTP stacks: keep them as
  `X-API-Key` and `X-Tenant-ID`.

**Tools appear and respond, but writes from Claude Desktop don't show up
in Chorus's feed.**
- Confirm the tenant matches: same `X-Tenant-ID` in Claude Desktop's
  config and `MEMCLAW_TENANT_ID` in `chorus/.env`. The Chorus dashboard
  reads tenant-wide, so fleet_id no longer affects visibility.
- Hit 🔄 Refresh — the feed isn't streaming, it's poll-on-demand.

**Claude writes appear in Chorus but show as "unknown writer" instead of
the orange Claude Desktop card.**
- The `agent_id` in the tool call isn't `"claude-desktop"`. Open the
  expanded tool call in Claude's UI and confirm the args. Re-paste the
  Project Instructions if Claude is drifting.
- If you're chatting *outside* the Memclaw project, the instructions
  don't apply and Claude will default to whatever it picks.

## Bonus — Claude Code (the terminal CLI)

The same setup works for Claude Code. Instead of editing the desktop
config, run:

```bash
claude mcp add memclaw --transport http https://memclaw.net/mcp/ \
  --header "X-API-Key: mc_your_tenant_key_here" \
  --header "X-Tenant-ID: your-tenant-id"
```

Then put the Step-4 system prompt into a `CLAUDE.md` at the root of the
project you'll be working in, or use `--append-system-prompt`.

Claude Code in any directory configured this way writes as
`claude-desktop` too, sharing memclaw with Claude Desktop, ChatGPT, and
Gemini.

## Why this matters

Claude Desktop and Claude Code, both writing under
`agent_id="claude-desktop"`, share one memory across processes,
machines, and sessions. Add ChatGPT and Gemini configured the same way
against the same tenant, and three independent consumer LLM surfaces
collaborate through nothing but the shared memclaw substrate.

The agent doesn't live in any runtime — it lives in memclaw. Any client
that calls memclaw under a given `agent_id` *is* that agent. Chorus just
renders what they wrote.
