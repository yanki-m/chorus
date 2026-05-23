# Setting up Gemini with caura-memclaw

This document walks through configuring a **Gemini surface** (Gem, AI
Studio, or Vertex) so that conversations with it become writes and
recalls in caura-memclaw, identifying as `agent_id="gemini"`. The Chorus
dashboard observes the tenant and renders those writes on the blue
**Gemini** card.

Chorus does not run any LLM itself — it's a read-only observability
surface. The agents live in their native runtimes; memclaw is the shared
substrate.

```
   ┌──────────────────┐                ┌──────────────────┐
   │  Gemini surface  │  writes/reads  │   caura-memclaw  │
   │  (Gem / AI Studio│ ─────────────▶ │    (tenant)      │
   │   / Vertex)      │                └─────────┬────────┘
   │   as "gemini"    │                          │ observed
   └──────────────────┘                          ▼
                                       ┌──────────────────┐
                                       │  Chorus UI       │
                                       │ (renders Gemini  │
                                       │  in 🔷)          │
                                       └──────────────────┘
```

## Honest framing

Of the three runtimes (Claude / GPT / Gemini), **Gemini has the weakest
consumer-UI story for connecting third-party tools.** Claude Desktop has
native MCP. ChatGPT has mature Custom GPT Actions. Gemini's consumer
"Gems" only recently started supporting custom tool integrations and
the experience varies by region and rollout phase.

So this doc gives you three paths, in order of effort vs. polish:

1. **Gemini Gem with API actions** — closest analog to a Custom GPT.
   Consumer Gemini app surface. Setup parity with the OpenAI doc.
2. **Google AI Studio with function calling** — developer surface, but
   the most reliable path *today*. Build a thin Streamlit/Python frontend
   in 30 minutes and call it done.
3. **Vertex AI Agent Engine** — deploy your existing `GoogleADKAgent`
   from Chorus as a real Vertex service. Heaviest setup, most native to
   Google's enterprise stack, talk to the Gemini surface through Vertex's chat UI.

Pick by audience: demo to consumers → Gem; demo to developers → AI
Studio; demo to enterprise buyers → Vertex.

## Prerequisites (shared by all paths)

