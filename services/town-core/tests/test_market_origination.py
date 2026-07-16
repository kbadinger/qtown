"""W1-M2: town-core originates market orders (producer NPCs auto-sell surplus).

Covers the origination logic (engine.simulation.economy.auto_sell_surplus) with a
mocked market client, and the best-effort MarketClient wrapper's request shaping
and graceful failure.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from engine.models import NPC, Building, Resource
from engine.simulation.economy import auto_sell_surplus, SURPLUS_KEEP_STOCK


def _seed_producer(db, *, role="miner", building_type="mine",
                   resource="Ore", quantity=30):
    """Seed a producer NPC at their work building with some stock. Returns the NPC."""
    building = Building(name=f"{role}_site", building_type=building_type, x=0, y=0)
    db.add(building)
    db.commit()
    npc = NPC(name=f"{role}_npc", role=role, x=0, y=0, gold=0)
    npc.work_building_id = building.id
    db.add(npc)
    db.add(Resource(name=resource, quantity=quantity, building_id=building.id))
    db.commit()
    return npc, building


class TestAutoSellSurplus:
    def test_places_ask_for_surplus_and_escrows_stock(self, db):
        npc, building = _seed_producer(db, quantity=30)  # surplus = 30 - 20 = 10
        client = MagicMock()
        client.place_order.return_value = ("ORD-1", True)  # accepted

        placed = auto_sell_surplus(db, client=client)

        assert placed == 1
        client.place_order.assert_called_once()
        kwargs = client.place_order.call_args.kwargs
        assert kwargs["npc_id"] == npc.id
        assert kwargs["resource"] == "Ore"
        assert kwargs["side"] == "ASK"
        assert kwargs["quantity"] == 10
        assert isinstance(kwargs["price"], float)

        # Accepted order escrows the surplus out of the building's local stock.
        ore = db.query(Resource).filter(
            Resource.name == "Ore", Resource.building_id == building.id
        ).first()
        assert ore.quantity == SURPLUS_KEEP_STOCK

    def test_no_order_when_stock_at_or_below_keep(self, db):
        _seed_producer(db, quantity=SURPLUS_KEEP_STOCK)  # exactly keep → no surplus
        client = MagicMock()

        placed = auto_sell_surplus(db, client=client)

        assert placed == 0
        client.place_order.assert_not_called()

    def test_market_down_keeps_stock(self, db):
        _seed_producer(db, quantity=30)
        client = MagicMock()
        client.place_order.return_value = None  # market unreachable

        placed = auto_sell_surplus(db, client=client)

        assert placed == 0
        ore = db.query(Resource).filter(Resource.name == "Ore").first()
        assert ore.quantity == 30  # nothing escrowed — no order landed

    def test_noop_when_no_client_configured(self, db, monkeypatch):
        # No MARKET_GRPC_ADDR → get_market_client() returns None → fast no-op.
        monkeypatch.delenv("MARKET_GRPC_ADDR", raising=False)
        _seed_producer(db, quantity=30)

        placed = auto_sell_surplus(db)  # client defaults to get_market_client()

        assert placed == 0
        ore = db.query(Resource).filter(Resource.name == "Ore").first()
        assert ore.quantity == 30

    def test_only_producer_roles_sell(self, db):
        # A non-producer role (guard) with lots of stock is never offered.
        building = Building(name="guardhouse", building_type="barracks", x=0, y=0)
        db.add(building)
        db.commit()
        npc = NPC(name="guard", role="guard", x=0, y=0, gold=0)
        npc.work_building_id = building.id
        db.add(npc)
        db.add(Resource(name="Ore", quantity=99, building_id=building.id))
        db.commit()
        client = MagicMock()

        placed = auto_sell_surplus(db, client=client)

        assert placed == 0
        client.place_order.assert_not_called()


class TestMarketClient:
    def test_place_order_builds_request_and_unpacks_response(self):
        from engine.clients.market_client import MarketClient

        client = MarketClient("localhost:50051")
        fake_stub = MagicMock()
        fake_stub.PlaceOrder.return_value = MagicMock(order_id="ORD-9", accepted=True)
        client._stub = fake_stub  # inject; skip real channel

        result = client.place_order(
            npc_id=7, resource="Wood", side="ASK", price=2.5, quantity=8
        )

        assert result == ("ORD-9", True)
        req = fake_stub.PlaceOrder.call_args[0][0]
        assert req.npc_id == 7
        assert req.resource == "Wood"
        assert req.side == 2  # OrderSide.ASK
        assert abs(req.price - 2.5) < 1e-6
        assert abs(req.quantity - 8.0) < 1e-6

    def test_place_order_returns_none_on_rpc_error(self):
        import grpc
        from engine.clients.market_client import MarketClient

        client = MarketClient("localhost:50051")
        fake_stub = MagicMock()
        fake_stub.PlaceOrder.side_effect = grpc.RpcError("boom")
        client._stub = fake_stub

        result = client.place_order(
            npc_id=1, resource="Ore", side="ASK", price=1.0, quantity=5
        )
        assert result is None

    def test_circuit_opens_after_threshold_and_fails_fast(self):
        import grpc
        from engine.clients.market_client import MarketClient

        clock = {"t": 0.0}
        client = MarketClient(
            "localhost:50051",
            failure_threshold=3,
            cooldown_s=30.0,
            time_fn=lambda: clock["t"],
        )
        failing = MagicMock()
        failing.PlaceOrder.side_effect = grpc.RpcError("down")
        client._stub = failing

        for _ in range(3):
            assert _place(client) is None
        assert failing.PlaceOrder.call_count == 3  # circuit now open

        # While open, calls fail fast — no further gRPC attempts.
        assert _place(client) is None
        assert failing.PlaceOrder.call_count == 3

        # After the cooldown elapses, calls are attempted again.
        clock["t"] = 31.0
        _place(client)
        assert failing.PlaceOrder.call_count == 4

    def test_success_resets_failure_count(self):
        import grpc
        from engine.clients.market_client import MarketClient

        client = MarketClient("localhost:50051", failure_threshold=3, time_fn=lambda: 0.0)
        stub = MagicMock()
        ok = MagicMock(order_id="ORD", accepted=True)
        # 2 fails, a success (resets), 2 more fails → never 3 in a row → stays closed.
        stub.PlaceOrder.side_effect = [
            grpc.RpcError("x"), grpc.RpcError("x"), ok,
            grpc.RpcError("x"), grpc.RpcError("x"),
        ]
        client._stub = stub

        results = [_place(client) for _ in range(5)]
        assert results[2] == ("ORD", True)
        assert client._circuit_open_until == 0.0  # never opened
        assert stub.PlaceOrder.call_count == 5  # all attempted


def _place(client):
    return client.place_order(
        npc_id=1, resource="Ore", side="ASK", price=1.0, quantity=1
    )
