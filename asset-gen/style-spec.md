# Qtown v2 — Locked Style Spec

> **Status:** Locked 2026-05-26 (Guardian decision `2f7c20c8`). Solarpunk + tech accents.

## One-line identity

A hopeful sci-fi town where AI agents build a future worth living in — Studio Ghibli warmth meets visible-but-integrated technology.

## Palette

### Primary (warm organics — the *solarpunk* layer)
- Terracotta `#C2674A`
- Sage green `#9CB68F`
- Ochre yellow `#D4A04C`
- Cream `#F4EAD8`
- Warm wood brown `#7A5230`

### Accent (the *tech* layer — used sparingly, ~5–10% of any composition)
- Electric copper `#E08B3C` (glowing signage, holo-elements)
- Bioluminescent cyan `#5FCFC4` (holographic UI, drone lights)
- Solar gold `#F2C84B` (solar panel glow, energy indicators)

### Neutrals
- Slate gray `#5C6670` (structural elements)
- Soft white `#FAF7F0` (cloth, paper, UI panels)

## Lighting

- **Default:** warm golden-hour preferred — soft directional light, long-but-not-harsh shadows
- **Night scenes:** deep blue ambient + bioluminescent cyan/copper accents from tech elements
- **Interior:** mixed warm practical lighting (lanterns, light strips) + cool tech accent points
- Always: soft volumetric haze for depth, never harsh contrast

## Architecture

- Integrated greenery (vines, climbing plants, green roofs, hanging gardens on every building)
- Organic curves over hard geometric edges — buildings *look* grown, not built
- Visible solar/wind tech — solar tiles on roofs, small wind turbines, water collection visible
- Holographic signage above shops (the only "screen" tech you see — no flat displays, only holos)
- Materials: warm wood, terracotta, woven fiber, brushed copper accents, glowing glass details
- No: chrome, no concrete, no harsh angles, no cyberpunk neon, no flat screens

## Character grammar

- **Always front-facing** (Pokémon-style 2.5D) — characters face the camera even in top-down overhead view
- Comfortable practical clothing — flowing layered fabrics, earth tones, with subtle tech detailing (glowing embroidery, holo-bracelets, integrated tool belts)
- Friendly expressive faces — large readable eyes, soft features
- Slightly stylized proportions (1:6 head-to-body) for readability at distance
- Multiple poses per character covering full activity range (idle, working, walking, sitting, sleeping, talking)
- Hair and clothing should suggest motion — slight wind, never perfectly still

## Mood prompts (positive)

Universal style suffix to append to every generation:

```
solarpunk aesthetic, studio ghibli inspired, hopeful futuristic,
warm golden hour lighting, integrated greenery, soft volumetric atmosphere,
terracotta and sage palette, copper and cyan tech accents,
holographic signage, organic architecture, flowing natural materials,
front-facing character, soft shadows, no harsh edges, no chrome, no concrete
```

## Negative prompts

Universal negative suffix:

```
cyberpunk, dystopian, dark, grimdark, neon noir, blade runner,
chrome, concrete, brutalist, harsh geometric, flat displays, screens,
photorealistic, 3d render, blurry, low quality, deformed, multiple characters,
text, watermark, gradient, amateur, sketch, rough, isometric, pixel art,
back view, side profile, generic sci-fi
```

## Prompt templates by asset class

### 1. Overhead building exterior (top-down 3/4 view)

```
top-down 3/4 view of a [BUILDING_TYPE] in a hopeful solarpunk town,
[BUILDING_DESCRIPTION], integrated greenery, solar panels on roof,
holographic signage, terracotta and sage palette, copper tech accents,
warm golden hour lighting, studio ghibli inspired, no characters,
empty exterior scene, clean illustration
```

Sized: 512×512 for grid tiles, 1024×1024 for hero buildings.

### 2. Overhead NPC sprite (front-facing, top-down 3/4 view)

```
front-facing portrait of a [NPC_ROLE] in solarpunk village,
[NPC_DESCRIPTION], earth-tone flowing clothing, friendly expression,
studio ghibli character design, warm lighting, full body visible,
plain background, [ACTIVITY_POSE], no other characters
```

Sized: 256×256 sprite, transparent background via post-process.

### 3. Interior room background (side-view)

```
side-view interior of a [ROOM_TYPE] in a solarpunk [BUILDING_TYPE],
[ROOM_DESCRIPTION], warm wood floors, terracotta walls,
green plants integrated, holographic signage details, copper accents,
lanterns and light strips, no characters, empty scene,
studio ghibli inspired interior, cozy atmosphere
```

Sized: 1280×720 for room backgrounds.

### 4. NPC activity pose (side-view interior, full body in action)

```
side-view of a [NPC_ROLE] [ACTIVITY] in a solarpunk [ROOM_TYPE],
[ACTIVITY_DESCRIPTION], earth-tone clothing, studio ghibli style,
warm interior lighting, copper and cyan tech accents,
front-facing or 3/4 view, full body visible, transparent background
```

Sized: 384×512 (taller for full-body activity poses).

## What each [PLACEHOLDER] gets filled with

Pulled from `taxonomy.yaml` at gen time. For example:
- `[BUILDING_TYPE]` → `tavern`
- `[BUILDING_DESCRIPTION]` → `cozy two-story building with wooden balcony, hops growing up the walls, copper brewing chimney`
- `[NPC_ROLE]` → `trader`
- `[ACTIVITY_POSE]` → `holding goods, mid-transaction gesture, smiling`
- `[ROOM_TYPE]` → `bar room`
- `[ACTIVITY]` → `pouring a drink from a copper tap`

## Quality bar

- Style consistency across the full library is the #1 priority. Better to regenerate misses than ship inconsistent style.
- IP-Adapter applied for character consistency across pose variants — same trader looks like the same trader haggling vs. walking vs. sitting.
- ControlNet (OpenPose) for activity poses — lock body language per activity type, vary character identity via prompt.
- Manual QA pass after each batch — visual diff against reference images, regen failures.

## How to extend

If a new building type, NPC role, or activity gets added to the sim later (Phase 8+), append to `taxonomy.yaml` and re-run `run_batch.py --only-new`. The style spec stays locked unless explicitly revised — and a revision means a new locked version, full library regen.
