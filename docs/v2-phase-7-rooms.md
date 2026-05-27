# Qtown v2 — Phase 7: Futuristic Art Reboot + Interior Rooms

> **Status:** Design seed. Not yet specced, not yet in `ralph/worklist.json`. Recorded 2026-05-26 after the original decision notes were lost — Kevin re-confirmed "this has always been the v2 vision" and locked Option B (full reboot, both views).

## The vision

Same conceptual layout as v1 — buildings/areas on a town grid — **rendered in a new futuristic art style for the overhead view, AND clickable to drill into building interiors** where you watch the AI NPCs actually working in real time.

| View | What you see | Style |
|---|---|---|
| Overhead town (rebuilt) | Buildings, NPCs walking between them, the town as a whole | **New futuristic** — replaces v1's isometric pixel-art |
| Interior rooms (new) | Inside a single building's rooms: NPCs at the bar drinking, the cook in the kitchen, students in the academy classroom, traders at market stalls, etc. | **New futuristic** — same visual language as overhead |

Both views ship in the new style — no hybrid, no v1 carry-over. v2 should *feel* different from v1 the moment someone loads it.

The product win: v1 was a top-down sim where you *inferred* AI agent behavior from logs and moving dots. v2's drill-in interiors make the AI agents visible — you actually see the LLM-driven NPCs being LLM-driven NPCs instead of imagining it.

## Art direction

**Locked: full futuristic reboot (Option B, 2026-05-26).** Not pixel-art (v1), not Peanuts/cartoon, not any retro aesthetic. Both overhead and interior views share one coherent futuristic visual language.

The specific style spec (palette, references, lighting, character grammar) was decided earlier in qtown's history, was never written down, and is lost as of 2026-05-26. The design pass for Phase 7 must re-establish it before any ComfyUI prompts are written.

**Options considered and rejected:**
- **Option A (pure updated v1, isometric pixel-art everywhere):** rejected — kills the interior-rooms feature; can't show a bartender pouring drinks in isometric pixel art.
- **Option C (hybrid: updated v1 overhead + futuristic interiors):** rejected — reads as unfinished, and the v2 home screen still looking like v1 means most players never click in to see the new style.

## What this is not

- Not Phase 6. Phase 6 (P6-001 through P6-026) is about making the existing v1-equivalent cross-service flows actually work end-to-end. Interior rooms are a product expansion on top of that, not a wiring fix.
- Not a Ralph-grindable backlog yet. Needs a design pass first; Ralph would burn cycles on under-specced stories otherwise.
- Not just "more sprites." It's a new sim-data model, new dashboard view layer, new asset taxonomy, and a new art style — they have to be designed together.

## Scope (what Phase 7 has to deliver)

### Sim & data layer
- Room model in `services/town-core` — buildings have rooms, rooms have activity types, NPCs have a current room + activity state
- Per-room activity state propagated to dashboard (gRPC or Kafka — design choice)
- Likely new proto contracts under `proto/` for room/activity types

### Dashboard layer
- Click handler on overhead view → routes to per-building interior page
- Interior renderer (probably separate from the existing PixiJS isometric layer)
- Per-building UI templates (tavern interior ≠ market interior ≠ academy interior)
- Smooth transition / "zoom-in" affordance so the drill-in feels like one continuous town, not two disconnected views

### Asset pipeline & art
- Lock the futuristic art style + prompt library
- Interior background generation per building type (tavern bar room, tavern kitchen, market floor, market stockroom, academy classroom, academy library, town-core hall, fortress armory, etc.)
- NPC activity-pose sprites (sitting/drinking, standing/teaching, haggling, cooking, sparring, etc.) — replacing v1's single-pose isometric sprites
- ComfyUI batch driver — one-shot pre-gen against the locked spec so Ollama (Ralph) and ComfyUI never fight for the GPU during the implementation phase

### Worklist
- Likely 25–40 stories appended as `P7-001` onward across the services + dashboard + asset-pipeline
- Same Ralph v2 routing rules as Phase 6 (`architect|design|refactor` → 27b, default → qwen3-coder-next, `debug|investigate` → r1:14b)

## Open design questions (block Ralph until answered)

1. **Art style** — what is "futuristic" concretely? Cyberpunk? Clean sci-fi? Solarpunk? Mood references? Color palette? Lighting? This needs prompt-able language, not vibes.
2. **Room taxonomy** — for each of v1's 21 building types, what rooms exist inside? What activities happen in each room?
3. **Sim-data fidelity** — does the sim actually track per-room activity already, or do we need to add positional state at room granularity to `town-core`?
4. **Drill-in UX** — modal? Full-page route? Animated zoom transition? Browser history per drill-in or not?
5. **Render strategy for interiors** — 2.5D parallax? Side-view? Top-down at a finer granularity? Each building same view convention or per-building art direction?
6. **NPC pose count** — how many activity poses per NPC role? Static frames or animated loops?
7. **Performance budget** — interiors might have ~5–15 NPCs visible at once; what's the FPS/asset-size target?

## Prerequisite: Phase 6 must close first

Don't open Phase 7 design until P6-022, P6-023, P6-024 (the three E2E flow tests) are green and the Phase 6 dashboard is rendering v1-sprite-baseline correctly. Phase 7 piles new product surface on top of working plumbing — opening it on broken plumbing means debugging two problems at once.

## Recovery note

This concept was decided once before, lived in Kevin's head + a now-lost note, and was at risk of being lost again on 2026-05-26. **If you're reading this and it conflicts with newer decisions, the newer decisions win — but make sure those newer decisions are also persisted somewhere durable.** Don't trust memory or notes-in-other-projects to carry product vision.
