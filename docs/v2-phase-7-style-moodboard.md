# Qtown v2 — Futuristic Style Direction Candidates

> **Status:** Working doc for Lock #1 of Phase 7 (style spec). Pick one direction, then we narrow with focused references and ComfyUI test-gens. Created 2026-05-26.

Six directional candidates for "futuristic." Each is distinct enough that test-gens against each will look meaningfully different. Pick one — or tell me which two to combine and how.

---

## 1. Clean Sci-Fi
**Visual feel:** Mass Effect citadel, Star Trek Discovery interiors, Apple-store-as-a-city
**Palette:** Cool whites, chrome, neutral grays, single accent (cyan OR amber, not both)
**Architecture:** Smooth curves, geometric primitives, no ornamentation
**Lighting:** Even, high-key, soft volumetrics; rim lighting on characters
**Character grammar:** Sleek bodysuits, minimalist silhouettes, readable at distance
**Mood:** Serene, optimistic, well-funded research colony
**Pro:** Easy to read at a distance (good for overhead town view); doesn't fight UI overlays
**Con:** Risk of feeling generic — "every sci-fi game looks like this"

---

## 2. Cyberpunk
**Visual feel:** Blade Runner 2049 night scenes, Cyberpunk 2077 street level, Ghost in the Shell
**Palette:** Saturated and high-contrast — hot pink, electric blue, sodium orange, deep black; wet reflections everywhere
**Architecture:** Dense, layered, signage-heavy, neon-lit
**Lighting:** Dramatic, directional, rim and key lights with heavy bloom
**Character grammar:** Detailed, gritty, cybernetic accents, varied silhouettes
**Mood:** Dystopian, alive, chaotic
**Pro:** Most "recognizably futuristic"; high visual interest at interior-room scale
**Con:** Busy — fights data overlays; overhead view risks reading as visual mush

---

## 3. Solarpunk
**Visual feel:** Studio Ghibli meets clean energy; "what if Hayao Miyazaki designed a sci-fi village"
**Palette:** Warm organics — terracotta, sage, ochre, cream — with selective electric blue or copper accents
**Architecture:** Integrated greenery, organic curves, solar/wind elements visible, biophilic
**Lighting:** Warm golden-hour preferred; soft shadows
**Character grammar:** Comfortable clothing, no harsh tech, friendly silhouettes
**Mood:** Hopeful, sustainable, humane — AI town *building* a future not surviving one
**Pro:** Distinctive — almost no sims look like this; emotionally inviting
**Con:** Reads less "futuristic" at a glance; might feel too cozy for what's supposed to be a serious sim

---

## 4. Holographic / Vaporwave Minimalism
**Visual feel:** Severance opening titles, vaporwave aesthetic, "you are watching a simulation"
**Palette:** Pastel + dark — pink/cyan/black, or peach/teal/charcoal
**Architecture:** Flat planes, holographic UI elements visible *in* the world, grid-lines on surfaces
**Lighting:** Flat with selective glows; emissive surfaces
**Character grammar:** Slightly translucent? Outline-emphasis? Could lean abstract
**Mood:** Meta — "this is a simulation, you're seeing the wireframe"
**Pro:** Plays into qtown's identity as an AI-sim *literally*; instantly recognizable
**Con:** Hard to make NPCs feel like real agents if they look like UI elements

---

## 5. Brutalist Futurism
**Visual feel:** Severance corporate floors, Dune architecture, 2001: A Space Odyssey monolith
**Palette:** Muted concrete + slate + bone; single cold accent (steel blue or pale violet)
**Architecture:** Massive geometric forms, sparse ornamentation, ritualistic spaces
**Lighting:** Hard directional, deep shadows, monumental
**Character grammar:** Uniforms, anonymized silhouettes, formal posture
**Mood:** Austere, serious, architectural — power and structure
**Pro:** Maximally distinctive; never seen in a sim; serious art-direction credibility
**Con:** Cold — fights the "watch agents being alive" warmth that interior rooms are for

---

## 6. Glowing-Edge Minimalism (Tron-style)
**Visual feel:** Tron Legacy, Mirror's Edge, qntm-style abstract simulation graphics
**Palette:** Mostly white or mostly black, with glowing colored edges (cyan, magenta, or chartreuse — pick one)
**Architecture:** Hyper-clean geometric forms, edge-lit, instantly readable
**Lighting:** Emissive edges only; otherwise flat and bright
**Character grammar:** Outlined silhouettes with glow accents; readable as data points at distance
**Mood:** Pure simulation, abstract, futuristic-in-the-1980s-imagined-future way
**Pro:** Best legibility for a town with many moving entities; ComfyUI handles this style cleanly
**Con:** Stylized risk — could read as "tech demo" not "real product"

---

## How to pick

Three honest questions to ask yourself:

1. **What's the dominant emotion you want a first-time viewer to feel?** Awe (1, 5), curiosity (4, 6), warmth (3), recognition (2)?
2. **Overhead readability vs. interior intimacy** — which matters more? If overhead, lean toward 1, 5, or 6 (clean, legible). If interior, lean toward 2 or 3 (rich, lived-in).
3. **Risk appetite for distinctive vs. proven** — 1 is safest, 4 is highest variance, 3 and 5 are most "no one else does this."

## What I'll do once you pick

1. Pull focused reference images for that direction (~10–20 images, real artwork + game/film references)
2. Draft 5–6 ComfyUI prompt templates for that style (building exterior, NPC sprite, interior background, activity scene, etc.)
3. Run test-gens (3–5 images per prompt template) once ComfyUI is up
4. You review, we lock or iterate
5. Then move to Lock #2 (rendering grammar — isometric or 2.5D)
