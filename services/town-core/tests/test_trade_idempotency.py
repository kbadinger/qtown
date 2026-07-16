"""W1-M4: idempotent economy.trade.settled consumer + DLQ.

Uses a real session (bound to the test db engine) so the ProcessedTrade
idempotency ledger is actually exercised — replaying a message must not
double-credit gold.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from engine.models import NPC, ProcessedTrade


def _patch_sessionlocal(monkeypatch, db):
    """Point the consumer's SessionLocal at the test db's engine."""
    factory = sessionmaker(bind=db.bind, autocommit=False, autoflush=False)
    monkeypatch.setattr("engine.kafka_consumer.SessionLocal", factory)


def _gold(db, npc_id: int) -> int:
    db.expire_all()
    return db.query(NPC).filter(NPC.id == npc_id).first().gold


@pytest.mark.asyncio
async def test_replay_credits_gold_once(db, monkeypatch):
    npc = NPC(name="Buyer", role="merchant", x=0, y=0, gold=100)
    db.add(npc)
    db.commit()
    npc_id = npc.id
    _patch_sessionlocal(monkeypatch, db)
    from engine.kafka_consumer import handle_trade_settled

    msg = {"npc_id": npc_id, "gold_delta": -30, "resource": "iron", "trade_id": "T1"}
    await handle_trade_settled(msg)
    await handle_trade_settled(msg)  # redelivery / replay

    assert _gold(db, npc_id) == 70  # 100 - 30, applied exactly once
    assert (
        db.query(ProcessedTrade)
        .filter(ProcessedTrade.trade_id == "T1", ProcessedTrade.npc_id == npc_id)
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_buyer_and_seller_share_trade_id_both_applied(db, monkeypatch):
    buyer = NPC(name="B", role="merchant", x=0, y=0, gold=100)
    seller = NPC(name="S", role="farmer", x=1, y=1, gold=100)
    db.add_all([buyer, seller])
    db.commit()
    bid, sid = buyer.id, seller.id
    _patch_sessionlocal(monkeypatch, db)
    from engine.kafka_consumer import handle_trade_settled

    # Same trade_id, opposite deltas — the compound (trade_id, npc_id) key lets
    # both counterparties settle while each stays idempotent on replay.
    await handle_trade_settled({"npc_id": bid, "gold_delta": -50, "resource": "wood", "trade_id": "T2"})
    await handle_trade_settled({"npc_id": sid, "gold_delta": 50, "resource": "wood", "trade_id": "T2"})
    await handle_trade_settled({"npc_id": bid, "gold_delta": -50, "resource": "wood", "trade_id": "T2"})  # replay buyer

    assert _gold(db, bid) == 50
    assert _gold(db, sid) == 150
    assert db.query(ProcessedTrade).filter(ProcessedTrade.trade_id == "T2").count() == 2


@pytest.mark.asyncio
async def test_handler_failure_routes_to_dlq(monkeypatch):
    from engine import kafka_consumer as kc

    captured = {}

    async def fake_emit(topic, key, value):
        captured["topic"] = topic
        captured["key"] = key
        captured["value"] = value

    monkeypatch.setattr(kc, "emit_event", fake_emit)

    consumer = kc.TownCoreConsumer()
    msg = MagicMock()
    msg.topic = "qtown.economy.trade.settled"
    msg.key = b"3"
    msg.value = {"npc_id": 3, "gold_delta": -30, "trade_id": "T3"}

    await consumer._send_to_dlq(msg, RuntimeError("boom"))

    assert captured["topic"] == "qtown.economy.trade.settled.dlq"
    assert captured["value"]["original_topic"] == "qtown.economy.trade.settled"
    assert captured["value"]["value"]["npc_id"] == 3
    assert "boom" in captured["value"]["error"]
    assert captured["value"]["failed_at"]  # ISO timestamp present


@pytest.mark.asyncio
async def test_replay_dlq_record_reapplies_idempotently(db, monkeypatch):
    npc = NPC(name="R", role="merchant", x=0, y=0, gold=100)
    db.add(npc)
    db.commit()
    npc_id = npc.id
    _patch_sessionlocal(monkeypatch, db)
    from engine.kafka_consumer import handle_trade_settled, replay_dlq_record

    record = {
        "original_topic": "qtown.economy.trade.settled",
        "value": {"npc_id": npc_id, "gold_delta": -25, "resource": "iron", "trade_id": "T4"},
    }
    await replay_dlq_record(record, handle_trade_settled)
    assert _gold(db, npc_id) == 75

    # Replaying the recovered message again is safe — no double debit.
    await replay_dlq_record(record, handle_trade_settled)
    assert _gold(db, npc_id) == 75
