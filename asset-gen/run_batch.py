#!/usr/bin/env python3
"""Qtown v2 pre-gen batch driver.

Reads asset-gen/taxonomy.yaml and asset-gen/style-spec.md, constructs
ComfyUI workflows per asset class (overhead building, overhead NPC,
interior background, NPC activity pose), submits them to a ComfyUI HTTP
server, downloads the outputs, and organises them under ./output/.

Designed to run on Kevin's i9 + RTX 3090 box where ComfyUI lives.

Usage
-----
    python3 run_batch.py --mode test --limit 5
    python3 run_batch.py --mode test --only buildings
    python3 run_batch.py --mode production
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

console = Console()
log = logging.getLogger("asset-gen")

ROOT = Path(__file__).resolve().parent
TAXONOMY_PATH = ROOT / "taxonomy.yaml"
CONFIG_PATH = ROOT / "config.yaml"

POLL_INTERVAL = 2.0
MAX_POLL_ATTEMPTS = 240   # ~8 minutes per image — Flux can be slow on first run


# ---------------------------------------------------------------------------
# Style prompt fragments — pulled from style-spec.md so this script is the
# single execution source of truth. Kevin edits style-spec.md for humans;
# changes there must be mirrored here.
# ---------------------------------------------------------------------------

STYLE_SUFFIX_POSITIVE = (
    "solarpunk aesthetic, studio ghibli inspired, hopeful futuristic, "
    "warm golden hour lighting, integrated greenery, soft volumetric atmosphere, "
    "terracotta and sage palette, copper and cyan tech accents, "
    "holographic signage, organic architecture, flowing natural materials, "
    "soft shadows, no harsh edges, no chrome, no concrete"
)

NEGATIVE_PROMPT = (
    "cyberpunk, dystopian, dark, grimdark, neon noir, blade runner, "
    "chrome, concrete, brutalist, harsh geometric, flat displays, screens, "
    "photorealistic, 3d render, blurry, low quality, deformed, multiple characters, "
    "text, watermark, gradient, amateur, sketch, rough, isometric, pixel art, "
    "back view, generic sci-fi"
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class GenJob:
    """One ComfyUI submission."""
    asset_class: Literal["overhead_building", "overhead_npc", "interior_background", "npc_activity"]
    output_subdir: str
    filename_stem: str
    prompt: str
    width: int
    height: int


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def prompt_overhead_building(building: dict) -> str:
    desc = building.get("description", "")
    return (
        f"top-down 3/4 view of a {building['id']} in a hopeful solarpunk town, "
        f"{desc}, integrated greenery, solar panels on roof, "
        f"holographic signage, no characters, empty exterior scene, clean illustration, "
        f"{STYLE_SUFFIX_POSITIVE}"
    )


def prompt_overhead_npc(npc: dict, pose: str = "idle") -> str:
    desc = npc.get("description", "")
    return (
        f"front-facing portrait of a {npc['id']} in solarpunk village, "
        f"{desc}, friendly expression, full body visible, "
        f"plain background, {pose} pose, no other characters, "
        f"{STYLE_SUFFIX_POSITIVE}"
    )


def prompt_interior_background(building: dict, room: dict) -> str:
    return (
        f"side-view interior of a {room['id']} in a solarpunk {building['id']}, "
        f"{room.get('description', '')}, warm wood floors, terracotta walls, "
        f"green plants integrated, holographic signage details, copper accents, "
        f"lanterns and light strips, no characters, empty scene, cozy atmosphere, "
        f"{STYLE_SUFFIX_POSITIVE}"
    )


def prompt_npc_activity(npc: dict, room: dict, activity: str) -> str:
    return (
        f"side-view of a {npc['id']} {activity} in a solarpunk {room['id']}, "
        f"{npc.get('description', '')}, "
        f"full body visible, transparent background, "
        f"warm interior lighting, copper and cyan tech accents, "
        f"{STYLE_SUFFIX_POSITIVE}"
    )


# ---------------------------------------------------------------------------
# Workflow construction (Flux + LoRAs)
# ---------------------------------------------------------------------------

def build_workflow(
    prompt: str,
    negative: str,
    width: int,
    height: int,
    model_cfg: dict,
    loras: list[dict],
) -> dict[str, Any]:
    """Construct a Flux ComfyUI workflow with LoRA stack.

    Numbered-node-id ComfyUI API format. Returns dict suitable for the
    /prompt endpoint's "prompt" key.
    """
    seed = int(uuid.uuid4()) & 0xFFFFFFFF

    wf: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": model_cfg["unet"],
                "weight_dtype": "fp8_e4m3fn",
            },
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": model_cfg["clip_t5"],
                "clip_name2": model_cfg["clip_l"],
                "type": "flux",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": model_cfg["vae"]},
        },
    }

    # Chain LoRA loaders — each one wraps model + clip
    model_ref: list[Any] = ["1", 0]
    clip_ref: list[Any] = ["2", 0]
    next_id = 4
    for lora in loras:
        wf[str(next_id)] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": lora["name"],
                "strength_model": lora.get("strength", 0.8),
                "strength_clip": lora.get("strength", 0.8),
            },
        }
        model_ref = [str(next_id), 0]
        clip_ref = [str(next_id), 1]
        next_id += 1

    pos_clip_id = str(next_id); next_id += 1
    neg_clip_id = str(next_id); next_id += 1
    latent_id = str(next_id); next_id += 1
    sampler_select_id = str(next_id); next_id += 1
    scheduler_id = str(next_id); next_id += 1
    noise_id = str(next_id); next_id += 1
    guider_id = str(next_id); next_id += 1
    sampler_advanced_id = str(next_id); next_id += 1
    vae_decode_id = str(next_id); next_id += 1
    save_image_id = str(next_id); next_id += 1

    wf[pos_clip_id] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": prompt, "clip": clip_ref},
    }
    wf[neg_clip_id] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative, "clip": clip_ref},
    }
    wf[latent_id] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1},
    }
    wf[sampler_select_id] = {
        "class_type": "KSamplerSelect",
        "inputs": {"sampler_name": "euler"},
    }
    wf[scheduler_id] = {
        "class_type": "BasicScheduler",
        "inputs": {
            "model": model_ref,
            "scheduler": "simple",
            "steps": model_cfg.get("steps", 25),
            "denoise": 1.0,
        },
    }
    wf[noise_id] = {
        "class_type": "RandomNoise",
        "inputs": {"noise_seed": seed},
    }
    wf[guider_id] = {
        "class_type": "BasicGuider",
        "inputs": {"model": model_ref, "conditioning": [pos_clip_id, 0]},
    }
    wf[sampler_advanced_id] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": [noise_id, 0],
            "guider": [guider_id, 0],
            "sampler": [sampler_select_id, 0],
            "sigmas": [scheduler_id, 0],
            "latent_image": [latent_id, 0],
        },
    }
    wf[vae_decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": [sampler_advanced_id, 0], "vae": ["3", 0]},
    }
    wf[save_image_id] = {
        "class_type": "SaveImage",
        "inputs": {"images": [vae_decode_id, 0], "filename_prefix": "qtown_v2"},
    }

    return wf


# ---------------------------------------------------------------------------
# ComfyUI HTTP client
# ---------------------------------------------------------------------------

async def submit_workflow(client: httpx.AsyncClient, workflow: dict) -> str:
    response = await client.post("/prompt", json={"prompt": workflow})
    response.raise_for_status()
    return response.json()["prompt_id"]


async def poll_for_result(client: httpx.AsyncClient, prompt_id: str) -> list[dict]:
    for _ in range(MAX_POLL_ATTEMPTS):
        response = await client.get(f"/history/{prompt_id}")
        response.raise_for_status()
        history = response.json()
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI error: {status.get('messages')}")
            images: list[dict] = []
            for node_output in entry.get("outputs", {}).values():
                for img in node_output.get("images", []):
                    images.append(img)
            if images:
                return images
        await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Workflow {prompt_id} did not complete in {MAX_POLL_ATTEMPTS * POLL_INTERVAL:.0f}s")


async def download_image(client: httpx.AsyncClient, image: dict) -> bytes:
    params: dict[str, str] = {"filename": image["filename"], "type": image.get("type", "output")}
    if image.get("subfolder"):
        params["subfolder"] = image["subfolder"]
    response = await client.get("/view", params=params)
    response.raise_for_status()
    return response.content


# ---------------------------------------------------------------------------
# Job planning
# ---------------------------------------------------------------------------

def plan_jobs(taxonomy: dict, dims: dict, only: str | None) -> list[GenJob]:
    """Walk the taxonomy and emit a flat list of generation jobs."""
    jobs: list[GenJob] = []

    if not only or only == "buildings":
        for b in taxonomy.get("buildings", []):
            w, h = dims["overhead_building"]
            jobs.append(GenJob(
                asset_class="overhead_building",
                output_subdir="overhead/buildings",
                filename_stem=b["id"],
                prompt=prompt_overhead_building(b),
                width=w, height=h,
            ))

    if not only or only == "interiors":
        for b in taxonomy.get("buildings", []):
            if b.get("overhead_only"):
                continue
            for r in b.get("rooms", []):
                w, h = dims["interior_background"]
                jobs.append(GenJob(
                    asset_class="interior_background",
                    output_subdir="interior/backgrounds",
                    filename_stem=f"{b['id']}__{r['id']}",
                    prompt=prompt_interior_background(b, r),
                    width=w, height=h,
                ))

    if not only or only == "npcs":
        for npc in taxonomy.get("npcs", []):
            w, h = dims["overhead_npc"]
            jobs.append(GenJob(
                asset_class="overhead_npc",
                output_subdir="overhead/npcs",
                filename_stem=f"{npc['id']}__idle",
                prompt=prompt_overhead_npc(npc, "idle"),
                width=w, height=h,
            ))

    if not only or only == "activities":
        # NPC × activity cross product, scoped to plausible rooms
        # Naive version: pair each NPC's activity_poses with the first
        # room whose activities list contains the matching activity.
        # Better consistency via IP-Adapter is a follow-up.
        for npc in taxonomy.get("npcs", []):
            for pose in npc.get("activity_poses", []):
                room = _find_room_for_activity(taxonomy, pose)
                if room is None:
                    continue
                w, h = dims["npc_activity"]
                jobs.append(GenJob(
                    asset_class="npc_activity",
                    output_subdir="interior/activities",
                    filename_stem=f"{npc['id']}__{pose}",
                    prompt=prompt_npc_activity(npc, room, pose),
                    width=w, height=h,
                ))

    return jobs


def _find_room_for_activity(taxonomy: dict, activity: str) -> dict | None:
    for b in taxonomy.get("buildings", []):
        for r in b.get("rooms", []):
            if activity in r.get("activities", []):
                return r
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> int:
    taxonomy = yaml.safe_load(TAXONOMY_PATH.read_text())
    config = yaml.safe_load(CONFIG_PATH.read_text())

    if not taxonomy.get("locked"):
        console.print("[red]Taxonomy is not locked — set locked: true before running production.[/red]")
        if args.mode == "production":
            return 1

    model_cfg = config["models"][args.mode]
    loras = config.get("loras", [])
    dims = config["dimensions"]
    comfy_url = config["comfyui_url"]

    jobs = plan_jobs(taxonomy, dims, args.only)
    if args.limit:
        jobs = jobs[: args.limit]

    if not jobs:
        console.print("[yellow]No jobs to run for these filters.[/yellow]")
        return 0

    output_root = ROOT / config["output"]["root"]
    output_root.mkdir(exist_ok=True)

    console.print(f"[cyan]Planning[/cyan] {len(jobs)} job(s) against ComfyUI at {comfy_url}, mode={args.mode}")
    failures: list[tuple[GenJob, str]] = []

    async with httpx.AsyncClient(
        base_url=comfy_url,
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=5.0),
    ) as client:
        # Sanity check
        try:
            r = await client.get("/system_stats")
            r.raise_for_status()
        except Exception as e:
            console.print(f"[red]ComfyUI unreachable at {comfy_url}: {e}[/red]")
            return 2

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task_id = progress.add_task("Generating", total=len(jobs))
            for job in jobs:
                target_dir = output_root / job.output_subdir
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / f"{job.filename_stem}.png"

                if target_path.exists() and not args.regen:
                    progress.update(task_id, advance=1, description=f"skip {job.filename_stem}")
                    continue

                workflow = build_workflow(
                    prompt=job.prompt,
                    negative=NEGATIVE_PROMPT,
                    width=job.width,
                    height=job.height,
                    model_cfg=model_cfg,
                    loras=loras,
                )

                try:
                    prompt_id = await submit_workflow(client, workflow)
                    images = await poll_for_result(client, prompt_id)
                    if not images:
                        raise RuntimeError("no images returned")
                    payload = await download_image(client, images[0])
                    target_path.write_bytes(payload)
                    progress.update(task_id, advance=1, description=f"ok   {job.filename_stem}")
                except Exception as e:
                    failures.append((job, str(e)))
                    progress.update(task_id, advance=1, description=f"FAIL {job.filename_stem}")

    console.print(f"\n[green]Done.[/green] {len(jobs) - len(failures)}/{len(jobs)} succeeded.")
    if failures:
        console.print(f"[red]{len(failures)} failure(s):[/red]")
        for job, err in failures:
            console.print(f"  - {job.filename_stem} ({job.asset_class}): {err}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Qtown v2 pre-gen batch driver")
    parser.add_argument("--mode", choices=["test", "production"], default="test",
                        help="test = Flux.1-schnell (fast); production = Flux.1-dev (full quality)")
    parser.add_argument("--limit", type=int, default=None,
                        help="cap total jobs (smoke-test the pipeline)")
    parser.add_argument("--only", choices=["buildings", "interiors", "npcs", "activities"],
                        default=None, help="generate only one asset class")
    parser.add_argument("--regen", action="store_true",
                        help="regenerate even if output file already exists")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
