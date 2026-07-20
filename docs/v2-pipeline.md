# Qtown v2 — Sprite Generation Pipeline

**Status:** Draft 1 · 2026-05-06
**Companions:** [`v2-spec.md`](./v2-spec.md) · [`visual-style-guide.md`](./visual-style-guide.md)

This is the recipe for the day-2 generation session. It assumes the visual style guide manifest (§ 6 of `visual-style-guide.md`) is signed off and the reference images for IPAdapter / LoRA training are curated.

---

## 1 · Hardware target

| Resource | Spec |
|---|---|
| GPU | NVIDIA RTX 3090 Ti, 24GB VRAM |
| System RAM | 32GB+ recommended (Flux loading + LoRA training is memory-hungry) |
| Disk | ~80GB free for model checkpoints (Flux base ~24GB + IPAdapter + ControlNet + BiRefNet + 3 trained LoRAs + working dir) |
| OS | Windows 11 Pro (existing) |

**Important during the session:** stop the Ollama service (`ollama stop` or kill the process). Flux + LoRA training will use the full 24GB of the 3090 Ti and will OOM if Ollama is also resident. Restart Ollama after the session completes (Ralph and Qwen go back to using the 3090 Ti).

---

## 2 · Software stack

### 2.1 Core install
- **ComfyUI** — latest release. If existing install is from v1 era, update via `git pull` + `pip install -r requirements.txt --upgrade`.
- **Flux.1 [dev]** base model — download from [black-forest-labs/FLUX.1-dev](https://huggingface.co/black-forest-labs/FLUX.1-dev). Place in `ComfyUI/models/unet/`.
- **Flux VAE** — `ae.safetensors` from the same repo. Place in `ComfyUI/models/vae/`.
- **Flux text encoders** — `clip_l.safetensors` + `t5xxl_fp8_e4m3fn.safetensors` (FP8 variant — fits on 24GB). Place in `ComfyUI/models/clip/`.

### 2.2 Custom nodes (install via ComfyUI-Manager)
- **ComfyUI-IPAdapter-Flux** (XLabs or InstantX implementation; pick whichever has the most recent commit at session start)
- **ComfyUI-Advanced-ControlNet** (for Flux ControlNet support)
- **ControlNet Canny + Depth for Flux** — model files from `XLabs-AI/flux-controlnet-collections`
- **ComfyUI-RMBG** (for BiRefNet background removal)
- **ComfyUI-Custom-Scripts** (quality-of-life: workflow auto-save, batch queue improvements)
- **rgthree-comfy** (better workflow management for batch runs)

### 2.3 LoRA training stack
- **Kohya SS GUI** — latest release. Train Flux LoRAs in this rather than a generic trainer; Kohya has Flux-specific configs.
- **LoRA+ mode** — enable in Kohya for faster convergence (16× learning rate optimization for the LoRA-A matrices). Reduces per-LoRA training time from ~3h to ~1.5-2h on the 3090 Ti.
- **FP8 quantization** — enable in Kohya for memory headroom during training.

### 2.4 Optional but recommended
- **Tensor RT for Flux** — 30-50% inference speedup if you're willing to sink an hour into setup. Marginal value for a one-time batch; skip if time-pressed.

---

## 3 · Style strategy

Per the v1 → v2 jump: v1 used `zavy-ctsmtrc` (SDXL) as its base style LoRA. **`zavy-ctsmtrc` has no Flux port.** v2 needs an equivalent base style LoRA from CivitAI/HuggingFace, plus per-neighborhood IPAdapter references for architectural variation. **No custom LoRA training in the happy path** — IPAdapter handles district variation. Custom training is an escape hatch only if the chosen base LoRA fails the trial.

### 3.1 Base style LoRA selection

Three Flux candidates, ranked. Test the top one first via the trial run (§ 5.1, step 7); fall back to #2 or #3 if quality is insufficient.

| Rank | LoRA | Source | Trigger | Strength | Why |
|---|---|---|---|---|---|
| **1** | **Flux Mobile Game Isometric Building** by orest_weise | [CivitAI 1901291](https://civitai.com/models/1901291/flux-mobile-game-isometric-building) | `isometric building mobile game style` | 0.8-0.9 | Closest to v1's `zavy-ctsmtrc` intent — explicit mobile-game asset training, white-background guarantee, matches "sticker silhouette" target |
| 2 | **Flux-Game-Assets-LoRA-v2** by gokaygokay | [HF gokaygokay/Flux-Game-Assets-LoRA-v2](https://huggingface.co/gokaygokay/Flux-Game-Assets-LoRA-v2) | `wbgmsst, [description], white background` | 0.7 | Production-proven (used by FAL Fast LoRA Trainer), explicit white-bg, 3D isometric assets — falls back here if #1 underdelivers cartoon feel |
| 3 | **Isometrica v1** by jurdn | [CivitAI 720442](https://civitai.com/models/720442/isometrica) | `isometric` | 0.4-0.75 | High downloads + ratings (3.6K likes), flexible architecture; output leans 3D-rendered over cartoon — use only if #1 and #2 both fail the trial |

**Settings (for #1):** Euler sampler, CFG 3.5, 20-40 steps, distilled-model-optimized.

### 3.2 Per-neighborhood IPAdapter references

Per-district architectural variation (Town Hall vs Fortress vs Market) is achieved by **swapping the IPAdapter v2 reference image per neighborhood**, not by stacking additional style LoRAs. This avoids the well-known multi-LoRA blending problem on Flux (3+ stacked LoRAs produce muddied output; community consensus is max 2 at 0.5 strength each — see [HF discussion](https://discuss.huggingface.co/t/trying-to-run-multiple-loras-on-flux-1-dev/106813)).

For each of the 9 neighborhoods, curate **one IPAdapter reference image** that captures the architectural mood:

| Neighborhood | Reference target |
|---|---|
| Town Hall | Civic Roman/Florentine palazzo, marble columns |
| Market District | Marrakech souk / Camden Market with copper awnings |
| The Fortress | Edinburgh Castle keep with brass gate accents |
| The Academy | Bodleian Library + Tesla's lab fusion |
| The Tavern | Renaissance inn with hearth glow |
| The Library | Trinity College Long Room |
| Cartographer's Guild | Royal Cartographic Society / Doge's map room |
| Artisan's Workshop | Medieval guild hall + Aardman workshop |
| Roads + countryside | Roman road with milestones, pilgrim's way |

Plus one **global "qtown set" reference** applied at lower strength (~0.3) across the entire batch to pull stylistic outliers back toward consistency.

**IPAdapter v2 setup for Flux:** install `flux-ip-adapter.safetensors` (XLabs) + `google/siglip-so400m-patch14-384` vision encoder. Apply LoRA to UNet first, then IPAdapter on the LoRA-modified model output. See [XLabs tutorial](https://www.youtube.com/watch?v=KvrRlVFZjVo).

### 3.3 Escape hatch — custom Flux LoRA training

Only triggered if the trial run (§ 5.1, step 7) shows the candidate base LoRAs cannot produce acceptable cartoon-sticker isometric output. In that case, train one Flux LoRA from scratch using v1's existing 76 SDXL sprites at `/v1/assets/` as the dataset (with manual cartoon adjustments where needed).

**Kohya SS GUI config (single Flux LoRA, only if needed):**
- Base: Flux.1 [dev]
- Network module: LoRA, dim 32, alpha 16
- Learning rate: 1e-4 with LoRA+ enabled
- Batch size: 1 (Flux memory headroom on 24GB)
- Resolution: 1024
- Epochs: 10-15, save every 2 epochs, pick best
- Training data: 25-50 reference sprites with descriptive captions (BLIP auto-caption + manual refinement)
- Time estimate: ~6-8h on 3090 Ti
- Output size: ~18-37 MB

**Acceptance test for custom LoRA:** 16-image grid comparing custom-LoRA at strength 0.7 vs candidate-LoRA-#1 at 0.8. Pick whichever produces cleaner cartoon-sticker silhouettes with white bg.

**Likelihood we hit this escape hatch:** moderate. Candidate #1 is the closest match for the v1 aesthetic but is newer / less proven. Budget the extra 6-8h in case.

---

## 4 · Workflow definition (ComfyUI)

Three workflows — one per sprite type. Save as JSON in `ComfyUI/workflows/qtown-v2/`.

### 4.1 `qtown-v2-building.json` — building generator
**Nodes:**
1. Load Flux UNet (FP8 if memory-constrained, FP16 otherwise)
2. Load Flux VAE
3. Load CLIP-L + T5-XXL (FP8 e4m3fn)
4. Load **base style LoRA** (from § 3.1 selection — Flux Mobile Game Isometric Building at strength 0.8-0.9 in the happy path)
5. IPAdapter v2 — load **per-neighborhood reference image** (strength 0.7) + **global "qtown set" reference** (strength 0.3 layered)
6. Load per-building Canny silhouette guide (strength 0.5) — optional, used for the larger buildings to lock isometric angle
7. Positive prompt: from `docs/v2-prompts/<neighborhood>.txt` (per-sprite line, includes the LoRA's trigger phrase)
8. Negative prompt: from `visual-style-guide.md` § 7.5
9. KSampler: 25 steps, Euler, sgm_uniform scheduler, CFG 3.5
10. VAE Decode
11. BiRefNet RMBG node (post-process)
12. Save image to `<output_root>/<neighborhood>/buildings/<sprite_id>.png`

### 4.2 `qtown-v2-npc.json` — NPC generator
Same as building, except:
- Base style LoRA: same as buildings (one LoRA for the entire batch)
- IPAdapter reference: per-neighborhood reference at strength 0.5 (slightly lower so NPCs don't read as buildings) + global "qtown set" at 0.3
- ControlNet: skip (NPCs don't need composition lock)
- Resolution: 512×512 (NPC canvas)
- KSampler: 22 steps (NPCs converge faster)

### 4.3 `qtown-v2-prop.json` — prop generator
Same as NPC (smaller canvas, no ControlNet), with:
- Base style LoRA: same as buildings/NPCs
- IPAdapter strength: per-neighborhood 0.4, global 0.3 (props are smaller, less style critical)
- KSampler: 20 steps

### 4.4 `qtown-v2-terrain.json` — terrain tile generator
Different from buildings/NPCs/props because terrain is tileable:
- No IPAdapter (terrain doesn't need to match the character/building style)
- Canvas: 256×128 with seamless edge prompt instructions
- Use Flux's seamless-tile prompt tricks: "seamless tile, edges blend perfectly, no border"
- Manual review for tileability is mandatory (BiRefNet not relevant; terrain is opaque)

---

## 5 · Batch generation plan

### 5.1 Order of operations
1. **Setup** (~3-4h):
   - Stop Ollama (frees the 3090 Ti for Flux)
   - Install/update ComfyUI + custom nodes (§ 2.2)
   - Download Flux base + VAE + encoders + IPAdapter Flux + ControlNet Flux + BiRefNet (§ 2.1)
2. **LoRA selection** (~30 min):
   - Download candidate base style LoRA #1 (Flux Mobile Game Isometric Building) and #2 (Flux-Game-Assets-LoRA-v2) from § 3.1
3. **IPAdapter reference curation** (~1h):
   - Curate 10 reference images (9 per-neighborhood + 1 global) per § 3.2 mapping
   - Place in `ComfyUI/input/qtown-refs/`
4. **Prompt generation** (~1h):
   - Substitute manifest entries from `visual-style-guide.md` § 6 into prompt patterns from § 7
   - Output: `docs/v2-prompts/<neighborhood>.txt` (one prompt per line, sprite ID in a comment, includes the base LoRA trigger phrase)
5. **Workflow build** (~2h):
   - Build the 4 ComfyUI workflows from § 4 (`qtown-v2-building.json`, `qtown-v2-npc.json`, `qtown-v2-prop.json`, `qtown-v2-terrain.json`)
   - Save to `ComfyUI/workflows/qtown-v2/`
6. **5-sprite trial** (~1h):
   - Generate 5 sprites end-to-end using base LoRA #1 (one building, one NPC, one prop, one terrain, one tech-signature prop)
   - Quality check against mood boards
   - **Decision gate:** if quality acceptable → continue to step 8 with LoRA #1
   - If poor: try LoRA #2, retest. If still poor: trigger § 3.3 escape hatch (custom Flux LoRA training, +6-8h)
7. **(Optional) Custom LoRA training** (~6-8h, only if step 6 failed):
   - Per § 3.3 — train one Flux LoRA on v1 sprite dataset
   - Re-test 5-sprite trial with the custom LoRA
8. **Batch generation** (~6-10h, mostly unattended):
   - Queue all prompts in ComfyUI's batch queue (rgthree-comfy makes this clean)
   - Run building workflow → 97 sprites × ~30-40s each = ~50-70 min
   - Run NPC workflow → 48 sprites × ~25s each = ~20 min
   - Run prop workflow → 51 sprites × ~20s each = ~17 min
   - Run terrain workflow → 9 tiles × ~30s = ~5 min
   - Retries for the ~10-15% that fail first-pass: ~4-6h additional
   - **Wall time estimate:** ~6-10h of unattended batch + manual restarts on OOM crashes
9. **Manual review** (~4-6h):
   - Visual side-by-side check against mood boards
   - Regenerate outliers (target: ~30 sprites need re-runs)
   - Per-sprite quality gate: silhouette is correct, palette matches, no text bleed, BiRefNet alpha is clean
10. **Asset publishing** (~30 min):
    - Copy curated final sprites into `dashboard/public/sprites/<neighborhood>/{buildings,npcs,props,terrain}/`
    - Generate `manifest.json` from filesystem walk
    - Bump `ASSET_VERSION=v22` in `dashboard/composables/useSpriteTextures.ts`
    - Git commit: `Phase 2: deliver 205 fresh sprites for v2 visual identity`
11. **Shutdown:**
    - Stop ComfyUI
    - Restart Ollama
    - 3090 Ti returns to Ralph/Qwen duty

### 5.2 Total time estimate
- **Happy path** (CivitAI base LoRA passes trial):
  - Setup + LoRA download + IPAdapter prep + prompts + workflow build: ~7-8h human
  - Trial: ~1h
  - Batch generation: ~6-10h compute (mostly unattended, overnight viable)
  - Manual review + retries: ~4-6h human
  - **Total wall clock: ~1 day** (most compute overnight)
- **Escape hatch path** (must train custom LoRA):
  - Add ~6-8h compute for LoRA training + ~1h re-trial
  - **Total wall clock: ~1.5-2 days**

---

## 6 · BiRefNet configuration

BiRefNet replaces v1's rembg pipeline. Quality gain: ~94% edge accuracy vs ~81% on hair/cloth (per the published benchmarks).

### 6.1 Setup
- Model: BiRefNet via `ComfyUI-RMBG` node, model variant: `BiRefNet-portrait` for NPCs, `BiRefNet-general` for buildings/props
- Threshold: 0.5 (default)
- Post-process: Gaussian blur radius 1px on alpha edge to soften (prevents jagged sticker edges)

### 6.2 Per-sprite-type config
- **Buildings:** `BiRefNet-general`, threshold 0.5, no edge blur (sharp silhouette desired)
- **NPCs:** `BiRefNet-portrait`, threshold 0.5, edge blur 1px
- **Props:** `BiRefNet-general`, threshold 0.5, edge blur 1px
- **Terrain:** SKIP — tiles are opaque, no alpha needed

### 6.3 Quality gate
After BiRefNet, sample 10 sprites at random and check:
- No background bleed visible at edges
- No haloing around hair / detailed silhouettes
- Alpha smooth at hard edges (with the 1px blur applied)

If any fail: investigate threshold or try `BiRefNet-DIS5K-TR` for more aggressive edge detection.

---

## 7 · Output organization

```
dashboard/public/sprites/
├── town-hall/
│   ├── buildings/   (15 PNGs)
│   ├── npcs/        (7 PNGs)
│   └── props/       (4 PNGs)
├── market/
│   ├── buildings/   (14 PNGs)
│   ├── npcs/        (6 PNGs)
│   └── props/       (6 PNGs)
├── fortress/
│   └── ...
├── academy/
├── tavern/
├── library/
├── cartographer/
├── artisan/
├── roads/
│   ├── buildings/   (4 PNGs)
│   ├── npcs/        (3 PNGs)
│   ├── props/       (8 PNGs)
│   └── terrain/     (9 PNGs)
└── manifest.json    (machine-readable manifest with all sprite IDs + paths)
```

Renderer reads `manifest.json` at boot to discover sprites; missing files trigger procedural fallback (preserves graceful degradation).

---

## 8 · Failure modes + mitigations

| Failure | Mitigation |
|---|---|
| LoRA overfits to specific reference building | Reduce epochs, increase regularization, curate references more aggressively |
| Flux OOM during batch | Switch UNet to FP8, reduce concurrent batch to 1, kill any background services |
| BiRefNet leaves halo on hair | Increase threshold to 0.6, switch to `BiRefNet-portrait` variant for the affected sprite type |
| Style drift across batch (sprite N looks different from sprite 1) | Verify IPAdapter is loaded for every prompt; try IPAdapter strength up to 0.8; reset and re-run problematic batch |
| Prompts produce text artifacts | Strengthen negative prompt for "text, watermark, signature"; reduce CFG to 3.0 |
| Multi-day session due to GPU instability | Save partial state; can resume — workflow JSON is deterministic; rerun only missing IDs |
| ComfyUI custom node breaking on update | Pin custom-node versions in `ComfyUI/custom_nodes/<node>/.git` HEAD before session start |

---

## 9 · Acceptance for Phase 1c

This doc is "done" when:
- The hardware target is unambiguous (§ 1) — **DONE**
- Software stack + custom nodes are listed with sources (§ 2) — **DONE**
- LoRA training plan is concrete: which LoRAs, training data sourcing, Kohya config, acceptance test (§ 3) — **DONE**
- Workflow definitions describe the four workflow types unambiguously (§ 4) — **DONE**
- Batch generation plan has a realistic time estimate and order of operations (§ 5) — **DONE**
- BiRefNet config is specific per sprite type (§ 6) — **DONE**
- Output organization matches what the renderer expects (§ 7) — **DONE**
- Failure modes are anticipated with mitigations (§ 8) — **DONE**
- User has tested ComfyUI + Flux + IPAdapter + ControlNet + BiRefNet running together on the 3090 Ti before signing off — pending Phase 2 setup

**Open items for Phase 2 setup:**
- Curate IPAdapter reference images (10 total — one per neighborhood + one global "qtown set")
- Download candidate base style LoRA(s) from § 3.1 (Flux Mobile Game Isometric Building primary; Flux-Game-Assets-LoRA-v2 fallback)
- Generate per-sprite full prompts into `docs/v2-prompts/<neighborhood>.txt`
- Run the 5-sprite trial (§ 5.1, step 6) — if it fails, source ~25-50 reference sprites for the custom-LoRA escape hatch (§ 3.3)
