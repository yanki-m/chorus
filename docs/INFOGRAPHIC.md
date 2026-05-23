# Blackboard infographic — design brief

A one-frame visual for explaining what **Chorus** (and, by extension,
caura-memclaw) does.

The current rendering lives at [`blackboard.svg`](blackboard.svg) and
follows this brief. If you edit one, update the other so they stay in
sync.

## Purpose

One image, no animation, that lets a viewer understand:

1. Multiple native LLM surfaces (Claude Desktop, ChatGPT, …) write into
   one shared caura-memclaw tenant.
2. They never talk to each other directly.
3. They coordinate exclusively by writing to and reading from that
   shared memory.
4. **Chorus** is a passive observer — a read-only dashboard that
   renders the memory stream with per-surface color attribution. It is
   not an agent; it is the window onto the substrate.

If a viewer takes one phrase away, it should be: **"Agents don't talk.
Memory remembers."**

## Layout

```
┌────────── native surfaces in a row ──────────┐
│  Claude Desktop          ChatGPT             │     (Gemini comes back later,
│  (agent_id="claude-desktop")  ("chatgpt")    │      pinned grey on the side)
└──────┬──┬───────────────────┬──┬─────────────┘
       │  │                   │  │
   write│  │recall         write│ │recall
       ▼  │                   ▼  │
┌──────────────── caura-memclaw tenant ──────────────────┐
│  ● memory · writer · time                              │
│  ● memory · writer · time                              │
│  ● memory · writer · time                              │
└─────────────────────────────┬──────────────────────────┘
                              │ scope='all' read
                              ▼
                  ┌──────────────────────┐
                  │   Chorus dashboard   │  (read-only window)
                  │  fleet cards + feed  │
                  └──────────────────────┘

            Agents don't talk. Memory remembers.
```

Vertical axis = "agent → substrate → observer". Top is native surfaces,
middle is the shared store, bottom is Chorus. Everything flows up and
down; nothing flows sideways.

## Required visual elements (non-negotiable)

These carry the architectural claim. If any are missing, the image
fails its job.

- **Separate surface cards across the top.** No connection between
  them. No shared frame. They are siblings, not a system. Today there
  are two (Claude Desktop, ChatGPT); the layout must remain
  add-friendly — a third (Gemini) and fourth (OpenClaw, etc.) should
  slot in without rearranging the rest.
- **Vertical-only arrows between surfaces and memclaw.** Each surface
  has two arrows: one for `write` (down, solid), one for `recall` (up,
  dashed). No horizontal arrow anywhere — that absence is the visual
  argument.
- **A single memclaw container with mixed memory cards.** The cards
  must be visibly attributed — the writer's identity is part of the
  card, not metadata hidden somewhere. Mixing cards from different
  writers inside one shared container is the whole point.
- **Color coding by writer.** Each surface uses its LLM/brand color
  (Claude Desktop orange / ChatGPT green / Gemini blue when present);
  the border accent / dot on each memory card matches its writer. A
  viewer should see at a glance "ChatGPT wrote that one, Claude
  Desktop wrote that other one, and they're side-by-side in the same
  store."
- **A distinct "Chorus" box below memclaw**, drawn smaller, in
  neutral/grey, with a *single* arrow up into memclaw labelled
  "scope='all' read." It must not look like a fourth surface — it has
  no write arrow because Chorus does not write user-visible memories.
- **The tagline.** "Agents don't talk. Memory remembers." Or a near
  variant. This is the takeaway phrase.

## Decorative elements (change freely)

- Specific memory contents in the cards — placeholders, swap with
  whatever resonates for the audience.
- Background — white in the current draft. Dark mode works too; just
  use white cards on a dark vault, not the reverse.
- Typography — current draft uses system sans-serif. Any clean,
  geometric sans works (Inter, IBM Plex Sans, etc.).
- Whether surfaces show an emoji or an SDK/brand logo. Logos look more
  polished but introduce licensing/trademark complexity.

## Palette

| Element | Hex | Notes |
| --- | --- | --- |
| Claude Desktop (Anthropic) | `#D97757` | terracotta / orange |
| ChatGPT (OpenAI) | `#10A37F` | OpenAI green |
| Gemini (Google) — when added | `#4285F4` | Google blue |
| caura-memclaw substrate | `#7850c8` | purple — matches the dashboard's feed header |
| caura-memclaw tint (fill) | `#F4F0FA` | very pale purple |
| Chorus dashboard box | `#888` border, white fill | neutral, deliberately understated |
| Text — body | `#222` | |
| Text — secondary | `#555` | arrow labels |
| Text — meta | `#888` | turn/attribution chips |

The vendor colors approximate brand colors. If publishing somewhere
brand-sensitive, double-check against each vendor's current brand
guidelines — they update occasionally.

## Typography

- Hero / surface names: 22pt, weight 700
- Section labels (e.g. "caura-memclaw — shared tenant"): 20pt, weight 700
- Chorus box label: 16pt, weight 600
- Body / memory text: 14pt
- Meta (turn, attribution): 11pt
- Tagline: 22pt italic

## Variants worth producing

- **Dark mode.** Same composition, but the substrate becomes dark
  purple on near-black background, cards become dark gray with
  brand-colored accents. Tagline stays prominent.
- **Animated (for video).** Memory cards fade in over time, each
  appearing inside the substrate as its surface "writes" it. A faint
  pulse on a card when a different surface recalls it. The Chorus box
  receives a thin "tick" pulse on each dashboard refresh. Keep the
  no-horizontal-arrow rule even during animation.
- **Wider (presentation aspect).** Pull surface cards further apart,
  widen the substrate. Same elements, 16:9 friendly.

## What NOT to do

- **Don't draw a hub-and-spoke with arrows between surfaces.** That's
  the wrong architecture — undoes the entire claim.
- **Don't put memclaw in the middle with surfaces around it as a circle.**
  Vertical hierarchy (surfaces above, substrate below, observer below
  that) reads more clearly as "everyone posts into one shared place"
  than a radial layout, which implies peer-to-peer routing.
- **Don't mix memory cards into per-surface buckets** ("Claude Desktop's
  memories", "ChatGPT's memories"). They share one store; siloing them
  visually breaks the point.
- **Don't add a "controller" or "orchestrator" box.** There isn't one.
- **Don't draw Chorus with write arrows into memclaw.** It only
  bootstraps a single marker memory under `agent_id="chorus-dashboard"`
  on first run, and that's a configuration detail, not part of the
  story.

## Use cases

- README hero image.
- Slide 1 of any pitch deck explaining caura-memclaw + Chorus.
- Twitter/LinkedIn post asset.
