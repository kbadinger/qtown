"""
ModelRouter — maps task types to Ollama model names and dispatches inference.

The router tracks per-request token costs and provides fallback/escalation logic
when a model is unavailable or returns an error.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("academy.models.router")

# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------

# Maps task_type → Ollama model name.
# Models are listed in ascending capability / cost order; escalation walks
# right through the list until one succeeds.
ROUTE_TABLE: dict[str, list[str]] = {
    "dialogue": ["llama3:8b", "llama3:70b"],
    "planning": ["mistral:7b", "llama3:70b"],
    "memory_summary": ["phi3:mini", "llama3:8b"],
    "narration": ["llama3:8b", "llama3:70b"],
    "embedding": ["nomic-embed-text"],
    "code": ["codellama:7b", "codellama:34b"],
    "default": ["llama3:8b"],
}


@dataclass
class RouteResult:
    task_type: str
    model_used: str
    response: str
    prompt_tokens: int
    completion_tokens: int
    escalated: bool = False


@dataclass
class ModelRouter:
    """Routes inference requests to appropriate Ollama models with fallback."""

    ollama_base_url: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    timeout: float = 60.0

    # Simple in-process cost tracking (reset on restart).
    total_requests: int = field(default=0, init=False)
    total_cost_tokens: int = field(default=0, init=False)

    @property
    def ROUTES(self) -> dict[str, list[str]]:
        return ROUTE_TABLE

    async def route(self, task_type: str, context: dict[str, Any]) -> RouteResult:
        """
        Route a task to the best available model.

        ``context`` must contain at minimum a ``prompt`` key with the text to
        send to the model.  Other keys (e.g. ``system``, ``temperature``) are
        passed through to the Ollama /api/generate endpoint.

        Falls back through the model list for the task type until one succeeds.
        """
        models = ROUTE_TABLE.get(task_type, ROUTE_TABLE["default"])
        prompt = context.get("prompt", "")

        last_exc: Exception | None = None
        escalated = False

        for i, model in enumerate(models):
            if i > 0:
                escalated = True
                logger.warning(
                    "escalating from model %s to %s for task '%s'",
                    models[i - 1],
                    model,
                    task_type,
                )

            try:
                result = await self._call_ollama(model, prompt, context)
                self.total_requests += 1
                self.total_cost_tokens += result["prompt_eval_count"] + result["eval_count"]

                return RouteResult(
                    task_type=task_type,
                    model_used=model,
                    response=result["response"],
                    prompt_tokens=result.get("prompt_eval_count", 0),
                    completion_tokens=result.get("eval_count", 0),
                    escalated=escalated,
                )

            except Exception as exc:
                logger.error("model %s failed for task '%s': %s", model, task_type, exc)
                last_exc = exc

        raise RuntimeError(
            f"All models exhausted for task '{task_type}'. Last error: {last_exc}"
        )

    async def _call_ollama(
        self, model: str, prompt: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Post a generate request to the local Ollama API."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": context.get("temperature", 0.7),
                "num_predict": context.get("max_tokens", 512),
            },
        }
        if "system" in context:
            payload["system"] = context["system"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.ollama_base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[return-value]
