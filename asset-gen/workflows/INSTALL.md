# 3090 Box Setup — Models, LoRAs, ComfyUI Extensions

Run these on the i9 + RTX 3090 box where ComfyUI lives. After this, `python3 ../run_batch.py --mode test --limit 5` should produce 5 sample images.

## 1. ComfyUI base + Manager

You said ComfyUI is already installed on the 3090 box. Confirm Manager is also there — it makes everything else easy:

```sh
cd ~/ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
# restart ComfyUI
```

## 2. Flux base models

Download to `ComfyUI/models/` — split into the right subdirs.

| File | Subdir | Source |
|---|---|---|
| `flux1-dev-fp8.safetensors` (~12GB) | `unet/` | https://huggingface.co/Comfy-Org/flux1-dev/blob/main/flux1-dev-fp8.safetensors |
| `flux1-schnell-fp8.safetensors` (~12GB) | `unet/` | https://huggingface.co/Comfy-Org/flux1-schnell/blob/main/flux1-schnell-fp8.safetensors |
| `t5xxl_fp8_e4m3fn.safetensors` (~5GB) | `clip/` | https://huggingface.co/comfyanonymous/flux_text_encoders/blob/main/t5xxl_fp8_e4m3fn.safetensors |
| `clip_l.safetensors` (~250MB) | `clip/` | https://huggingface.co/comfyanonymous/flux_text_encoders/blob/main/clip_l.safetensors |
| `ae.safetensors` (~330MB) | `vae/` | https://huggingface.co/black-forest-labs/FLUX.1-dev/blob/main/ae.safetensors (gated — login + accept license) |

Use `huggingface-cli download <repo> <file>` or your method of choice.

## 3. ControlNet + IP-Adapter for Flux

| File | Subdir | Source |
|---|---|---|
| `flux_openpose_controlnet.safetensors` | `controlnet/` | https://huggingface.co/XLabs-AI/flux-controlnet-collections (OpenPose) |
| `flux_depth_controlnet.safetensors` | `controlnet/` | https://huggingface.co/XLabs-AI/flux-controlnet-collections (Depth) |
| `flux_ip_adapter_plus.safetensors` | `ipadapter/` (create if missing) | https://huggingface.co/XLabs-AI/flux-ip-adapter |
| `clip_vision_h.safetensors` | `clip_vision/` | https://huggingface.co/h94/IP-Adapter |

Custom node packs needed (via Manager):
- `ComfyUI-Flux-IPAdapter`
- `comfyui_controlnet_aux` (preprocessors)
- `ComfyUI-Impact-Pack` (post-processing — background removal etc.)
- `ComfyUI-rembg` or `ComfyUI-LayerStyle` (background removal for sprites)

## 4. Style LoRAs from Civitai

Browse Civitai with these search terms and pick the highest-rated ones with Flux compatibility:

- "flux solarpunk" — look for a solarpunk/cottagecore-meets-tech LoRA
- "flux studio ghibli" — Ghibli-style LoRA for warmth + character grammar
- "flux 2d character" — front-facing character LoRA (Pokémon-style)
- Optional: "flux holographic" — for the tech-accent layer if you find a good one

Download to `ComfyUI/models/loras/`. **Update `asset-gen/config.yaml`** with the actual filenames you downloaded.

## 5. Smoke test

In ComfyUI UI:
1. Load the default Flux workflow (Manager → Browse Templates → Flux)
2. Set the unet to `flux1-dev-fp8.safetensors`
3. Set positive prompt to: `a cozy solarpunk tavern at golden hour, integrated greenery, terracotta walls, copper holographic signage, studio ghibli inspired, warm atmospheric lighting`
4. Run — should produce a recognizable solarpunk building in ~30s

If that works, ComfyUI is ready. Run the batch driver next.

## 6. Run the batch driver

```sh
cd ~/qtown   # wherever you pulled the repo
cd asset-gen
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# verify ComfyUI is up
curl http://localhost:8188/system_stats

# smoke test — 5 images against schnell
python3 run_batch.py --mode test --limit 5

# check output/
ls -R output/
```

If those 5 look good (right style, right composition), expand:
```sh
# all overhead buildings only
python3 run_batch.py --mode test --only buildings

# everything, schnell-quality (faster QA pass)
python3 run_batch.py --mode test

# everything, dev-quality (production batch — run overnight)
python3 run_batch.py --mode production
```
