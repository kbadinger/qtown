# Asset Inventory & Gap Plan — Qtown v2

> Companion to `docs/plans/02-ASSETS.md`. This is the **have / missing / build-step**
> ledger Kevin asked for. Source of truth: `asset-gen/taxonomy.yaml` (`locked: true`,
> 19 buildings · 35 rooms · 10 roles × 6 poses) and `asset-gen/style-spec.md` (solarpunk
> + tech accents). Verified against the repo on 2026-06-12.

## TL;DR — where the assets actually stand

**You have zero v2 assets. The pipeline that builds them is also unfinished.**

| Thing | State |
|---|---|
| `asset-gen/output/` | **Empty** — 0 generated files (the generated library is unbuilt) |
| `asset-gen/run_batch.py` | **~60% built and improving.** Working inline Flux+LoRA workflow builder, ComfyUI submit/poll/download, taxonomy-driven planning. **2026-06-13 (box-independent parts, validated offline):** deterministic per-asset seeds, all-6-poses overhead NPCs (was idle-only → now 60), `interior_cast`-driven deduped activity planning, `genlog.jsonl` provenance, offline `--plan` + `--manifest`. **Still box-coupled / TODO:** IP-Adapter + ControlNet node wiring (identity/pose consistency), rembg/WebP post-process (P7A-004) |
| `asset-gen/taxonomy.yaml` | ✅ Locked; **+ additive `interior_cast` matrix + class-E extras (P7A-002, done)** |
| `asset-gen/style-spec.md` | ✅ Locked and complete |
| `asset-gen/workflows/*.json` | Only `INSTALL.md`. **Superseded:** workflows are built inline in `run_batch.py` (parameterized), so separate JSON files are not needed — P7A-001 is now "wire IP-Adapter/ControlNet into the inline builder," done with the box in the loop |
| `services/town-core/assets/` | 39 buildings + 37 NPCs — **v1 pixel art, off-taxonomy, wrong style.** v1 fallback only (P6-021), not reusable for the v2 look |

So the v2 asset **library is 0% generated**, but the **pipeline is ~60% built** and the
box-independent half landed on 2026-06-13. `python3 run_batch.py --plan` now prints the
real manifest offline: **A=19, B=60, C=35, D=94 (deduped), E=21 → 229 total.** Remaining
work maps to Phase 7-A stories (P7A-001 IP-Adapter/ControlNet, P7A-003 finish,
P7A-004 postprocess, P7A-006 LoRA) in `ralph/worklist.json`.

This lane has **zero dependency on Phase 6** — it can start the moment the ComfyUI
workflows exist (P7A-001), in parallel with all service wiring.

## The full manifest (derived from the locked taxonomy)

### Class A — Overhead building exteriors · 19 total · **0 have / 19 missing**
- 13 standard @ 512×512, 6 hero @ 1024×1024.
- **Hero (1024):** `tavern`, `market`, `academy`, `town_hall`, `validation_citadel`, `tower`.
- **Standard (512):** home, blacksmith, bakery, farm, clinic, temple, workshop, warehouse,
  bank, courthouse, restoration_center, theater, park.
- Output: `output/overhead/buildings/<building_id>.png` → WebP.

