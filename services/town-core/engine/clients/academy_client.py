"""gRPC client from town-core to the Academy dialogue service.

Trigger path for Flow 2 (W1-A7): when two NPCs share a tile, town-core asks
Academy to write their conversation (`GenerateDialogue`). Academy generates it,
embeds it, and emits ``qtown.ai.content.generated`` for Tavern to broadcast — so
town-core only needs to *call* the RPC.

Best-effort by design — a slow or unreachable Academy must never break the sim
tick, so every call has a deadline, swallows transport errors, and returns
``None`` on failure. The client is only active when ``ACADEMY_GRPC_ADDR`` is set
(the compose / deployed stack sets it); ``get_academy_client()`` returns ``None``
otherwise, making the trigger a fast no-op in unit tests and single-service runs.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("town-core.academy_client")

# Make the buf-generated proto package (repo-root gen/python) importable — the
# generated modules use absolute imports (``from qtown import academy_pb2``).
# parents[4] == repo root from this file.
_GEN_PYTHON = Path(__file__).resolve().parents[4] / "gen" / "python"
if _GEN_PYTHON.is_dir() and str(_GEN_PYTHON) not in sys.path:
    sys.path.insert(0, str(_GEN_PYTHON))

try:
    import grpc
    from qtown import academy_pb2, academy_pb2_grpc

    _GRPC_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard for missing codegen/deps
    logger.warning("academy gRPC client unavailable (%s); dialogue trigger disabled", exc)
    _GRPC_AVAILABLE = False


# Dialogue is an LLM generation, not an order-book insert — give it real headroom
# (a warm model answers in a few seconds; this bounds the worst case). The tick
# call is wrapped off the event loop, so a longer deadline only delays that one
# tick, never FastAPI request handling.
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_COOLDOWN_S = 60.0


@dataclass
class DialogueLine:
    npc_id: int
    text: str
    emotion: str


class AcademyClient:
    """Thin best-effort wrapper over the Academy gRPC stub.

    Resilience: every call has a deadline (returns None instead of hanging), and
    a circuit breaker trips after repeated failures to fail fast during an outage.
    """

    def __init__(
        self,
        addr: str,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
        time_fn=time.monotonic,
    ) -> None:
        self._addr = addr
        self._channel = None
        self._stub = None
        self._failure_threshold = failure_threshold
        self._cooldown_s = cooldown_s
        self._now = time_fn
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _stub_or_none(self):
        if not _GRPC_AVAILABLE:
            return None
        if self._stub is None:
            self._channel = grpc.insecure_channel(self._addr)
            self._stub = academy_pb2_grpc.AcademyStub(self._channel)
        return self._stub

    def generate_dialogue(
        self,
        *,
        npc_id_a: int,
        npc_id_b: int,
        context: str,
        tone: str = "friendly",
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> list[DialogueLine] | None:
        """Ask Academy to write a conversation between two NPCs.

        Returns the generated lines, or ``None`` if Academy is unreachable / the
        call fails / the circuit is open. Never raises — the tick must continue.
        """
        # Circuit open → fail fast without a gRPC call (no deadline wait).
        if self._now() < self._circuit_open_until:
            return None

        stub = self._stub_or_none()
        if stub is None:
            return None
        req = academy_pb2.DialogueRequest(
            npc_id_a=int(npc_id_a),
            npc_id_b=int(npc_id_b),
            context=context,
            tone=tone,
        )
        try:
            resp = stub.GenerateDialogue(req, timeout=timeout)
            self._consecutive_failures = 0  # success resets the breaker
            return [
                DialogueLine(npc_id=line.npc_id, text=line.text, emotion=line.emotion)
                for line in resp.lines
            ]
        except grpc.RpcError as exc:  # academy down/slow — degrade, never crash
            code = exc.code() if hasattr(exc, "code") else "?"
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._circuit_open_until = self._now() + self._cooldown_s
                logger.warning(
                    "academy circuit OPEN for %.0fs after %d consecutive failures "
                    "(last: %s)",
                    self._cooldown_s, self._consecutive_failures, code,
                )
            else:
                logger.warning(
                    "GenerateDialogue(%s, %s) failed: %s", npc_id_a, npc_id_b, code
                )
            return None


_client: AcademyClient | None = None
_initialized = False


def get_academy_client() -> AcademyClient | None:
    """Return the singleton academy client, or ``None`` if not configured.

    Active only when ``ACADEMY_GRPC_ADDR`` is set (compose / deployed stack), so
    the dialogue trigger is a fast no-op in unit tests and single-service dev runs.
    """
    global _client, _initialized
    if not _initialized:
        _initialized = True
        addr = os.environ.get("ACADEMY_GRPC_ADDR")
        if addr and _GRPC_AVAILABLE:
            _client = AcademyClient(addr)
            logger.info("academy dialogue trigger enabled → %s", addr)
    return _client