1. **caura-memclaw** running. For Gem and Vertex paths it must be
   publicly reachable over HTTPS — tunnel via [ngrok](https://ngrok.com/)
   or a real deployment. AI Studio can talk to `localhost` from a script
   running on the same machine.
2. A tenant API key (`mc_…`) and tenant ID from `chorus/.env`.
3. A **Google account** with Gemini access (and, for Vertex, a GCP project
   with billing enabled).
4. (Optional) the Chorus UI running so you can watch the cross-surface
   round-trip live.

---

## Path 1 — Gemini Gem with API actions (consumer UI)

The closest Gemini analog to a ChatGPT Custom GPT.

### Step 1 — confirm Gems support custom tools in your region

Open the Gemini app → **Gems** → **New Gem**. If you see an option to
add "tools" / "actions" / "API connections" with an OpenAPI spec, you're
good. If not, Gems in your tenant/region are still instructions-only —
skip to Path 2 instead.

### Step 2 — create the Memclaw Gem

1. **Name:** `Memclaw` (or any organizational label you prefer)
2. **Description:** *Writes/recalls into the shared caura-memclaw tenant as agent_id="gemini".*
3. **Instructions:** paste the system prompt from Step 4 below.

### Step 3 — add caura-memclaw as a tool

Add a tool / action with the same OpenAPI snippet from
[`openai-setup.md` step 3](openai-setup.md#step-3--add-caura-memclaw-as-an-action).
Substitute your public memclaw URL into `servers.url`.

Auth: header-based API key (`X-API-Key: mc_…`). If the Gem UI in your
build only supports a Bearer token, you'll need a small proxy that
translates `Authorization: Bearer <key>` → `X-API-Key: <key>` and adds
`X-Tenant-ID` for caura-memclaw.

### Step 4 — Gem instructions

```
You are Gemini, an AI agent integrated with caura-memclaw.

**On every action call, always pass:**
- `agent_id="gemini"`
- `fleet_id="chorus"`

You share memclaw with two other native surfaces in this tenant:
  - claude-desktop (Claude)
  - chatgpt        (OpenAI ChatGPT)

Behavior:
- When the user shares a fact, preference, or anything worth remembering,
  call `memclawWrite` to save it. Pass raw content; memclaw auto-enriches
  with title/summary/tags.
- When the user asks a question that depends on prior context, call
  `memclawRecall` first. Memory is **shared across surfaces** — you can
  recall facts other surfaces wrote, and they can recall yours.
- If you recall a fact written by another surface, briefly acknowledge it
  (e.g. "(recalled — originally written by Claude Desktop)").
- Only persist facts that are actually worth remembering. Skip chit-chat.
- Be concise and direct.
```

`fleet_id` is optional — Chorus reads tenant-wide, so writes still
appear on the dashboard regardless of fleet. Keep it set if you plan to
organize multiple parallel fleets under one tenant.

### Step 5 — verify the write appears in Chorus

Write a fact in the Gem, hit 🔄 Refresh on Chorus's live memory feed,
and a new card tagged blue (because `agent_id="gemini"`) should appear.
If Claude Desktop or ChatGPT is configured against the same tenant,
asking either to recall the fact closes the cross-surface loop —
entirely between the native runtimes and memclaw. Chorus only watches.

---

## Path 2 — Google AI Studio (developer surface)

The most reliable path *today*. Talks directly to the Gemini API with
function calling. Reuses the `GoogleADKAgent` from Chorus minus the ADK
layer, or just calls the Gemini SDK plus memclaw's REST API.

### Minimal version (Python, ~40 lines)

The Chorus repo ships a Gemini adapter at `adapters/google_adk_agent.py`
that you can reuse to build a standalone CLI. It writes to memclaw under
whatever `agent_id` you give it.

```python
# gemini_cli.py
import asyncio
from dotenv import load_dotenv

load_dotenv()

from adapters import GoogleADKAgent
from prompts import build_system_prompt
from config import MemclawConfig

cfg = MemclawConfig.from_env()
gemini = GoogleADKAgent(
    agent_id="gemini",
    display="Gemini",
    system_prompt=build_system_prompt(
        display="Gemini",
        agent_id="gemini",
        fleet_id=cfg.fleet_id,
        peers=[("claude-desktop", "Claude Desktop"), ("chatgpt", "ChatGPT")],
    ),
    memclaw=cfg,
)

async def main():
    history = []
    while True:
        msg = input("You> ").strip()
        if not msg:
            break
        async for ev in gemini.run_turn(user_message=msg, history=history):
            if ev["type"] == "assistant_text":
                print(f"Gemini> {ev['text']}")
            elif ev["type"] == "done":
                history = ev["history"]

asyncio.run(main())
```

Run it: `python gemini_cli.py`. Same tenant, same memory as the Chorus
dashboard — just a developer surface instead of the consumer Gem UI.

### Polished version

Wrap that in a Streamlit page or a minimal web frontend. Or skip ADK
entirely and call Gemini's `google.genai` SDK with `tools=[…]` pointing
at memclaw REST endpoints — the [Gemini docs on function calling](https://ai.google.dev/gemini-api/docs/function-calling)
have the boilerplate.

This path is "developer surface", not "consumer surface" — but it's
honest about what's actually available today.

---

## Path 3 — Vertex AI Agent Engine (enterprise surface)

If the audience is "enterprise buyer who lives in GCP", deploy a
`GoogleADKAgent` as a Vertex AI Agent Engine service. Users talk to it
through Vertex's chat UI — fully native to Google's stack.

Outline (not a full guide — Vertex docs evolve):

1. Containerize a `GoogleADKAgent` configured with `agent_id="gemini"`,
   wrapped behind a thin HTTP server.
2. Deploy to Cloud Run or Vertex AI Agent Engine.
3. Configure Vertex's chat UI to use that endpoint as the agent backend.
4. The memclaw connection inside the agent works the same way as in the
   CLI above — `agent_id="gemini"`, `fleet_id="chorus"`.

This path takes ~1-2 hours plus GCP setup. Worth it if you're already
in Vertex; overkill otherwise.

Reference: [Vertex AI Agent Engine docs](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview).

---

## Troubleshooting

**Gem doesn't see my action / tool.**
- Custom tools in Gems are still rolling out by region and account
  tier. Confirm with the Gemini docs for your account.
- Fall back to Path 2 (AI Studio) — it always works.

**Gemini calls the tool but with the wrong `agent_id`.**
- The Instructions field is the only thing forcing `gemini`. Keep it
  short and explicit; remove anything that contradicts it.

**My self-hosted memclaw URL doesn't work from a Gem.**
- Same as ChatGPT: consumer Gems can only call public HTTPS. Use ngrok
  or a real deployment.

**Writes from Gemini don't appear in Chorus's vault.**
- `fleet_id` mismatch. The Gem must pass `fleet_id="chorus"` exactly.

## Why this matters

Claude Desktop, ChatGPT, and a Gemini surface all writing to the same
caura-memclaw tenant — three independent consumer LLMs collaborating via
the blackboard pattern, with Chorus as the read-only window onto the
shared memory pool.

The agent doesn't live in any runtime. It lives in memclaw — and so does
the value prop.
