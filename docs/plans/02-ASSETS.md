# Plan 02 — Assets: Manifest, Generation Pipeline, QA Bar

> Part of the v2 plan pack (`00-MASTER-PLAN.md`). Owns Phase 7-A.
> Locked inputs: `asset-gen/style-spec.md` (solarpunk + tech accents, prompt templates,
> negative prompts), `asset-gen/taxonomy.yaml` (locked 2026-05-26).
> Pipeline state today: style spec ✅, taxonomy ✅, `workflows/*.json` ❌ (only
> INSTALL.md exists), `run_batch.py` exists but untested against real workflows,
> test-gens ❌, production batch ❌.
> Runs on Kevin's i9 + RTX 3090 box (ComfyUI :8188) — **zero dependency on Phase 6**,
> start immediately, in parallel with everything else.

## 1. The manifest — every asset v2 ships

All counts derive from the locked taxonomy. Generators MUST read the taxonomy at run
time (`run_batch.py` already does) — the numbers below are the human-readable contract,
not a second source of truth.

### 1.1 Class A — Overhead building exteriors (19)

| Spec | Value |
|---|---|
| Prompt template | style-spec §"Overhead building exterior" |
| Size | 512×512 standard; **1024×1024 hero** for the 6 landmark buildings: tavern, market, academy, town_hall, validation_citadel, tower |
| Count | 19 (13 standard + 6 hero) — park renders as an exterior "open block" asset |
| Output | `output/overhead/buildings/<building_id>.png` |
| Post | WebP convert; hero also gets a 512 downscale for the grid |

### 1.2 Class B — Overhead NPC sprites (60)

10 roles × 6 poses each (pose lists locked per role in taxonomy `activity_poses`).

| Spec | Value |
|---|---|
| Prompt template | style-spec §"Overhead NPC sprite" |
| Size | 256×256, transparent background (rembg post-process) |
| Consistency | IP-Adapter: generate each role's `idle` first, approve it, then condition the other 5 poses on it — same trader stays the same trader |
| Output | `output/overhead/npcs/<role>_<pose>.png` |

### 1.3 Class C — Interior room backgrounds (35)

One per room in the taxonomy (park has none).

| Spec | Value |
|---|---|
| Prompt template | style-spec §"Interior room background" + the room's `description` |
| Size | 1280×720, no characters |
| Layering | Generate as one plate; the parallax mid/foreground layers (Plan 01 §3.5) are cut from the plate in post (manual or SAM-assisted) for the 5 flagship rooms only; second-ring rooms ship flat plates first |
| Output | `output/interior/backgrounds/<building_id>_<room_id>.png` |

### 1.4 Class D — Interior NPC activity poses (~100)

