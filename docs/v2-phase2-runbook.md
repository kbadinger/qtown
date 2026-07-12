# Qtown v2 — Phase 2 Setup Runbook

**Status:** Draft 1 · 2026-05-06
**Companions:** [`v2-pipeline.md`](./v2-pipeline.md) (the why) · [`visual-style-guide.md`](./visual-style-guide.md) (the manifest)

This is the step-by-step you follow on the 3090 Ti to get from "ComfyUI is installed" to "5-sprite trial generated, ready for full batch." Pipeline doc has the rationale; this doc is just the concrete download/install/curate/verify checklist.

**Estimated time to complete this runbook (excluding the actual batch generation):** 4-5 hours.

---

## TL;DR — the batch is automated (`run_batch.py`)

> **The actual sprite generation is fully automated by `asset-gen/run_batch.py`.** It builds the
> Flux + LoRA ComfyUI workflow *in code* (`build_workflow()`), derives every prompt from
> `taxonomy.yaml` + `style-spec.md`, submits to ComfyUI's HTTP API, uses deterministic per-sprite
> seeds, logs provenance to `genlog.jsonl`, and **skips anything already generated** (resumable).
>
> So Steps 0–7 are the one-time **setup** (models, LoRAs, custom nodes, reference images) and are
> still required. Steps 8–9 (hand-building workflow JSONs / prompt files) are **optional** — useful
> only for one-off validation in the ComfyUI UI; the batch does not need them.
>
> **Current state:** 86 of 229 sprites generated (all 19 buildings + all 35 room interiors done).
> **143 remain** — 50 NPC poses, 72 activity poses, 21 terrain tiles.
>
> **To generate the remaining 143** (run from `asset-gen/`, after setup + a green trial):
> ```bash
> python3 run_batch.py --mode test --limit 5          # trial gate (Step 10) — eyeball 5 first
> python3 run_batch.py --mode production               # fills only the missing sprites (skips the 86 done)
> python3 run_batch.py --mode production --only npcs   # or target one category: npcs | activities | buildings | interiors
> ```
> Add `--regen` to overwrite existing, `--plan` to dry-run the job list.

---

## Step 0 — Pre-flight

**What:** free up the 3090 Ti and confirm prerequisites.

```bash
# Stop Ollama (Windows)
ollama stop          # if running as a service
# or kill the process: Get-Process ollama | Stop-Process -Force

# Confirm Python ≥ 3.10
python --version

# Confirm CUDA
nvidia-smi           # should show "RTX 3090 Ti, 24576MiB"
```

**Verify:** GPU memory shows ~24GB free, no Ollama process running.

---

## Step 1 — Install / update ComfyUI

**What:** get the latest ComfyUI on the 3090 Ti rig.

If you already have ComfyUI:
```bash
cd C:\path\to\ComfyUI
git pull
.\python_embeded\python.exe -m pip install -r requirements.txt --upgrade
```

If you're starting fresh (download the portable Windows build):
- https://github.com/comfyanonymous/ComfyUI/releases/latest
- Pick `ComfyUI_windows_portable_nvidia.7z`
- Extract to `C:\ComfyUI` (or wherever)

