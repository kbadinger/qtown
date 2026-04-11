"""
Ollama HTTP client wrapper for the Academy service.

Provides async httpx-based access to a local Ollama instance with:
  - Streaming and non-streaming generation
  - Embedding via nomic-embed-text
  - Model listing
  - Configurable timeouts per model tier
  - Exponential-backoff retry (3 attempts)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger("academy.ollama_client")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL: str = "nomic-embed-text"

# Timeouts per model class (seconds)
TIMEOUT_FAST: float = 60.0   # qwen3-coder-next / small models
TIMEOUT_HEAVY: float = 120.0  # qwen3.5:27b, deepseek-r1:14b

_HEAVY_MODEL_PREFIXES = ("qwen3.5:27b", "qwen3.5:35b", "deepseek-r1")

MAX_RETRIES = 3
BACKOFF_BASE = 1.5  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _timeout_for(model: str) -> float:
    """Return the appropriate timeout (seconds) for a given model name."""
    lower = model.lower()
    for prefix in _HEAVY_MODEL_PREFIXES:
        if lower.startswith(prefix):
            return TIMEOUT_HEAVY
    return TIMEOUT_FAST


async def _with_retry(coro_factory, *, retries: int = MAX_RETRIES) -> Any:
    """
    Execute an async factory with exponential-backoff retries.

    ``coro_factory`` is a zero-arg callable that returns a coroutine.
    Retried on httpx.RequestError and httpx.HTTPStatusError with 5xx codes.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            last_exc = exc
            wait = BACKOFF_BASE ** attempt
            logger.warning(
                "Ollama request attempt %d/%d failed (%s): %s — retrying in %.1fs",
                attempt + 1,
                retries,
                type(exc).__name__,
                exc,
                wait,
            )
            if attempt < retries - 1:
                await asyncio.sleep(wait)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise  # 4xx — don't retry
            last_exc = exc
            wait = BACKOFF_BASE ** attempt
            logger.warning(
                "Ollama HTTP %d attempt %d/%d — retrying in %.1fs",
                exc.response.status_code,
                attempt + 1,
                retries,
                wait,
            )
            if attempt < retries - 1:
                await asyncio.sleep(wait)

    raise RuntimeError(f"Ollama request failed after {retries} attempts") from last_exc


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OllamaClient:
    """Async Ollama HTTP client with retry and timeout management."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = False,
    ) -> str:
        """
        Generate text from a prompt.

        Returns the full response string (non-streaming) or streams tokens
        and returns the concatenated result (streaming).
        """
        if stream:
            chunks: list[str] = []
            async for chunk in self.generate_stream(
                model, prompt, system=system, temperature=temperature, max_tokens=max_tokens
            ):
                chunks.append(chunk)
            return "".join(chunks)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        timeout = _timeout_for(model)

        async def _call() -> str:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data["response"]

        return await _with_retry(_call)

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """
        Yield text tokens as they arrive from the streaming Ollama API.
        """
        import json as _json

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        timeout = _timeout_for(model)

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/generate", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = _json.loads(line)
                    except _json.JSONDecodeError:
                        continue
                    token: str = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break

    async def embed(self, text: str, *, model: str = EMBED_MODEL) -> list[float]:
        """
        Return a float embedding vector for ``text``.

        Uses the Ollama /api/embeddings endpoint with ``nomic-embed-text``
        by default (768-dimensional).
        """

        async def _call() -> list[float]:
            async with httpx.AsyncClient(timeout=TIMEOUT_FAST) as client:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data["embedding"]

        return await _with_retry(_call)

    async def embed_batch(
        self, texts: list[str], *, model: str = EMBED_MODEL
    ) -> list[list[float]]:
        """
        Embed a batch of texts sequentially (Ollama does not support batch endpoints).

        Respects a batch size cap of 32.
        """
        if len(texts) > 32:
            raise ValueError("embed_batch: maximum batch size is 32")

        results: list[list[float]] = []
        for text in texts:
            vec = await self.embed(text, model=model)
            results.append(vec)
        return results

    async def list_models(self) -> list[str]:
        """Return the names of all models currently available in Ollama."""

        async def _call() -> list[str]:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return [m["name"] for m in data.get("models", [])]

        return await _with_retry(_call)

    async def is_available(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            await self.list_models()
            return True
        except Exception:
            return False

    async def generate_with_metadata(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        """
        Generate text and return a dict with response + token counts + latency.

        Returns::

            {
                "response": str,
                "model": str,
                "prompt_tokens": int,
                "completion_tokens": int,
                "latency_ms": float,
            }
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        timeout = _timeout_for(model)
        t0 = time.monotonic()

        async def _call() -> dict[str, Any]:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json()

        data = await _with_retry(_call)
        latency_ms = (time.monotonic() - t0) * 1000.0

        return {
            "response": data.get("response", ""),
            "model": model,
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "latency_ms": round(latency_ms, 2),
        }


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_client: OllamaClient | None = None


def get_client() -> OllamaClient:
    """Return the module-level OllamaClient singleton."""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client
