import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

# ---------- CONFIG ----------

COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8188")
BASE_DIR = os.path.dirname(__file__)
API_WORKFLOW_PATH = os.path.join(BASE_DIR, "workflows", "building_api.json")

# ../assets
ASSET_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "assets"))

# ../ComfyUI/output  (adjust if your ComfyUI path is different)
COMFY_OUTPUT_DIR = os.getenv("COMFY_OUTPUT_DIR", str(Path.home() / "ComfyUI" / "output"))

app = FastAPI()


class AssetRequest(BaseModel):
    prompt: str
    seed: int | None = None
    width: int | None = None
    height: int | None = None


# ---------- WORKFLOW HELPERS ----------

def load_api_workflow() -> dict:
    with open(API_WORKFLOW_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def patch_api_workflow(flow: dict, req: AssetRequest) -> dict:
    # deep copy so we don't mutate the base template
    flow = json.loads(json.dumps(flow))

    # Make sure we have a client_id
    if "client_id" not in flow or not flow["client_id"]:
        flow["client_id"] = "qwen-town"

    prompt_nodes = flow["prompt"]

    # node "3": positive CLIPTextEncode (text prompt)
    node3 = prompt_nodes["3"]
    node3["inputs"]["text"] = req.prompt

    # node "9": EmptyLatentImage (width/height)
    if req.width is not None or req.height is not None:
        node9 = prompt_nodes["9"]
        if req.width is not None:
            node9["inputs"]["width"] = req.width
        if req.height is not None:
            node9["inputs"]["height"] = req.height

    # node "8": KSamplerAdvanced (seed)
    if req.seed is not None:
        node8 = prompt_nodes["8"]
        node8["inputs"]["noise_seed"] = req.seed

    return flow
async def wait_for_result(prompt_id: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        while True:
            r = await client.get(f"{COMFY_URL}/history/{prompt_id}")
            r.raise_for_status()
            data = r.json()
            if prompt_id in data and data[prompt_id]["outputs"]:
                break
            await asyncio.sleep(0.5)

    prompt_data = data[prompt_id]
    outputs = prompt_data["outputs"]
    print("HISTORY OUTPUTS:", json.dumps(outputs, indent=2))

    for node_id, node_out in outputs.items():
        images = node_out.get("images")
        if not images:
            continue
        img = images[0]
        filename = img["filename"]
        subfolder = img.get("subfolder", "")
        # This might already be relative to Comfy's output dir, or include it
        path = os.path.join(COMFY_OUTPUT_DIR, subfolder, filename)
        print("RESOLVED IMAGE PATH:", path)
        return path

    raise RuntimeError("No image outputs found in Comfy history")


# ---------- API ENDPOINT ----------

@app.post("/api/generate_building")
async def generate_building(req: AssetRequest):
    base_flow = load_api_workflow()
    flow = patch_api_workflow(base_flow, req)

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{COMFY_URL}/api/prompt", json=flow)
        print("COMFY STATUS:", r.status_code, r.text)
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]

    src = await wait_for_result(prompt_id)
    # For now, just return whatever we got back; don't copy
    return {"source_path": src}