Install ComfyUI-Manager (you'll need this for custom nodes):
```bash
cd C:\ComfyUI\custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager
```

**Verify:** launch ComfyUI (`run_nvidia_gpu.bat` in the portable build) — it should open at `http://127.0.0.1:8188` and show the Manager button in the top-right.

---

## Step 2 — Download Flux base model + VAE + text encoders

**What:** the foundation models. ~30GB total.

You need a HuggingFace account + access agreement (one-click on the model page).

| File | Source | Place in |
|---|---|---|
| `flux1-dev.safetensors` (~24GB) | [black-forest-labs/FLUX.1-dev](https://huggingface.co/black-forest-labs/FLUX.1-dev/blob/main/flux1-dev.safetensors) | `ComfyUI/models/unet/` |
| `ae.safetensors` (~335MB) | [black-forest-labs/FLUX.1-dev](https://huggingface.co/black-forest-labs/FLUX.1-dev/blob/main/ae.safetensors) | `ComfyUI/models/vae/` |
| `clip_l.safetensors` (~250MB) | [comfyanonymous/flux_text_encoders](https://huggingface.co/comfyanonymous/flux_text_encoders/blob/main/clip_l.safetensors) | `ComfyUI/models/clip/` |
| `t5xxl_fp8_e4m3fn.safetensors` (~5GB) | [comfyanonymous/flux_text_encoders](https://huggingface.co/comfyanonymous/flux_text_encoders/blob/main/t5xxl_fp8_e4m3fn.safetensors) | `ComfyUI/models/clip/` |

**Why fp8 t5xxl:** the fp16 version eats ~10GB VRAM. fp8 fits comfortably with Flux + IPAdapter all loaded.

**Verify:** in ComfyUI → Manager → "Model Manager", these four files show as present. Or check the directories directly with `dir`.

---

## Step 3 — Install custom nodes (via ComfyUI-Manager)

**What:** the nodes that make Flux + IPAdapter + ControlNet + BiRefNet work in ComfyUI.

Open ComfyUI in the browser → click **Manager** → **Install Custom Nodes** → search and install each:

1. **ComfyUI-IPAdapter-Flux** (XLabs implementation) — search "IPAdapter Flux" pick the XLabs one
2. **ComfyUI-Advanced-ControlNet** — search "Advanced ControlNet"
3. **ComfyUI-RMBG** — search "RMBG"; this gives you BiRefNet
4. **rgthree-comfy** — search "rgthree"; quality-of-life for batch queues
5. **ComfyUI-Custom-Scripts** — search "Custom Scripts"; auto-saves workflows

After all install: **Restart ComfyUI** (close the window + relaunch the .bat, or use Manager → "Restart").

**Verify:** in ComfyUI's node menu (right-click empty canvas → search), nodes like `ApplyIPAdapterFlux`, `ControlNetApplyAdvanced`, `BiRefNet RMBG`, `Power Lora Loader (rgthree)` are all available.

---

## Step 4 — Download IPAdapter for Flux + vision encoder

**What:** the IPAdapter model file + its vision encoder.

| File | Source | Place in |
|---|---|---|
| `flux-ip-adapter.safetensors` (~3GB) | [XLabs-AI/flux-ip-adapter](https://huggingface.co/XLabs-AI/flux-ip-adapter/blob/main/flux-ip-adapter.safetensors) | `ComfyUI/models/ipadapter-flux/` (create dir if missing) |
| Vision encoder: `google/siglip-so400m-patch14-384` | [HF page](https://huggingface.co/google/siglip-so400m-patch14-384) | Auto-downloads on first run via the IPAdapter Flux node — but you can pre-download to `ComfyUI/models/clip_vision/` |

**Verify:** in a fresh ComfyUI workflow, drop a `LoadIPAdapterFlux` node — it should list `flux-ip-adapter.safetensors` in its dropdown.

---

## Step 5 — Download ControlNet for Flux (Canny)

**What:** the ControlNet model for composition-locking buildings.

| File | Source | Place in |
|---|---|---|
| `flux-canny-controlnet.safetensors` (~6GB) | [XLabs-AI/flux-controlnet-collections](https://huggingface.co/XLabs-AI/flux-controlnet-collections/blob/main/flux-canny-controlnet-v3.safetensors) | `ComfyUI/models/controlnet/` |

**Verify:** Manager → Model Manager shows the file; or `dir ComfyUI\models\controlnet\flux-canny*.safetensors`.

---

## Step 6 — Download the base style LoRA from CivitAI ⭐ (this is the key step you asked about)

**What:** the LoRA that gives every sprite the "isometric sticker cartoon" look — equivalent to v1's `zavy-ctsmtrc`. Without this, Flux outputs generic photoreal-ish stuff.

### Primary candidate (try first):

| File | Source | Place in |
|---|---|---|
| `flux-mobile-game-isometric-building.safetensors` (~38MB) | [CivitAI 1901291 — Flux Mobile Game Isometric Building](https://civitai.com/models/1901291/flux-mobile-game-isometric-building) | `ComfyUI/models/loras/` |

**To download from CivitAI:**
1. Open the page, click the orange **Download** button next to the latest version
2. CivitAI may ask you to log in (free account works)
3. The file lands in your browser's download folder; move it to `ComfyUI/models/loras/`

**Trigger phrase for prompts:** `isometric building mobile game style`
**Recommended strength:** `0.8` to `0.9`
**Sampler settings (per the model card):** Euler, CFG 3.5, 20-40 steps

### Fallback candidate (only if primary fails the trial):

| File | Source | Place in |
|---|---|---|
| `Flux-Game-Assets-LoRA-v2.safetensors` (~38MB) | [HF gokaygokay/Flux-Game-Assets-LoRA-v2](https://huggingface.co/gokaygokay/Flux-Game-Assets-LoRA-v2) | `ComfyUI/models/loras/` |

**Trigger phrase:** `wbgmsst, [your description here], white background`
**Recommended strength:** `0.7`

You can download both upfront (~76MB total) so the swap is fast if needed.

**Verify:** in ComfyUI → drop a `LoraLoader` node → both files appear in its dropdown.

---

## Step 7 — Curate the 10 IPAdapter reference images

**What:** one mood image per neighborhood that gets fed to IPAdapter as the "look here for this district's vibe" reference. Plus one global reference for cross-batch consistency.

Per `visual-style-guide.md` § 4 (per-neighborhood mood) + reference touchstones, you need:

| # | Slot | Source suggestion |
|---|---|---|
| 1 | Town Hall | A photo of a Florentine palazzo or Roman forum at midday, ~1024×1024 |
| 2 | Market District | A bustling Marrakech souk or Camden Market shot with copper awnings |
| 3 | The Fortress | An Edinburgh Castle keep with brass-bound details (wide shot) |
| 4 | The Academy | The Bodleian Library or a Victorian Tesla lab interior |
| 5 | The Tavern | A Renaissance inn / Prancing Pony illustration with hearth glow |
| 6 | The Library | The Trinity College Long Room |
| 7 | Cartographer's Guild | A mapmaker's office or the Doge's Palace map room |
| 8 | Artisan's Workshop | A medieval guild hall or Aardman Animations workshop |
| 9 | Roads + countryside | A Roman road / Pilgrim's Way with milestones |
| 10 | Global "qtown set" | A clean isometric sticker-cartoon game asset image (search "tycoon game isometric building art") |

**Sources:** Wikipedia / Wikimedia Commons (CC-licensed, safe), Unsplash, your own collected references. **Avoid:** copyrighted game screenshots — they'll lawsuit-bait your blog post.

**Place all 10 in:** `ComfyUI/input/qtown-refs/` (create dir).

**Naming:** `ref-01-town-hall.jpg`, `ref-02-market.jpg`, ..., `ref-10-global.jpg`. The workflows will reference these by filename.

**Verify:** all 10 files present, each ~1024×1024 (or larger — ComfyUI will resize).

---

## Step 8 — Build the four ComfyUI workflows

> **Optional — `run_batch.py` builds this workflow in code** (`build_workflow()`), so you do **not**
> need to hand-build or save workflow JSONs for the batch. Do this step only to eyeball the graph or
> debug generation interactively in the ComfyUI UI.

**What:** the actual graph that generates a sprite. One workflow per sprite type (building, NPC, prop, terrain).

Per `v2-pipeline.md` § 4, each workflow has roughly this graph:

```
[Load Flux UNet] ─┐
[Load Flux VAE]   ├─→ [LoraLoader: base style] ─→ [ApplyIPAdapterFlux: per-district + global]
[Load CLIP]       │                                         │
[Load T5-XXL]     ┘                                         ├─→ [KSampler] ─→ [VAE Decode] ─→ [BiRefNet RMBG] ─→ [Save Image]
                                                            │     ↑
                                                            │     │
                                            [Positive prompt]    [(Optional) ControlNet Canny]
                                            [Negative prompt]
```

**Easiest path:** find a published Flux + IPAdapter + LoRA workflow on [OpenArt.ai](https://openart.ai/workflows) or [civitai.com](https://civitai.com/workflows), import it, then modify:
- Set the LoRA dropdown to `flux-mobile-game-isometric-building.safetensors` at strength 0.85
- Set the IPAdapter reference image input to `qtown-refs/ref-01-town-hall.jpg` (you'll swap this per neighborhood)
- Set the BiRefNet node at the end before save
- Save the workflow as `qtown-v2-building.json` in `ComfyUI/workflows/qtown-v2/`

Repeat with tweaks for `qtown-v2-npc.json`, `qtown-v2-prop.json`, `qtown-v2-terrain.json` per `v2-pipeline.md` §§ 4.2-4.4.

**Verify:** load `qtown-v2-building.json`, click Queue Prompt with a placeholder prompt — it should generate one image without errors.

---

## Step 9 — Generate per-sprite prompts

> **Optional — `run_batch.py` generates every prompt in code** from `taxonomy.yaml` + `style-spec.md`
> (`prompt_overhead_building()`, `prompt_overhead_npc()`, `prompt_interior_background()`,
> `prompt_npc_activity()`). Use the manual `.txt` path below only to hand-tune a specific prompt.

**What:** convert the 205 manifest entries from `visual-style-guide.md` § 6 into actual Flux prompts using the templates from § 7.

**Output:** `docs/v2-prompts/<neighborhood>.txt` — one prompt per line, sprite ID as a comment.

Example for `docs/v2-prompts/town-hall.txt`:
```
# town-hall-main
isometric building mobile game style, civic Roman main town hall, 3 stories, classical columns, central clock face, materials: marble and aged bronze, palette: ivory marble + deep blue trim, single light source warm afternoon sun, white background, sticker silhouette, hand-painted soft shadow, no text, 30-degree isometric projection, clean cartoon style consistent with qtown set

# town-hall-clock-tower
isometric building mobile game style, standalone civic bell tower with great clock face, marble masonry, brass clock hands, single light source warm afternoon sun, white background, sticker silhouette, hand-painted soft shadow, no text, 30-degree isometric projection
```

I (Claude) can generate these for you mechanically. Just ask. Otherwise:

**Manually:** open `visual-style-guide.md` § 7 (prompt templates), substitute `{neighborhood_mood}` / `{building_description}` / `{neighborhood_materials}` / `{neighborhood_palette}` / `{tech_accent_if_applicable}` from § 4 + § 2 + § 3 + § 6 for each entry. Tedious but mechanical.

**Verify:** each `<neighborhood>.txt` file has the expected number of lines (Town Hall: 26 entries, Market: 26, etc. per § 6.10).

---

## Step 10 — Run the 5-sprite trial ⭐ (gate decision)

**What:** generate 5 representative sprites end-to-end. **This is the gate that decides whether to continue with the primary base LoRA or fall back.**

Pick one of each:
- 1 building from a "warm" neighborhood (e.g., `tavern-main`)
- 1 building from a "formal" neighborhood (e.g., `town-hall-main`)
- 1 NPC (e.g., `market-npc-trader-01`)
- 1 prop (e.g., `fortress-prop-validation-orb-accept`)
- 1 terrain tile (e.g., `terrain-cobble-road-straight`)

Run them through the workflows with the primary LoRA (`Flux Mobile Game Isometric Building`).

**Quality gate** (all 5 must pass):
- ✅ Silhouette is clearly isometric (30° angle)
- ✅ Reads as "sticker / cartoon / game asset" not "photorealistic 3D render"
- ✅ Background is white (or removable cleanly by BiRefNet)
- ✅ Palette aligns with the neighborhood palette in `visual-style-guide.md` § 2
- ✅ No text artifacts, no watermark, no cropping
- ✅ Mood matches the reference image you fed to IPAdapter

**Decision:**
- All 5 pass → continue to full batch (Phase 2 step 8 in `v2-pipeline.md`)
- 0-1 fail → tweak prompt + sampler settings, retry once
- 2+ fail → switch to fallback LoRA (`Flux-Game-Assets-LoRA-v2`), redo trial
- Both fallbacks fail → trigger the custom-LoRA escape hatch (`v2-pipeline.md` § 3.3)

---

## What you've got after the runbook

After completing all 10 steps, your 3090 Ti has:
- ✅ ComfyUI with Flux + IPAdapter Flux + ControlNet Flux + BiRefNet stack working
- ✅ A base style LoRA from CivitAI loaded and proven on a 5-sprite trial
- ✅ 10 IPAdapter reference images curated
- ✅ `run_batch.py` proven on a 5-sprite trial (it builds the workflow + prompts in code — no hand-saved JSONs or prompt files needed)
- ✅ A green decision gate to proceed to full batch generation

Next: run the full batch — from `asset-gen/`, `python3 run_batch.py --mode production` (fills only the 143 missing sprites, ~6-10h mostly unattended). Then manual review + asset publishing.

---

## Quick-reference download list

If you want a single shopping list to start, here it is. Everything is free / one-time download.

```
Flux base (HF, requires accept agreement):
  flux1-dev.safetensors          → ComfyUI/models/unet/
  ae.safetensors                 → ComfyUI/models/vae/
  clip_l.safetensors             → ComfyUI/models/clip/
  t5xxl_fp8_e4m3fn.safetensors   → ComfyUI/models/clip/

IPAdapter Flux (HF):
  flux-ip-adapter.safetensors    → ComfyUI/models/ipadapter-flux/

ControlNet Flux (HF):
  flux-canny-controlnet-v3.safetensors → ComfyUI/models/controlnet/

Base style LoRA (CivitAI — primary):
  flux-mobile-game-isometric-building.safetensors → ComfyUI/models/loras/

Base style LoRA (HF — fallback):
  Flux-Game-Assets-LoRA-v2.safetensors → ComfyUI/models/loras/

Custom nodes (via ComfyUI-Manager UI):
  ComfyUI-IPAdapter-Flux (XLabs)
  ComfyUI-Advanced-ControlNet
  ComfyUI-RMBG
  rgthree-comfy
  ComfyUI-Custom-Scripts
```

That's everything. Ping me when you're ready to run the trial — happy to help interpret the 5 outputs.
