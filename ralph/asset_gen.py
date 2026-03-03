"""ComfyUI integration for generating building and NPC sprites.

Loads workflow templates from asset-gen/workflows/, patches prompts and seeds,
submits to the ComfyUI API, polls for results, runs rembg background removal,
and saves output images into the assets/ directory tree.

Gracefully degrades if ComfyUI is not running — returns None and logs a warning.
"""

import asyncio
import io
import json
import logging
import os
import random
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8188")

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = PROJECT_ROOT / "asset-gen" / "workflows"
BUILDING_WORKFLOW = WORKFLOW_DIR / "building_api.json"
ASSET_DIR = PROJECT_ROOT / "assets"
BUILDINGS_DIR = ASSET_DIR / "buildings"
NPCS_DIR = ASSET_DIR / "npcs"

COMFY_TIMEOUT = 180  # seconds to wait for generation
POLL_INTERVAL = 1.0  # seconds between history polls

# Target sizes for final sprites
BUILDING_SIZE = 256
NPC_SIZE = 128


# ---------------------------------------------------------------------------
# Workflow loading and patching
# ---------------------------------------------------------------------------


def _load_workflow(path: Path) -> dict:
    """Load and return a deep copy of a ComfyUI API workflow template."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _patch_workflow(
    flow: dict,
    prompt_text: str,
    negative_text: str | None = None,
    seed: int | None = None,
) -> dict:
    """Patch a workflow template with prompt, negative prompt, and seed."""
    flow = json.loads(json.dumps(flow))  # deep copy

    if "client_id" not in flow or not flow["client_id"]:
        flow["client_id"] = "qwen-town"

    nodes = flow["prompt"]

    # Node 3: positive CLIP text prompt
    nodes["3"]["inputs"]["text"] = prompt_text

    # Node 4: negative CLIP text prompt
    if negative_text is not None:
        nodes["4"]["inputs"]["text"] = negative_text

    # Node 8: KSamplerAdvanced seed
    if seed is None:
        seed = random.randint(0, 2**53)
    nodes["8"]["inputs"]["noise_seed"] = seed

    return flow


# ---------------------------------------------------------------------------
# ComfyUI interaction
# ---------------------------------------------------------------------------


async def _submit_prompt(flow: dict) -> str:
    """POST the workflow to ComfyUI and return the prompt_id."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{COMFY_URL}/api/prompt", json=flow)
        resp.raise_for_status()
        return resp.json()["prompt_id"]


async def _poll_and_download(prompt_id: str) -> bytes | None:
    """Poll ComfyUI history until done, then download the image via API.

    Returns raw PNG bytes, or None on failure/timeout.
    """
    deadline = asyncio.get_event_loop().time() + COMFY_TIMEOUT
    async with httpx.AsyncClient(timeout=30) as client:
        while asyncio.get_event_loop().time() < deadline:
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

                    # Download via ComfyUI /view API
                    dl_url = f"{COMFY_URL}/view?filename={filename}&type={img_type}"
                    if subfolder:
                        dl_url += f"&subfolder={subfolder}"

                    dl_resp = await client.get(dl_url)
                    dl_resp.raise_for_status()
                    return dl_resp.content

                logger.warning("ComfyUI outputs contained no images for prompt %s", prompt_id)
                return None

            await asyncio.sleep(POLL_INTERVAL)

    logger.warning("ComfyUI timed out waiting for prompt %s", prompt_id)
    return None