The curated (role × activity) matrix — NOT the full cross-product (which would be
500+). Curation rule: **for each room, cast 1–2 roles per activity** (the natural
worker + one visitor role). The canonical cast matrix is added to the taxonomy as a new
additive field (taxonomy stays locked; this adds, it doesn't change):

```yaml
# appended per-room in taxonomy.yaml
interior_cast:
  - {activity: cooking, roles: [cook]}
  - {activity: drinking, roles: [trader, farmer]}
  ...
```

Dedupe by (role, activity): a `trader_talking` sprite is generated once and reused in
every room where traders talk. Expected unique count ≈ **95–110 sprites**.

| Spec | Value |
|---|---|
| Prompt template | style-spec §"NPC activity pose" |
| Size | 384×512, transparent background |
| Pose control | ControlNet OpenPose — one reference skeleton per activity type (sitting-drinking, standing-teaching, haggling…), kept in `asset-gen/poses/`; identity via IP-Adapter from the role's approved idle sprite |
| Output | `output/interior/activities/<role>_<activity>.png` |

### 1.5 Class E — World & chrome extras (~25, additions not yet in taxonomy)

| Asset | Count | Size | Notes |
|---|---|---|---|
| Ground tiles (grass, path, plaza, garden bed, water feature, soil) | ~10 | 512×512 tileable | Overhead terrain under buildings |
| Overhead props (trees ×3, benches, solar bollard, planter, drone, cart) | ~8 | 256×256 transparent | Scatter decoration |
| Landing hero | 1 | 1920×1080 | Town panorama in locked style — replaces the coming-soon art |
| OG/social image | 1 | 1200×630 | Crop of hero |
| Favicon source | 1 | 512×512 | Single building glyph (tower) |
| Day→night variants | 0 | — | **Deliberately deferred to Phase 8** (doubles the library; style spec's night grammar is ready when wanted) |

UI chrome (proof-panel frame, docs drawer, room tabs, speech bubbles) is **hand-built
SVG/CSS in the dashboard, not generated** — generated UI chrome reads as mush at small
sizes; the palette tokens from the style spec move into a `dashboard/assets/style-tokens.css`.

### 1.6 Totals

| Class | Count |
|---|---|
| A — building exteriors | 19 |
| B — overhead NPC sprites | 60 |
| C — interior backgrounds | 35 |
| D — interior activity poses | ~100 |
| E — extras | ~21 |
| **Total unique assets** | **~235** |
| With ~30% regen overhead | ~310 generations |
| GPU time @ ~35s/img (Flux.1-dev fp8, 25 steps, 3090) | **~3–4 GPU-hours** for production; test-gens are minutes (schnell @ 4 steps) |

## 2. Pipeline completion — what Opus builds before Kevin presses go

| ID | Story | Done when |
|---|---|---|
| P7A-001 | Author 4 ComfyUI workflow JSONs (one per class A–D) per `workflows/INSTALL.md` model layout: Flux.1-dev fp8 + IP-Adapter + ControlNet-OpenPose nodes, parameterized prompt/size/seed inputs | Each workflow validates via ComfyUI `/prompt` API dry-run |
| P7A-002 | Add `interior_cast` matrix to taxonomy.yaml (additive field, per §1.4 rule) + class-E extras list | `run_batch.py --plan` prints the full manifest with counts matching §1.6 ±10% |
| P7A-003 | Finish `run_batch.py`: manifest expansion, job submit, poll, download, retry-on-failure, `--only-new`, `--only-class`, deterministic seeds logged per asset | `--mode test --limit 10` produces 10 correctly named files |
| P7A-004 | Post-process step: rembg for B/D transparency, WebP conversion, contact-sheet generator (one grid PNG per class for QA review) | `postprocess.py` runs on test batch; contact sheets render |
| P7A-005 | `assets/manifest.json` emitter — building/room/sprite → relative path, consumed by the dashboard (Plan 01 §5) and served via asset-pipeline storage (P6-016) | Dashboard InteriorRenderer loads a room purely from manifest |
| P7A-006 | LoRA selection: evaluate the `config.yaml` candidate slots — run A/B test-gens with vs without a solarpunk LoRA; pick or drop | Decision + seeds recorded in `asset-gen/DECISIONS.md` |

## 3. Execution protocol (Kevin + the 3090 box)

1. **Test gate:** `run_batch.py --mode test --limit 10` (schnell) → Kevin reviews the
   contact sheet → approve direction or tune prompts. Repeat per class. *Cheap, fast,
   do this before any production burn.*
2. **Flagship-first production:** generate Class A hero 6 + Class C flagship-5 rooms +
   Class B for the roles those rooms cast + their Class D poses (~70 assets). Kevin
   QA-pass. This unblocks Phase 7-B integration before the full library exists.
3. **Full batch:** remaining classes, `--only-new`.
4. **QA pass per batch (the style-spec bar):** style consistency is priority #1 —
   regen misses rather than ship inconsistency. Checklist per asset: palette compliance
   (terracotta/sage/copper/cyan only), front-facing characters, no banned elements
   (chrome/concrete/neon/pixel-art/text artifacts), transparent edges clean, identity
   consistent within a role.
5. **Publish:** post-processed WebP + `manifest.json` → `services/asset-pipeline`
   storage path (P6-016) → public URLs the dashboard fetches. Originals + seeds stay in
   `asset-gen/output/` (git-LFS or kept local; decide at publish — only WebP +
   manifest enter the repo/CDN).

## 4. Acceptance criteria for Gate C (Phase 7-A done)

- `manifest.json` covers 100% of taxonomy rooms/roles; dashboard can render any room
  with zero hardcoded asset paths.
- Contact sheets for all classes reviewed and approved by Kevin (the human QA gate is
  the style lock working as designed).
- Every asset's generation is reproducible: prompt, seed, workflow, and model hash
  logged in `asset-gen/output/genlog.jsonl`.
- No GPU contention risk left: the batch is complete before Ralph/Ollama activation, or
  runs on the 3090 box while Ralph runs on the Mac (the architecture already separates
  them — keep it that way).
