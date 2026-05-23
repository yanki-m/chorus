# Blackboard infographic — design brief

A one-frame visual for explaining what **Chorus** (and, by extension,
caura-memclaw) does.

A working draft lives at [`blackboard.svg`](blackboard.svg). This doc
is the spec — what it's trying to say, what *must* be in it, and
what is just decoration that can change.

## Purpose

One image, no animation, that lets a viewer understand:

1. Three independent agents (the muses Clio, Calliope, Urania — backed by
   Claude, GPT, Gemini respectively) are in the same fleet.
2. They never talk to each other directly.
3. They coordinate exclusively by writing to and reading from a shared
   memclaw vault.
4. Each memory in the vault is attributed to whichever muse wrote it.

If a viewer takes one phrase away, it should be: **"Agents don't talk.
Memory remembers."**

## Layout

```
┌────────────────── three muse cards in a row ────────────────────┐
│   Clio              Calliope         Urania                      │
│   (Claude)          (GPT)            (Gemini)                    │
└──────┬──┬──────────┬──┬─────────────┬──┬───────────────────────┘
       │  │          │  │             │  │
   write│  │recall write│ │recall write│ │recall
       ▼  │          ▼  │             ▼  │
┌──────────────── one memclaw vault ─────────────────────────────┐
│  ● memory · attribution · turn                                  │
│  ● memory · attribution · turn                                  │
│  ● memory · attribution · turn                                  │
└─────────────────────────────────────────────────────────────────┘
            Agents don't talk. Memory remembers.
```

Vertical axis = "agent → substrate". Top is agents, bottom is the
shared store. Everything flows up and down; nothing flows sideways.

## Required visual elements (non-negotiable)

These carry the architectural claim. If any are missing, the image
fails its job.

- **Three separate agent cards across the top.** No connection
  between them. No shared frame around them. They are siblings, not
  a system.
- **Vertical-only arrows.** Each agent has two arrows to the vault:
  one for `write` (down, solid), one for `recall` (up, dashed). No
  horizontal arrow anywhere in the image — that absence is the visual
  argument.
- **A single vault containing memory cards.** The cards must be
  visibly attributed — the writer's identity is part of the card,
  not metadata hidden somewhere. Mixing cards from different writers
  inside one shared container is the whole point.
- **Color coding by writer.** Each muse uses its LLM's brand color
  (Clio orange / Calliope green / Urania blue); the border / accent /
  dot on each memory card matches the writer's color. A viewer should
  be able to see at a glance "Calliope wrote that one, Urania wrote
  that other one, and they're side-by-side in the same store."
- **The tagline.** "Agents don't talk. Memory remembers." Or a near
  variant. This is the takeaway phrase.

## Decorative elements (change freely)

- Specific memory contents in the cards — placeholders, swap with
  whatever resonates for the audience.
- Background — white in the current draft. Dark mode works too; just
  use white cards on a dark vault, not the reverse.
- Typography — current draft uses system sans-serif. Any clean,
  geometric sans works (Inter, IBM Plex Sans, etc.).
- Whether agents have an emoji or an SDK logo. Logos look more
  polished but introduce licensing/trademark complexity.

## Palette

| Element | Hex | Notes |
| --- | --- | --- |
| Clio (Claude / Anthropic) | `#D97757` | terracotta / orange |
| Calliope (GPT / OpenAI) | `#10A37F` | OpenAI green |
| Urania (Gemini / Google) | `#4285F4` | Google blue |
| memclaw vault | `#7850c8` | purple — matches the streamlit demo's memclaw column |
| memclaw tint (fill) | `#F4F0FA` | very pale purple |
| Text — body | `#222` | |
| Text — secondary | `#555` | arrow labels |
| Text — meta | `#888` | turn/attribution chips |

The Anthropic/OpenAI/Google colors approximate brand colors. If you're
publishing this somewhere brand-sensitive, double-check against each
vendor's current brand guidelines — they update occasionally.

## Typography

- Hero / agent names: 22pt, weight 700
- Section labels (e.g. "caura-memclaw — shared fleet"): 20pt, weight 700
- Body / memory text: 14pt
- Meta (turn, attribution): 11pt
- Tagline: 22pt italic

## Variants worth producing

- **Dark mode.** Same composition, but the vault becomes dark purple
  on near-black background, cards become dark gray with brand-colored
  accents. Tagline stays prominent.
- **Animated (for video).** Memory cards fade in over time, each
  appearing inside the vault as its agent "writes" it. Later, a
  faint pulse on a card when a different agent recalls it. Keep the
  no-horizontal-arrow rule even during animation.
- **Wider (presentation aspect).** Pull the three agent cards
  further apart, widen the vault. Same elements, 16:9 friendly.

## What NOT to do

- **Don't draw a hub-and-spoke diagram with arrows between agents.**
  That's the wrong architecture — undoes the entire claim.
- **Don't put memclaw in the middle with agents around it as a circle.**
  Vertical hierarchy (agents above, substrate below) reads more clearly
  as "agents post into a shared place" than a radial layout, which can
  imply peer-to-peer routing through a hub.
- **Don't mix memory cards into per-agent buckets** ("Clio's memories",
  "Calliope's memories"). They share one store; siloing them visually
  breaks the point.
- **Don't add a "controller" or "orchestrator" box.** There isn't
  one. The CLI's turn-rotator is a demo convenience, not part of the
  architecture, and it shouldn't be in this image.

## Use cases

- README hero image (Concept A from the design conversation).
- Slide 1 of any pitch deck explaining caura-memclaw fleets.
- Twitter/LinkedIn post asset when announcing the connector.

For motion / demo videos, see Concept B (timeline / piano-roll) which
is a separate diagram and not covered here.
