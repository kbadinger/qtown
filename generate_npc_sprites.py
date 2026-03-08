"""Batch-generate 30 unique NPC sprites via ComfyUI.

Each sprite has a distinct appearance (hair, clothing, gender, style).
Saves to assets/npcs/npc_01.png through npc_30.png.
"""
import asyncio
import io
import json
import os
import random
import sys
from pathlib import Path

import httpx

COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8188")
PROJECT_ROOT = Path(__file__).resolve().parent
WORKFLOW_PATH = PROJECT_ROOT / "asset-gen" / "workflows" / "building_api.json"
NPCS_DIR = PROJECT_ROOT / "assets" / "npcs"
NPC_SIZE = 128
COMFY_TIMEOUT = 180
POLL_INTERVAL = 1.5

# 30 unique character descriptions — diverse appearances
CHARACTERS = [
    "young boy with spiky red hair and green tunic",
    "girl with long blonde braids and blue dress",
    "old man with white beard and brown robes",
    "woman with short black hair and leather armor",
    "boy with brown curly hair and yellow vest",
    "girl with pink pigtails and white apron",
    "muscular man with bald head and blacksmith apron",
    "woman with purple hair and wizard hat",
    "boy with blue cap and overalls",
    "girl with green hair and flower crown",
    "old woman with grey bun and shawl",
    "man with red mohawk and plate armor",
    "woman with long orange hair and merchant clothes",
    "boy with glasses and scholar robes",
    "girl with twin tails and red ribbon",
    "man with eye patch and dark cloak",
    "woman with braided silver hair and shield",
    "boy with straw hat and fishing rod",
    "girl with short brown hair and baker outfit",
    "man with long black hair and samurai outfit",
    "woman with afro and colorful dress",
    "boy with bandana and adventurer gear",
    "girl with beret and paint-stained smock",
    "old man with monocle and top hat",
    "woman with red headband and martial arts gi",
    "boy with wolf ears hood and fur cape",
    "girl with crown and royal dress",
    "man with bushy mustache and chef hat",
    "woman with goggles and engineer overalls",
    "boy with feathered cap and bow",
]

NPC_NEGATIVE = (
    "isometric, platform, ground plate, floor, base, tile, pedestal, "
    "isometric base, green base, wooden platform, "
    "multiple views, turnaround, character sheet, reference sheet, "
    "multiple characters, multiple poses, grid, collage, "
    "realistic, photo, 3d, text, watermark, logo, nsfw, low quality, blurry"
)


def _load_workflow():
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _patch_workflow(flow, prompt_text, negative_text, seed=None):
    flow = json.loads(json.dumps(flow))
    if "client_id" not in flow or not flow["client_id"]:
        flow["client_id"] = "qwen-town-batch"
    nodes = flow["prompt"]
    nodes["3"]["inputs"]["text"] = prompt_text
    nodes["4"]["inputs"]["text"] = negative_text
    if seed is None:
        seed = random.randint(0, 2**53)
    nodes["8"]["inputs"]["noise_seed"] = seed
    return flow


async def _submit_prompt(flow):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{COMFY_URL}/api/prompt", json=flow)
        resp.raise_for_status()
        return resp.json()["prompt_id"]


async def _poll_and_download(prompt_id):
    import time
    deadline = time.time() + COMFY_TIMEOUT
    while time.time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(f"{COMFY_URL}/history/{prompt_id}")
                resp.raise_for_status()
                data = resp.json()
                if prompt_id in data and data[prompt_id].get("outputs"):
                    outputs = data[prompt_id]["outputs"]
                    for node_out in outputs.values():
                        images = node_out.get("images")
                        if not images:
                            continue
                        img = images[0]
                        filename = img["filename"]
                        subfolder = img.get("subfolder", "")
                        img_type = img.get("type", "output")
                        dl_url = f"{COMFY_URL}/view?filename={filename}&type={img_type}"
                        if subfolder:
                            dl_url += f"&subfolder={subfolder}"
                        dl_resp = await client.get(dl_url)
                        dl_resp.raise_for_status()
                        return dl_resp.content
                    return None
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
            print(f"    Poll retry ({e.__class__.__name__})")
        await asyncio.sleep(POLL_INTERVAL)
    return None


def _process_sprite(raw_bytes, target_size):
    from PIL import Image
    from rembg import remove

    cleaned = remove(raw_bytes)
    img = Image.open(io.BytesIO(cleaned)).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    size = max(w, h)
    padded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    padded.paste(img, ((size - w) // 2, size - h))
    padded = padded.resize((target_size, target_size), Image.LANCZOS)
    out = io.BytesIO()
    padded.save(out, format="PNG")
    return out.getvalue()


async def generate_one(index, description):
    sprite_id = f"npc_{index:02d}"
    dest = NPCS_DIR / f"{sprite_id}.png"

    if dest.exists():
        print(f"  [{sprite_id}] Already exists, skipping")
        return sprite_id

    prompt_text = (
        f"zavy-ctsmtrc, cute chibi {description}, 1boy, solo, single character, "
        f"full body, standing, centered, simple solid white background, "
        f"game character sprite, isolated character"
    )

    flow = _load_workflow()
    flow = _patch_workflow(flow, prompt_text, NPC_NEGATIVE)

    print(f"  [{sprite_id}] Generating: {description}...")
    prompt_id = await _submit_prompt(flow)
    raw_bytes = await _poll_and_download(prompt_id)

    if raw_bytes is None:
        print(f"  [{sprite_id}] FAILED — no image returned")
        return None

    processed = _process_sprite(raw_bytes, NPC_SIZE)
    dest.write_bytes(processed)
    print(f"  [{sprite_id}] Saved ({len(processed)} bytes)")
    return sprite_id


async def main():
    # Check ComfyUI health
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{COMFY_URL}/system_stats")
            if resp.status_code != 200:
                print("ComfyUI not responding")
                sys.exit(1)
    except Exception as e:
        print(f"ComfyUI not reachable: {e}")
        sys.exit(1)

    NPCS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating {len(CHARACTERS)} unique NPC sprites...")
    print(f"Output: {NPCS_DIR}/")
    print()

    results = []
    for i, desc in enumerate(CHARACTERS, start=1):
        try:
            result = await generate_one(i, desc)
        except Exception as e:
            print(f"  [npc_{i:02d}] ERROR: {e}")
            result = None
        results.append(result)

    success = sum(1 for r in results if r is not None)
    print(f"\nDone: {success}/{len(CHARACTERS)} sprites generated")


if __name__ == "__main__":
    asyncio.run(main())