### Class B — Overhead NPC sprites · 60 total · **0 have / 60 missing**
- 10 roles × 6 poses, transparent (rembg). Identity locked via IP-Adapter (gen each
  role's `idle` first, approve, condition the other 5 on it).
- Roles × poses (from taxonomy):

  | Role | Poses |
  |---|---|
  | trader | idle, walking, haggling, selling, carrying_goods, talking |
  | scholar | idle, walking, reading, teaching, researching, talking |
  | artisan | idle, walking, crafting, working, examining_work, talking |
  | farmer | idle, walking, planting, harvesting, tending, talking |
  | healer | idle, walking, examining, treating, preparing_remedy, talking |
  | cook | idle, walking, cooking, kneading, serving, talking |
  | smith | idle, walking, forging, hammering, examining_metal, talking |
  | guard | idle, walking, patrolling, observing, talking, deterring |
  | official | idle, walking, addressing, documenting, listening, talking |
  | child | idle, walking, running, playing, watching, talking |

- Output: `output/overhead/npcs/<role>_<pose>.png` → WebP.

### Class C — Interior room backgrounds · 35 total · **0 have / 35 missing**
- One 1280×720 plate per room, no characters. `park` has no rooms (overhead-only).
- Flagship 5 rooms also get parallax mid/foreground layers cut from the plate
  (SAM-assisted); second-ring rooms ship flat plates first.
- Rooms per building:

  | Building | Rooms (each needs a background) |
  |---|---|
  | tavern | bar_room ★, kitchen, cellar |
  | market | trading_floor ★, stockroom |
  | academy | classroom ★, library, laboratory |
  | town_hall | assembly, office |
  | home | living_room, bedroom, kitchen |
  | blacksmith | forge, showroom |
  | bakery | bakehouse, shopfront |
  | farm | barn, greenhouse |
  | clinic | examination, dispensary |
  | temple | sanctuary, garden |
  | workshop | workspace |
  | warehouse | storage_floor |
  | bank | lobby, vault |
  | courthouse | courtroom |
  | restoration_center | counseling, reflection_garden |
  | theater | stage, audience |
  | tower | observation_deck ★ |
  | validation_citadel | verification_chamber ★, arbitration |

  ★ = flagship five (build + QA first → unblocks Phase 7-B integration).
- Output: `output/interior/backgrounds/<building_id>_<room_id>.png` → WebP.

### Class D — Interior NPC activity poses · ~95–110 unique · **0 have / ~100 missing**
- The curated `(role × activity)` matrix — **not** the 500+ full cross-product. Curation
  rule (P7A-002): for each room, cast 1–2 roles per activity (natural worker + one
  visitor). Dedupe by `(role, activity)` — a `trader_talking` is generated once, reused
  everywhere traders talk.
- 384×512, transparent. Identity via IP-Adapter from the role's approved idle; pose via
  ControlNet-OpenPose (one reference skeleton per activity in `asset-gen/poses/`).
- **Resolved (P7A-002, done):** the additive `interior_cast` matrix is in `taxonomy.yaml`
  and `run_batch.py --plan` prints the real deduped count: **94 unique activity sprites**.
- Output: `output/interior/activities/<role>_<activity>.png` → WebP.

### Class E — World & chrome extras · ~21 · **0 have / ~21 missing**
| Asset | Count | Size | Notes |
|---|---|---|---|
| Ground tiles (grass, path, plaza, garden bed, water, soil) | ~10 | 512×512 tileable | Overhead terrain |
| Overhead props (trees ×3, benches, solar bollard, planter, drone, cart) | ~8 | 256×256 transparent | Scatter decoration |
| Landing hero panorama | 1 | 1920×1080 | Replaces coming-soon art |
| OG/social image | 1 | 1200×630 | Crop of hero |
| Favicon source (tower glyph) | 1 | 512×512 | — |

UI chrome (proof-panel frame, docs drawer, room tabs, speech bubbles) is **hand-built
SVG/CSS in the dashboard, not generated** — palette tokens go to
`dashboard/assets/style-tokens.css`. Day/night variants + animation loops are deferred to
Phase 8 (deliberate; doubles the library for no interview signal).

## Totals & cost

| Class | Missing | Notes |
|---|---|---|
| A exteriors | 19 | 6 hero @ 1024, 13 @ 512 |
| B overhead NPCs | 60 | 10×6, IP-Adapter identity |
| C interior backgrounds | 35 | flagship 5 also get parallax cuts |
| D interior poses | ~95–110 | curated, count finalized by P7A-002 |
| E extras | ~21 | + hand-built UI chrome (not generated) |
| **Total unique** | **~235** | |
| **+ ~30% regen overhead** | **~310 generations** | |
| **GPU time** | **~3–4 GPU-hours** | Flux.1-dev fp8, 25 steps, RTX 3090. Test-gens = minutes (schnell @ 4 steps) |

## Build steps (each maps to a worklist story)

| Step | Story | Who | Output |
|---|---|---|---|
| 1. Author 4 ComfyUI workflow JSONs (Flux + IP-Adapter + ControlNet) | **P7A-001** | Opus authors · Kevin runs on 3090 | `asset-gen/workflows/*.json` |
| 2. Add `interior_cast` + class-E lists to taxonomy (additive) | **P7A-002** | Opus | finalizes Class-D count |
| 3. Finish `run_batch.py` (expand/submit/poll/retry/filters/genlog) | **P7A-003** | Opus | working batch driver |
| 4. Post-process (rembg, WebP, contact sheets) | **P7A-004** | Ralph | QA-ready outputs |
| 5. Emit `assets/manifest.json` for the dashboard | **P7A-005** | Ralph | zero-hardcoded-path rendering |
| 6. LoRA A/B decision | **P7A-006** | Opus + Kevin GPU | `asset-gen/DECISIONS.md` |

## Execution protocol on the 3090 box (Kevin's hands)

1. **Test gate** — `run_batch.py --mode test --limit 10` (schnell) → review contact sheet
   → approve direction or tune prompts. Per class. Cheap; do before any production burn.
2. **Flagship-first production** (~70 assets) — Class A hero 6 + Class C flagship 5 +
   the Class B roles those rooms cast + their Class D poses. QA-pass. **This unblocks
   Phase 7-B integration before the full library exists.**
3. **Full batch** — remaining classes, `--only-new`.
4. **QA bar (style-spec):** palette only (terracotta/sage/copper/cyan), front-facing
   characters, no banned elements (chrome/concrete/neon/pixel-art/text artifacts), clean
   transparency, identity-consistent per role. **Regen misses rather than ship
   inconsistency.**
5. **Publish** — WebP + `manifest.json` → asset-pipeline storage (P6-016) → public URLs.
   Originals + seeds + `genlog.jsonl` stay in `asset-gen/output/` (provenance).

## The one fact that matters

Nothing visible ships without these assets, and **none of them exist yet** — but the lane
is fully parallelizable (3090 box, no Phase-6 dependency). The single highest-leverage
first move on the asset side is **P7A-001 + P7A-002 + P7A-003** (the pipeline), because
the moment those land, Kevin can test-gen and the ~3–4 GPU-hours can run while service
wiring proceeds on a different machine.
