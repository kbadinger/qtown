"""gRPC client from town-core to the market-district order book.

Origination path for W1-M2: producer NPCs place SELL orders for their surplus
(see ``engine.simulation.economy.auto_sell_surplus``).

Best-effort by design — a slow or unreachable market must never break the sim
tick, so every call has a short deadline, swallows transport errors, and returns
``None`` on failure. The client is only active when ``MARKET_GRPC_ADDR`` is set
(the compose / deployed stack sets it); ``get_market_client()`` returns ``None``
otherwise, making origination a fast no-op in unit tests and single-service runs.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger("town-core.market_client")

# Make the buf-generated proto package (repo-root gen/python) importable. The
# generated modules use absolute imports (``from qtown import market_pb2``), so
# gen/python must be on sys.path. parents[4] == repo root from this file.
_GEN_PYTHON = Path(__file__).resolve().parents[4] / "gen" / "python"
if _GEN_PYTHON.is_dir() and str(_GEN_PYTHON) not in sys.path:
    sys.path.insert(0, str(_GEN_PYTHON))

try:
    import grpc
    from qtown import market_pb2, market_pb2_grpc

    _GRPC_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard for missing codegen/deps
    logger.warning("market gRPC client unavailable (%s); origination disabled", exc)
    _GRPC_AVAILABLE = False


# A slow/down market must not stall the tick — bound every call.
DEFAULT_TIMEOUT_S = 0.5
# Circuit breaker: after this many consecutive failures, stop calling for a
# cooldown so a down market costs one fast no-op per order instead of a full
# deadline wait on every order, every tick.
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_COOLDOWN_S = 30.0


class MarketClient:
    """Thin best-effort wrapper over the MarketDistrict gRPC stub.

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
        # Circuit-breaker state.
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
            self._stub = market_pb2_grpc.MarketDistrictStub(self._channel)
        return self._stub

    def place_order(
        self,
        *,
        npc_id: int,
        resource: str,
        side: str,
        price: float,
        quantity: float,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> tuple[str, bool] | None:
        """Place an order. ``side`` is ``"ASK"`` (sell) or ``"BID"`` (buy).

        Returns ``(order_id, accepted)`` on success, or ``None`` if the market is
        unreachable / the call fails / the circuit is open. Never raises — the
        tick must continue.
        """
        # Circuit open → fail fast without a gRPC call (no deadline wait).
        if self._now() < self._circuit_open_until:
            return None

        stub = self._stub_or_none()
        if stub is None:
            return None
        side_enum = (
            market_pb2.OrderSide.ASK if side == "ASK" else market_pb2.OrderSide.BID
        )
        req = market_pb2.PlaceOrderRequest(
            npc_id=int(npc_id),
            resource=resource,
            side=side_enum,
            price=float(price),
            quantity=float(quantity),
        )
        try:
            resp = stub.PlaceOrder(req, timeout=timeout)
            self._consecutive_failures = 0  # success resets the breaker
            return resp.order_id, resp.accepted
        except grpc.RpcError as exc:  # market down/slow — degrade, never crash
            code = exc.code() if hasattr(exc, "code") else "?"
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._circuit_open_until = self._now() + self._cooldown_s
                logger.warning(
                    "market circuit OPEN for %.0fs after %d consecutive failures "
                    "(last: %s)",
                    self._cooldown_s, self._consecutive_failures, code,
                )
            else:
                logger.warning(
                    "PlaceOrder(%s %s x%s) failed: %s", side, resource, quantity, code
                )
            return None


_client: MarketClient | None = None
_initialized = False


def get_market_client() -> MarketClient | None:
    """Return the singleton market client, or ``None`` if not configured.

    Active only when ``MARKET_GRPC_ADDR`` is set (compose / deployed stack), so
    origination is a fast no-op in unit tests and single-service dev runs.
    """
    global _client, _initialized
    if not _initialized:
        _initialized = True
        addr = os.environ.get("MARKET_GRPC_ADDR")
        if addr and _GRPC_AVAILABLE:
            _client = MarketClient(addr)
            logger.info("market origination enabled → %s", addr)
    return _client
