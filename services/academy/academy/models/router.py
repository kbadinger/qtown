"""
ModelRouter — maps task types to Ollama model names and dispatches inference.

Model tiers:
  LOCAL_FAST    → qwen3-coder-next  (≤3B, sub-second, zero cost)
  LOCAL_QUALITY → deepseek-r1:14b   (14B, good reasoning, zero cost)
  LOCAL_HEAVY   → qwen3.5:27b       (27B, newspaper / long-form, zero cost)
  LOCAL_CONTENT → qwen3.5:35b-a3b   (35B MoE, creative content, zero cost)
  CLOUD_FALLBACK→ configured via env (has per-token cost)

Escalation chain: if a LOCAL model fails, the router falls back to
CLOUD_FALLBACK for that request and records it against routing stats.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("academy.models.router")

# ---------------------------------------------------------------------------
# Model tier definitions
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    LOCAL_FAST = "local_fast"
    LOCAL_QUALITY = "local_quality"
    LOCAL_HEAVY = "local_heavy"
    LOCAL_CONTENT = "local_content"
    CLOUD_FALLBACK = "cloud_fallback"


@dataclass(frozen=True)
class RouteConfig:
    """Configuration for a single task-type route."""

    model_id: str
    tier: ModelTier
    cost_per_1k_tokens: float = 0.0  # USD; 0.0 for all local models
    max_tokens: int = 512
    temperature: float = 0.7


# ---------------------------------------------------------------------------
# Route table  — maps task_type → RouteConfig
# ---------------------------------------------------------------------------

_CLOUD_MODEL = os.environ.get("CLOUD_MODEL", "gpt-4o-mini")
_CLOUD_COST = float(os.environ.get("CLOUD_COST_PER_1K", "0.0015"))

ROUTE_TABLE: dict[str, RouteConfig] = {
    # Fast chatter — lightweight NPC one-liners
    "npc_chatter": RouteConfig(
        model_id="qwen3:3b",
        tier=ModelTier.LOCAL_FAST,
        max_tokens=128,
        temperature=0.8,
    ),
    # Full NPC dialogue exchanges. Model is env-overridable so a deployment can
    # point it at a model its Ollama actually has — otherwise an unavailable model
    # escalates to the cloud fallback, which returns a stub when no API key is set
    # (that would be fabricated dialogue; see Flow 2 / W1-A7).
    "npc_dialogue": RouteConfig(
        model_id=os.environ.get("NPC_DIALOGUE_MODEL", "deepseek-r1:14b"),
        tier=ModelTier.LOCAL_QUALITY,
        max_tokens=512,
        temperature=0.7,
    ),
    # NPC planning / decision making
    "planning": RouteConfig(
        model_id="deepseek-r1:14b",
        tier=ModelTier.LOCAL_QUALITY,
        max_tokens=256,
        temperature=0.3,
    ),
    # Memory summarisation (short)
    "memory_summary": RouteConfig(
        model_id="qwen3-coder-next",
        tier=ModelTier.LOCAL_FAST,
        max_tokens=256,
        temperature=0.4,
    ),
    # In-world newspaper articles
    "newspaper": RouteConfig(
        model_id="qwen3.5:27b",
        tier=ModelTier.LOCAL_HEAVY,
        max_tokens=1024,
        temperature=0.7,
    ),
    # Long-form creative / quest text
    "narration": RouteConfig(
        model_id="qwen3.5:35b-a3b",
        tier=ModelTier.LOCAL_CONTENT,
        max_tokens=768,
        temperature=0.75,
    ),
    # Debug / analysis tasks
    "debug": RouteConfig(
        model_id="deepseek-r1:14b",
        tier=ModelTier.LOCAL_QUALITY,
        max_tokens=1024,
        temperature=0.1,
    ),
    # Escalated / complex generation (cloud)
    "complex_gen": RouteConfig(
        model_id=_CLOUD_MODEL,
        tier=ModelTier.CLOUD_FALLBACK,
        cost_per_1k_tokens=_CLOUD_COST,
        max_tokens=2048,
        temperature=0.7,
    ),
}

# ---------------------------------------------------------------------------
# Route result
# ---------------------------------------------------------------------------


class RouteResult(str):
    """
    The result of a routed inference call: the generated text plus routing
    metadata (which model ran, real token counts).

    Subclasses ``str`` so legacy callers that treat the result as the raw
    response text keep working; new callers should read ``.response`` and
    ``.model_used`` explicitly.
    """

    task_type: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int

    def __new__(
        cls,
        *,
        task_type: str,
        model_used: str,
        response: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> "RouteResult":
        obj = super().__new__(cls, response)
        obj.task_type = task_type
        obj.model_used = model_used
        obj.prompt_tokens = prompt_tokens
        obj.completion_tokens = completion_tokens
        return obj

    @property
    def response(self) -> str:
        return str(self)


def _normalize_call_result(
    raw: dict[str, Any] | str, fallback_model: str
) -> tuple[str, str, int, int]:
    """
    Return ``(text, model_used, prompt_tokens, completion_tokens)`` from a
    model-call result. The call helpers return a metadata dict; unit tests
    mock them with bare strings, in which case token counts are 0
    ("not measured"), never invented.
    """
    if isinstance(raw, dict):
        return (
            raw.get("response", ""),
            raw.get("model", fallback_model),
            int(raw.get("prompt_tokens", 0)),
            int(raw.get("completion_tokens", 0)),
        )
    return raw, fallback_model, 0, 0


# ---------------------------------------------------------------------------
# Stats tracking
# ---------------------------------------------------------------------------


@dataclass
class RoutingStats:
    total_requests: int = 0
    local_requests: int = 0
    cloud_requests: int = 0
    total_cost_usd: float = 0.0
    latencies: list[float] = field(default_factory=list)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    requests_by_model: dict[str, int] = field(default_factory=dict)
    latency_by_model: dict[str, list[float]] = field(default_factory=dict)

    def record(
        self,
        model_id: str,
        tier: ModelTier,
        latency_ms: float,
        tokens_in: int,
        tokens_out: int,
        cost_per_1k: float,
    ) -> None:
        self.total_requests += 1
        self.latencies.append(latency_ms)

        if tier == ModelTier.CLOUD_FALLBACK:
            self.cloud_requests += 1
        else:
            self.local_requests += 1

        total_tokens = tokens_in + tokens_out
        cost = (total_tokens / 1000.0) * cost_per_1k
        self.total_cost_usd += cost
        self.cost_by_model[model_id] = self.cost_by_model.get(model_id, 0.0) + cost
        self.requests_by_model[model_id] = self.requests_by_model.get(model_id, 0) + 1

        if model_id not in self.latency_by_model:
            self.latency_by_model[model_id] = []
        self.latency_by_model[model_id].append(latency_ms)


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------


class ModelRouter:
    """
    Routes inference requests to the appropriate Ollama (or cloud) model.

    Usage::

        router = ModelRouter()
        result = await router.route("npc_dialogue", "Tell me about the harvest.")
        print(result.response, result.model_used)
    """

    def __init__(self) -> None:
        from academy.ollama_client import OllamaClient

        self._ollama = OllamaClient()
        self.stats = RoutingStats()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def ROUTES(self) -> dict[str, RouteConfig]:
        return ROUTE_TABLE

    def get_routing_stats(self) -> dict[str, Any]:
        """Return a JSON-serialisable stats snapshot."""
        s = self.stats
        total = max(s.total_requests, 1)
        avg_lat = sum(s.latencies) / len(s.latencies) if s.latencies else 0.0

        by_model = [
            {
                "model_name": model,
                "request_count": s.requests_by_model.get(model, 0),
                "avg_latency_ms": round(
                    sum(s.latency_by_model.get(model, [0])) /
                    max(len(s.latency_by_model.get(model, [1])), 1),
                    2,
                ),
                "cost_usd": round(s.cost_by_model.get(model, 0.0), 6),
            }
            for model in s.requests_by_model
        ]

        return {
            "total_requests": s.total_requests,
            "local_pct": round(s.local_requests / total * 100, 1),
            "cloud_pct": round(s.cloud_requests / total * 100, 1),
            "avg_latency_ms": round(avg_lat, 2),
            "cost_today_usd": round(s.total_cost_usd, 4),
            "by_model": by_model,
        }

    async def route(
        self,
        task_type: str,
        request: str | dict[str, Any],
        *,
        system: str | None = None,
    ) -> RouteResult:
        """
        Route a prompt to the appropriate model.

        ``request`` is either the prompt string, or a dict with ``prompt``
        plus optional per-call overrides (``system``, ``temperature``,
        ``max_tokens``). Falls back to cloud if the local model fails.
        Returns a :class:`RouteResult` carrying the generated text and real
        token counts.
        """
        cfg = ROUTE_TABLE.get(task_type, ROUTE_TABLE["npc_chatter"])
        if isinstance(request, dict):
            prompt = request.get("prompt", "")
            system = request.get("system", system)
            temperature = float(request.get("temperature", cfg.temperature))
            max_tokens = int(request.get("max_tokens", cfg.max_tokens))
        else:
            prompt = request
            temperature = cfg.temperature
            max_tokens = cfg.max_tokens

        t0 = time.monotonic()

        try:
            if cfg.tier == ModelTier.CLOUD_FALLBACK:
                raw = await self._call_cloud(
                    cfg.model_id, prompt, system=system, max_tokens=max_tokens,
                    temperature=temperature,
                )
                text, model_used, tokens_in, tokens_out = _normalize_call_result(
                    raw, cfg.model_id
                )
                latency_ms = (time.monotonic() - t0) * 1000.0
                self.stats.record(
                    cfg.model_id, cfg.tier, latency_ms, tokens_in, tokens_out,
                    cfg.cost_per_1k_tokens,
                )
                return RouteResult(
                    task_type=task_type, model_used=model_used, response=text,
                    prompt_tokens=tokens_in, completion_tokens=tokens_out,
                )

            # Local path — attempt Ollama, escalate on failure
            try:
                raw = await self._call_ollama(
                    cfg.model_id, prompt, system=system,
                    max_tokens=max_tokens, temperature=temperature,
                )
                text, model_used, tokens_in, tokens_out = _normalize_call_result(
                    raw, cfg.model_id
                )
                latency_ms = (time.monotonic() - t0) * 1000.0
                self.stats.record(
                    cfg.model_id, cfg.tier, latency_ms, tokens_in, tokens_out, 0.0
                )
                return RouteResult(
                    task_type=task_type, model_used=model_used, response=text,
                    prompt_tokens=tokens_in, completion_tokens=tokens_out,
                )

            except Exception as local_exc:
                logger.warning(
                    "Local model %s failed for task '%s': %s — escalating to cloud",
                    cfg.model_id, task_type, local_exc,
                )
                cloud_cfg = ROUTE_TABLE["complex_gen"]
                raw = await self._call_cloud(
                    cloud_cfg.model_id, prompt, system=system,
                    max_tokens=cloud_cfg.max_tokens, temperature=cloud_cfg.temperature,
                )
                text, model_used, tokens_in, tokens_out = _normalize_call_result(
                    raw, cloud_cfg.model_id
                )
                latency_ms = (time.monotonic() - t0) * 1000.0
                self.stats.record(
                    cloud_cfg.model_id, ModelTier.CLOUD_FALLBACK, latency_ms,
                    tokens_in, tokens_out, cloud_cfg.cost_per_1k_tokens,
                )
                return RouteResult(
                    task_type=task_type, model_used=model_used, response=text,
                    prompt_tokens=tokens_in, completion_tokens=tokens_out,
                )

        except Exception as exc:
            logger.error("ModelRouter.route failed for task '%s': %s", task_type, exc)
            raise

    # ------------------------------------------------------------------
    # Internal helpers (can be mocked in tests)
    # ------------------------------------------------------------------

    async def _call_ollama(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> dict[str, Any] | str:
        """
        Call Ollama and return the metadata dict (response + real token
        counts). Tests may mock this with a bare response string; ``route()``
        normalizes either shape.

        ``think=False`` disables the chain-of-thought trace on reasoning models
        (qwen3.5 / deepseek-r1): the router's callers parse the ``response``, not
        the reasoning, and leaving thinking on burns the ``max_tokens`` budget on
        hidden tokens — which can truncate or empty the actual answer.
        """
        return await self._ollama.generate_with_metadata(
            model, prompt, system=system, temperature=temperature,
            max_tokens=max_tokens, think=False,
        )

    async def _call_cloud(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> dict[str, Any] | str:
        """
        Call a cloud LLM (OpenAI-compatible API) and return a metadata dict
        (response + usage token counts). Tests may mock this with a bare
        response string; ``route()`` normalizes either shape.

        Requires OPENAI_API_KEY in environment. Falls back to a stub
        response if the key is absent (for offline testing).
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set; returning stub cloud response")
            return {
                "response": f"[cloud-stub] Response to: {prompt[:60]}...",
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        import httpx  # already a dep

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            return {
                "response": data["choices"][0]["message"]["content"],
                "model": data.get("model", model),
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
            }
