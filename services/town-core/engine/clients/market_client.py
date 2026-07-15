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


class MarketClient:
    """Thin best-effort wrapper over the MarketDistrict gRPC stub."""

    def __init__(self, addr: str) -> None:
        self._addr = addr
        self._channel = None
        self._stub = None

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
        unreachable / the call fails. Never raises — the tick must continue.
        """
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
            return resp.order_id, resp.accepted
        except grpc.RpcError as exc:  # market down/slow — degrade, never crash
            code = exc.code() if hasattr(exc, "code") else "?"
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
