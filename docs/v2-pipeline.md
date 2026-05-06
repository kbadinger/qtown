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

## 3 · LoRA training plan

Three architectural-style LoRAs cover all 9 neighborhoods with appropriate cross-bleed:

| LoRA | Covers | Reference set | Training time |
|---|---|---|---|
| `qtown-civic-formal` | Town Hall, Cartographer's Guild, Library | 50-60 images: civic Roman/Florentine, marble palaces, Long Room library, Royal Cartographic Society interiors | ~1.5-2h on 3090 Ti |
| `qtown-militant-industrial` | The Fortress, Artisan's Workshop | 50-60 images: stone keeps, brass-fitted gates, medieval guild halls, steampunk forges, Aardman-style workshop interiors | ~1.5-2h |
| `qtown-warm-organic` | The Tavern, Market District, The Academy (partial), Roads | 50-60 images: Renaissance inns, Camden Market stalls, Bodleian Library cozy reading rooms, Roman roads with milestones | ~1.5-2h |

**The Academy** uses `qtown-warm-organic` as a base with `qtown-civic-formal` blended at 0.4 strength for the more formal lecture hall + Tesla coil tower. **Roads + countryside** uses `qtown-warm-organic` only.

### 3.1 Training data sourcing
- All references must be public-domain or CC-licensed (or owned by you)
- Curate ~50-60 high-quality images per LoRA (1024×1024 or upscale-able)
- Caption each image with descriptive tags — Kohya generates auto-captions via BLIP, then refine by hand for accuracy
- Avoid mixing styles within a single LoRA's training set (causes drift)

### 3.2 Kohya config (per LoRA)
- Base: Flux.1 [dev]
- Network module: LoRA
- Network dim: 32 (good balance of expressiveness vs file size for a Flux style LoRA)
- Network alpha: 16
- Learning rate: 1e-4 with LoRA+ enabled
- Batch size: 1 (Flux is memory-heavy; bigger batches OOM on 24GB)
- Resolution: 1024
- Epochs: 10-15
- Save checkpoints every 2 epochs to compare; pick the best one (usually epoch 8-12)

### 3.3 LoRA acceptance test
After each LoRA trains, run a 16-image grid comparing the LoRA at strength 0.7 vs base Flux. Acceptance: the LoRA visibly imparts the architectural style without overfitting (no specific buildings appear verbatim from training data).

---

## 4 · Workflow definition (ComfyUI)

Three workflows — one per sprite type. Save as JSON in `ComfyUI/workflows/qtown-v2/`.

### 4.1 `qtown-v2-building.json` — building generator
**Nodes:**
1. Load Flux UNet (FP8 if memory-constrained, FP16 otherwise)
2. Load Flux VAE
3. Load CLIP-L + T5-XXL (FP8 e4m3fn)
4. Load architectural-style LoRA (selected per-neighborhood; strength 0.7)
5. Load global "qtown set" IPAdapter reference image (strength 0.7)
6. Load per-building Canny silhouette guide (strength 0.5) — optional, used for the larger buildings to lock isometric angle
7. Positive prompt: from `docs/v2-prompts/<neighborhood>.txt` (per-sprite line)
8. Negative prompt: from `visual-style-guide.md` § 7.5
9. KSampler: 25 steps, dpmpp_2m_sde, sgm_uniform scheduler, CFG 3.5
10. VAE Decode
11. BiRefNet RMBG node (post-process)
12. Save image to `<output_root>/<neighborhood>/buildings/<sprite_id>.png`

### 4.2 `qtown-v2-npc.json` — NPC generator
Same as building, except:
- LoRA selection per neighborhood (same mapping as buildings)
- IPAdapter reference: the global "qtown set" reference at strength 0.6 (slightly lower so NPCs don't blend into buildings)
- ControlNet: skip (NPCs don't need composition lock)
- Resolution: 512×512 (NPC canvas)
- KSampler: 22 steps (NPCs converge faster)

### 4.3 `qtown-v2-prop.json` — prop generator
Same as NPC (smaller canvas, no ControlNet), with:
- IPAdapter strength 0.5 (props are smaller, less style critical)
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
1. **Setup day** (~4-6h):
   - Install ComfyUI updates + custom nodes
   - Download Flux base + VAE + encoders + IPAdapter Flux + ControlNet Flux + BiRefNet
   - Curate IPAdapter reference images (10: one per neighborhood + global)
   - Curate LoRA training data (~150-180 images across 3 LoRAs)
2. **LoRA training night** (~6h, parallel — start one, do other prep, kick off next):
   - Train `qtown-civic-formal`
   - Train `qtown-militant-industrial`
   - Train `qtown-warm-organic`
3. **Prompt generation** (~1h):
   - Substitute manifest entries into prompt patterns from `visual-style-guide.md` § 7
   - Output: `docs/v2-prompts/<neighborhood>.txt` (one prompt per line, sprite ID in a comment)
4. **Batch generation** (~12-18h, mostly unattended):
   - Queue all prompts in ComfyUI's batch queue (rgthree-comfy makes this clean)
   - Run building workflow → 97 sprites × ~30-40s each = ~50-70 min
   - Run NPC workflow → 48 sprites × ~25s each = ~20 min
   - Run prop workflow → 51 sprites × ~20s each = ~17 min
   - Run terrain workflow → 9 tiles × ~30s = ~5 min
   - Variants + retries for the ~10-15% that fail first-pass: ~4-6h additional
   - **Wall time estimate:** ~6-10h of unattended batch + manual restarts on OOM crashes
5. **Manual review** (~4-6h):
   - Visual side-by-side check against mood boards
   - Regenerate outliers (target: ~30 sprites need re-runs)
   - Per-sprite quality gate: silhouette is correct, palette matches, no text bleed, BiRefNet alpha is clean
6. **Asset publishing** (~30 min):
   - Copy curated final sprites into `dashboard/public/sprites/<neighborhood>/{buildings,npcs,props,terrain}/`
   - Bump `ASSET_VERSION=v22` in `dashboard/composables/useSpriteTextures.ts`
   - Git commit with the sprite manifest count: `Phase 2: deliver 205 fresh sprites for v2 visual identity`
7. **Shutdown:**
   - Stop ComfyUI
   - Restart Ollama
   - 3090 Ti returns to Ralph/Qwen duty

### 5.2 Total time estimate
- Setup + LoRA prep: ~4-6h human time
- LoRA training: ~6h compute (overlaps with setup)
- Prompt generation: ~1h human
- Batch generation: ~6-10h compute (mostly unattended, overnight viable)
- Manual review + retries: ~4-6h human
- **Total wall clock:** 1.5-2 days, with most compute overnight

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
- Curate IPAdapter reference images (10 total)
- Source LoRA training data (~150-180 images)
- Generate per-sprite full prompts into `docs/v2-prompts/<neighborhood>.txt`
- Run a 5-sprite trial batch end-to-end before committing to the full ~205-sprite run
