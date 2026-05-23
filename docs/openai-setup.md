# Setting up ChatGPT with caura-memclaw

This document walks through configuring **ChatGPT** (the OpenAI consumer
GUI) so that conversations with it become writes and recalls in
caura-memclaw, identifying as `agent_id="chatgpt"`. The Chorus dashboard
observes the tenant and renders those writes on the green **ChatGPT**
card.

Chorus does not run any LLM itself — it's a read-only observability
surface. The agents live in their native runtimes; memclaw is the shared
substrate.

```
   ┌──────────────────┐                ┌──────────────────┐
   │     ChatGPT      │  writes/reads  │   caura-memclaw  │
   │  Custom GPT with │ ─────────────▶ │    (tenant)      │
   │ memclaw actions  │                └─────────┬────────┘
   │   as "chatgpt"   │                          │ observed
   └──────────────────┘                          ▼
                                       ┌──────────────────┐
                                       │  Chorus UI       │
                                       │ (renders ChatGPT │
                                       │  in 🟢)          │
                                       └──────────────────┘
```

ChatGPT's consumer UI doesn't speak MCP natively (as of mid-2026), so
the path is **Custom GPT Actions** calling caura-memclaw's REST API.

## Prerequisites

1. **caura-memclaw** reachable from the public internet —
   ChatGPT Actions only call public HTTPS URLs.
   - The hosted instance at `https://memclaw.net` works out of the box.
   - For a self-hosted memclaw on localhost, tunnel it first via
     [ngrok](https://ngrok.com/), Cloudflare Tunnel, etc.
     (`ngrok http 8000`).
2. A tenant API key starting with `mc_` and your tenant ID — the same
   ones Chorus uses (look in `chorus/.env`).
3. A **ChatGPT Plus / Pro / Team / Enterprise** subscription (free
   ChatGPT can't create Custom GPTs).
4. (Optional) the Chorus UI running so you can watch the cross-surface
   round-trip live.

## Step 1 — confirm your memclaw REST endpoints

Custom GPT Actions speak OpenAPI 3, so we need REST endpoints (not MCP).
caura-memclaw exposes its OpenAPI spec at:

```
GET  http://<your-memclaw-host>/openapi.json
GET  http://<your-memclaw-host>/docs           ← interactive Swagger UI
```

Open `/docs` in a browser and confirm at least these endpoints exist:

| Purpose | Likely path |
| --- | --- |
| Write a memory | `POST /api/v1/memories` |
| Recall (semantic search) | `POST /api/v1/search` |
| List memories | `GET /api/v1/memories` |

If your deployment's paths differ, adjust the OpenAPI snippet in Step 3.

## Step 2 — create the Memclaw Custom GPT

1. In ChatGPT, click your profile → **My GPTs** → **Create**.
2. In the **Configure** tab:
   - **Name:** `Memclaw` (or any organizational label you prefer)
   - **Description:** *Writes/recalls into the shared caura-memclaw tenant as agent_id="chatgpt".*
   - **Instructions:** paste the system prompt from Step 4 below.
3. Leave **Knowledge** empty (caura-memclaw is the knowledge).
4. Under **Capabilities**, turn off web browsing and image generation
   unless you specifically want them — they add noise.

## Step 3 — add caura-memclaw as an Action

In the GPT's **Configure** tab, scroll to **Actions** → **Create new
action**. Two things to configure: the OpenAPI schema and the auth.

### OpenAPI schema

Paste this (substitute your public memclaw URL into `servers.url`):

```yaml
openapi: 3.0.1
info:
  title: caura-memclaw
  version: 1.0.0
  description: Shared memory for the Chorus fleet
servers:
  - url: https://your-memclaw-host.example.com
paths:
  /api/v1/memories:
    post:
      operationId: memclawWrite
      summary: Persist a fact to the shared fleet
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [content, tenant_id, agent_id]
              properties:
                content:
                  type: string
                  description: Raw fact to remember. memclaw auto-enriches.
                tenant_id:
                  type: string
                  description: Always "<your-tenant-id>" for this GPT. Must match the key's tenant.
                agent_id:
                  type: string
                  description: Always "chatgpt" for this GPT.
                fleet_id:
                  type: string
                  description: Optional. Set to "chorus" if you want fleet grouping.
      responses:
        "201":
          description: Memory created
  /api/v1/search:
    post:
      operationId: memclawRecall
      summary: Semantically search the shared fleet
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [query, tenant_id, agent_id]
              properties:
                query:
                  type: string
                tenant_id:
                  type: string
                  description: Always "<your-tenant-id>" for this GPT.
                agent_id:
                  type: string
                  description: Always "chatgpt" for this GPT.
                fleet_id:
                  type: string
                  description: Optional. Set to "chorus" if you want fleet grouping.
                top_k:
                  type: integer
                  default: 10
                  maximum: 20
      responses:
        "200":
          description: Search results
```

> **Important:** if your memclaw deployment's actual schema (from
> `/openapi.json`) differs in field names or paths, copy the relevant
> parts from there instead. The snippet above is the canonical shape;
> your install may name things slightly differently.

### Authentication

In the Action's **Authentication** dialog:

- **Auth Type:** API Key
- **API Key:** your `mc_…` tenant key
- **Auth Type → Custom:** set the header name to `X-API-Key`

`tenant_id` is not a header — it's a required field in the JSON body of
every memclaw REST call. The OpenAPI schema above declares it, and the
Step 4 instructions tell ChatGPT to always pass your tenant. The route
verifies the body's `tenant_id` matches the key's tenant
(`caura-memclaw/.../routes/memories.py` enforce_tenant) — so swap in
your real tenant id in the Step 4 instructions block below.

## Step 4 — pin ChatGPT's agent_id via Instructions

Paste this into the GPT's **Instructions** field:

```
You are ChatGPT, integrated with caura-memclaw — a shared persistent
memory service that you MUST use to save and recall facts about the
user. Memory is shared across surfaces (Claude Desktop, Gemini, ChatGPT)
under one tenant.

# MANDATORY TOOL USE — NO EXCEPTIONS

You MUST call `memclawWrite` whenever the user shares ANY of:
- Preferences: "I love X", "I prefer Y", "I hate Z", "my favorite is …"
- Personal facts: "I live in X", "I work at Y", "I am …", "my … is …"
- Explicit asks: "remember that …", "note …", "don't forget …"
- Decisions, goals, plans, commitments, deadlines
- Anything stated about themselves, their team, project, or context

You MUST call `memclawRecall` BEFORE answering when the user:
- Asks about themselves, their preferences, history, or context
- Says "what we talked about", "what I told you", "what do you know
  about me", "my …"
- Asks anything where prior context could change the answer

# REQUIRED FIELDS ON EVERY CALL — NEVER OMIT

- `tenant_id`: `<your-tenant-id>`   ← replace with the value from chorus/.env MEMCLAW_TENANT_ID
- `agent_id`:  `chatgpt`
- `fleet_id`:  `chorus`

# FORBIDDEN BEHAVIORS

- DO NOT say "I'll remember that" / "I'll keep it in mind" /
  "I'll note that down" UNLESS you have already called `memclawWrite`
  and it succeeded. Those phrases without a tool call are LIES.
- DO NOT decide a fact is "too small" or "not worth saving" — save it.
  Relevance filtering happens server-side, not in your head.
- DO NOT skip `memclawRecall` when the user asks about prior context.
- DO NOT continue silently if a tool call errors — tell the user it
  failed, exactly which tool, and ask them to check Chorus / memclaw
  setup. Do not pretend you saved or recalled.

# OTHER SURFACES YOU SHARE MEMORY WITH

- `claude-desktop` — Claude (Desktop / Code)
- `gemini`         — Google Gemini

If `memclawRecall` returns a fact written by another surface, briefly
acknowledge the source: "(recalled from Claude Desktop)" etc.

# STYLE

Tool first, prose second. Be concise. Don't editorialize about your
memory use — just use it.
```

`fleet_id` is optional — Chorus reads tenant-wide, so writes still
appear on the dashboard regardless of fleet. Keep it set if you plan to
organize multiple parallel fleets under one tenant.

## Step 5 — verify the write appears in Chorus

1. In your new Custom GPT, type:
   *"Remember that I prefer dark mode in dashboards."*
   ChatGPT will show an "Allow once / Always allow" prompt the first
   time the action runs. Allow it.
2. Open the Chorus UI (`streamlit run chorus.py`).
3. Hit **🔄 Refresh** on the live memory feed. The new memory should
   appear, tagged green because its `agent_id` is `chatgpt`.

If Claude Desktop or Gemini is also configured against the same tenant,
asking either to recall the user's UI preferences should turn up the
dark-mode fact — the cross-surface shared-memory story runs entirely
between the native runtimes and memclaw. Chorus only watches.

## Bonus — programmatic path via the Responses API

If you don't want a Custom GPT and prefer a programmatic surface, the
**OpenAI Responses API** (gpt-4.1+) supports MCP directly:

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-4.1",
    instructions="You are ChatGPT, integrated with caura-memclaw. Pass agent_id='chatgpt', fleet_id='chorus' on every memclaw_* call.",
    input="Remember that I prefer dark mode in dashboards.",
    tools=[{
        "type": "mcp",
        "server_label": "memclaw",
        "server_url": "https://your-memclaw-host/mcp/",
        "headers": {
            "X-API-Key": "mc_...",
            "X-Tenant-ID": "your-tenant-id",
        },
    }],
)
```

Same fleet, same memory, no Custom GPT UI in between.

## Troubleshooting

**Action calls fail with 401 / 403.**
- API key is wrong, or `X-API-Key` was misspelled in the auth dialog.
- The key is `mca_…` (agent-scoped) instead of `mc_…` (tenant-scoped).
  Custom GPTs need a `mc_…` key.

**Action calls fail with "missing tenant" or similar 400.**
- Your memclaw deployment requires `X-Tenant-ID` and the `mc_…` key
  isn't enough alone. Stand up the small proxy from Step 3.

**Writes from ChatGPT don't appear in Chorus's feed.**
- Confirm the tenant matches: same tenant key in the Custom GPT Action
  auth and `MEMCLAW_TENANT_ID` in `chorus/.env`. The Chorus dashboard
  reads tenant-wide, so fleet_id no longer affects visibility.
- Hit 🔄 Refresh — the feed isn't streaming, it's poll-on-demand.

**ChatGPT writes appear in Chorus but show as "unknown writer" instead
of the green ChatGPT card.**
- The `agent_id` in the action call isn't `"chatgpt"`. Open the
  expanded action call in ChatGPT and confirm.
- The Instructions are the only thing forcing `chatgpt`. Re-paste them.
- Custom GPT Instructions are short-context; if you have lots of
  conflicting text, trim it to the prompt above.

**ChatGPT can't reach my memclaw at all.**
- Custom GPT Actions only call public HTTPS URLs. `http://localhost`
  won't work. Use the hosted `https://memclaw.net`, your own deployment,
  or `ngrok http 8000` for self-hosted testing.

## Why this matters

ChatGPT and Claude Desktop, each writing under their own surface
`agent_id`, share one memory through nothing but the caura-memclaw
tenant. Add Gemini, and three independent consumer LLMs collaborate via
the blackboard pattern — no direct messaging between them, no router,
just a shared substrate.

The agent doesn't live in any runtime. It lives in memclaw. Chorus is
the window onto that substrate, not a participant in it.