async def _is_comfy_running() -> bool:
    """Quick health check — can we reach ComfyUI?"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{COMFY_URL}/system_stats")
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        return False


# ---------------------------------------------------------------------------
# Image post-processing
# ---------------------------------------------------------------------------


def _process_sprite(raw_bytes: bytes, target_size: int) -> bytes:
    """Remove background with rembg, trim, pad to square, resize.

    Returns processed PNG bytes.
    """
    from PIL import Image
    from rembg import remove

    # rembg background removal
    cleaned = remove(raw_bytes)
    img = Image.open(io.BytesIO(cleaned)).convert("RGBA")

    # Trim transparent padding
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Pad to square (bottom-center align so sprite stands at bottom)
    w, h = img.size
    size = max(w, h)
    padded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    padded.paste(img, ((size - w) // 2, size - h))

    # Resize to target
    padded = padded.resize((target_size, target_size), Image.LANCZOS)

    out = io.BytesIO()
    padded.save(out, format="PNG")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

BUILDING_POSITIVE = (
    "zavy-ctsmtrc, isometric, cute isometric {type} building, "
    "white background, game asset, cartoon style"
)
BUILDING_NEGATIVE = (
    "realistic, photo, 3d, text, watermark, logo, nsfw, low quality, blurry, "
    "multiple, grid, collage"
)

NPC_POSITIVE = (
    "zavy-ctsmtrc, cute chibi {role}, 1boy, solo, single character, "
    "full body, standing, centered, simple solid white background, "
    "game character sprite, isolated character"
)
NPC_NEGATIVE = (
    "isometric, platform, ground plate, floor, base, tile, pedestal, "
    "isometric base, green base, wooden platform, "
    "multiple views, turnaround, character sheet, reference sheet, "
    "multiple characters, multiple poses, grid, collage, "
    "realistic, photo, 3d, text, watermark, logo, nsfw, low quality, blurry"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_building_sprite(building_type: str) -> str | None:
    """Generate an isometric building sprite via ComfyUI.

    Returns the destination path (str) under assets/buildings/ on success,
    or None if ComfyUI is unavailable or generation failed.
    """
    if not await _is_comfy_running():
        logger.warning("ComfyUI is not running — skipping building sprite for '%s'", building_type)
        return None

    prompt_text = BUILDING_POSITIVE.format(type=building_type)

    try:
        flow = _load_workflow(BUILDING_WORKFLOW)
        flow = _patch_workflow(flow, prompt_text, BUILDING_NEGATIVE)
        prompt_id = await _submit_prompt(flow)
        logger.info("ComfyUI building prompt queued: %s (prompt_id=%s)", building_type, prompt_id)

        raw_bytes = await _poll_and_download(prompt_id)
        if raw_bytes is None:
            logger.warning("Building sprite generation failed for '%s'", building_type)
            return None

        # Post-process: rembg + resize
        processed = _process_sprite(raw_bytes, BUILDING_SIZE)

        BUILDINGS_DIR.mkdir(parents=True, exist_ok=True)
        dest = BUILDINGS_DIR / f"{building_type}.png"
        dest.write_bytes(processed)
        logger.info("Building sprite saved: %s", dest)
        return str(dest)

    except Exception:
        logger.exception("Error generating building sprite for '%s'", building_type)
        return None


async def generate_npc_sprite(role: str) -> str | None:
    """Generate a chibi NPC sprite via ComfyUI.

    Generates a standalone character (no isometric base/ground plate),
    removes background with rembg, and saves as a clean transparent PNG.

    Returns the destination path (str) under assets/npcs/ on success,
    or None if ComfyUI is unavailable or generation failed.
    """
    if not await _is_comfy_running():
        logger.warning("ComfyUI is not running — skipping NPC sprite for '%s'", role)
        return None

    prompt_text = NPC_POSITIVE.format(role=role)

    try:
        flow = _load_workflow(BUILDING_WORKFLOW)
        flow = _patch_workflow(flow, prompt_text, NPC_NEGATIVE)
        prompt_id = await _submit_prompt(flow)
        logger.info("ComfyUI NPC prompt queued: %s (prompt_id=%s)", role, prompt_id)

        raw_bytes = await _poll_and_download(prompt_id)
        if raw_bytes is None:
            logger.warning("NPC sprite generation failed for '%s'", role)
            return None

        # Post-process: rembg + resize
        processed = _process_sprite(raw_bytes, NPC_SIZE)

        NPCS_DIR.mkdir(parents=True, exist_ok=True)
        dest = NPCS_DIR / f"{role}.png"
        dest.write_bytes(processed)
        logger.info("NPC sprite saved: %s", dest)
        return str(dest)

    except Exception:
        logger.exception("Error generating NPC sprite for '%s'", role)
        return None


async def ensure_default_assets():
    """Check the database for all building types and NPC roles,
    then generate sprites for any that are missing on disk.

    This is designed to be called after Ralph completes building-type stories.
    It degrades gracefully if the models haven't been created yet or if
    ComfyUI isn't running.
    """
    if not await _is_comfy_running():
        logger.warning("ComfyUI is not running — skipping asset generation")
        return

    # Import DB models lazily to avoid circular imports
    try:
        from engine.db import SessionLocal
    except ImportError:
        logger.warning("Cannot import engine.db — skipping ensure_default_assets")
        return

    db = SessionLocal()
    try:
        # Gather building types
        building_types = set()
        try:
            from engine.models import Building
            buildings = db.query(Building).all()
            for b in buildings:
                bt = getattr(b, "building_type", None) or getattr(b, "type", None)
                if bt:
                    building_types.add(bt.lower())
        except Exception:
            logger.info("Building model not available yet — using defaults")
            building_types = {"civic", "market", "residential", "tavern", "smithy"}

        # Gather NPC roles
        npc_roles = set()
        try:
            from engine.models import NPC
            npcs = db.query(NPC).all()
            for n in npcs:
                role = getattr(n, "role", None)
                if role:
                    npc_roles.add(role.lower())
        except Exception:
            logger.info("NPC model not available yet — using defaults")
            npc_roles = {"villager", "merchant", "guard", "farmer", "blacksmith"}

    finally:
        db.close()

    # Generate missing building sprites
    BUILDINGS_DIR.mkdir(parents=True, exist_ok=True)
    for bt in sorted(building_types):
        dest = BUILDINGS_DIR / f"{bt}.png"
        if not dest.exists():
            logger.info("Generating missing building sprite: %s", bt)
            await generate_building_sprite(bt)

    # Generate missing NPC sprites
    NPCS_DIR.mkdir(parents=True, exist_ok=True)
    for role in sorted(npc_roles):
        dest = NPCS_DIR / f"{role}.png"
        if not dest.exists():
            logger.info("Generating missing NPC sprite: %s", role)
            await generate_npc_sprite(role)

    logger.info("Asset generation sweep complete")
