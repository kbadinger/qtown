"""HTTP client for ComfyUI workflow submission and result polling."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COMFYUI_BASE_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")
POLL_INTERVAL_SECONDS = float(os.getenv("COMFYUI_POLL_INTERVAL", "2.0"))
MAX_POLL_ATTEMPTS = int(os.getenv("COMFYUI_MAX_POLL_ATTEMPTS", "150"))  # ~5 min


# ---------------------------------------------------------------------------
# Default workflow template (SDXL-compatible)
# ---------------------------------------------------------------------------

def _build_workflow(prompt: str, negative_prompt: str, width: int, height: int) -> dict[str, Any]:
    """Return a minimal ComfyUI workflow dict for text-to-image generation."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": int(uuid.uuid4()) & 0xFFFFFFFF,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": os.getenv("COMFYUI_MODEL", "v1-5-pruned-emaonly.ckpt")
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["4", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt or "blurry, low quality, ugly", "clip": ["4", 1]},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "qtown"},
        },
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ComfyUIClient:
    """Async HTTP client for ComfyUI API."""

    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=COMFYUI_BASE_URL,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=5.0),
        )
        logger.info("ComfyUIClient connected to %s", COMFYUI_BASE_URL)

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("ComfyUIClient not started — call start() first")
        return self._http

    async def submit_workflow(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        workflow_override: dict[str, Any] | None = None,
    ) -> str:
        """Submit a workflow to ComfyUI and return the prompt_id.

        Parameters
        ----------
        prompt:
            Positive text prompt for image generation.
        negative_prompt:
            Negative text prompt.
        width / height:
            Output image dimensions.
        workflow_override:
            If provided, use this workflow dict instead of the default.

        Returns
        -------
        prompt_id — string UUID assigned by ComfyUI.
        """
        workflow = workflow_override or _build_workflow(prompt, negative_prompt, width, height)
        payload = {"prompt": workflow}

        response = await self.http.post("/prompt", json=payload)
        response.raise_for_status()
        data = response.json()
        prompt_id: str = data["prompt_id"]
        logger.info("Submitted workflow; prompt_id=%s", prompt_id)
        return prompt_id

    async def poll_for_result(self, prompt_id: str) -> list[dict[str, Any]]:
        """Poll the /history endpoint until the workflow completes.

        Returns
        -------
        List of output image dicts with keys: filename, subfolder, type.

        Raises
        ------
        TimeoutError if MAX_POLL_ATTEMPTS is exceeded.
        RuntimeError if ComfyUI reports an execution error.
        """
        for attempt in range(MAX_POLL_ATTEMPTS):
            response = await self.http.get(f"/history/{prompt_id}")
            response.raise_for_status()
            history = response.json()

            if prompt_id not in history:
                # Not finished yet
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue

            entry = history[prompt_id]

            # Check for execution errors
            if entry.get("status", {}).get("status_str") == "error":
                messages = entry.get("status", {}).get("messages", [])
                raise RuntimeError(f"ComfyUI execution error for {prompt_id}: {messages}")

            # Collect output images from node "9" (SaveImage)
            images: list[dict[str, Any]] = []
            outputs = entry.get("outputs", {})
            for node_id, node_output in outputs.items():
                for img in node_output.get("images", []):
                    images.append(img)

            if images:
                logger.info(
                    "Workflow %s completed; %d image(s) ready (attempt %d)",
                    prompt_id,
                    len(images),
                    attempt + 1,
                )
                return images

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(
            f"ComfyUI workflow {prompt_id} did not complete within "
            f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS:.0f}s"
        )

    async def download_image(self, filename: str, subfolder: str = "", image_type: str = "output") -> bytes:
        """Download a generated image by filename."""
        params: dict[str, str] = {"filename": filename, "type": image_type}
        if subfolder:
            params["subfolder"] = subfolder
        response = await self.http.get("/view", params=params)
        response.raise_for_status()
        return response.content


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_comfyui_client: ComfyUIClient | None = None


def get_comfyui_client() -> ComfyUIClient:
    global _comfyui_client
    if _comfyui_client is None:
        _comfyui_client = ComfyUIClient()
    return _comfyui_client
