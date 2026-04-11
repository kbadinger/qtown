"""Tests for the Kafka consumer routing and buffer logic."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from library.kafka_consumer import IndexBuffer, LibraryConsumer


# ---------------------------------------------------------------------------
# IndexBuffer unit tests
# ---------------------------------------------------------------------------


class TestIndexBuffer:
    def test_add_and_drain(self) -> None:
        buf = IndexBuffer("qtown-events")
        buf.add({"event_id": "e1"})
        buf.add({"event_id": "e2"})
        assert not buf.is_empty()
        drained = buf.drain()
        assert len(drained) == 2
        assert buf.is_empty()

    def test_should_flush_on_size(self) -> None:
        buf = IndexBuffer("qtown-events")
        from library.kafka_consumer import MAX_BUFFER_SIZE

        for i in range(MAX_BUFFER_SIZE):
            buf.add({"event_id": f"e{i}"})
        assert buf.should_flush()

    def test_should_flush_on_time(self) -> None:
        buf = IndexBuffer("qtown-events")
        buf.add({"event_id": "e1"})
        # Backdate the last flush time
        buf._last_flush = time.monotonic() - 10.0
        assert buf.should_flush()

    def test_should_not_flush_when_empty(self) -> None:
        buf = IndexBuffer("qtown-events")
        # Even with stale timestamp, empty buffer should not flush
        buf._last_flush = time.monotonic() - 10.0
        assert not buf.should_flush()

    def test_drain_resets_last_flush(self) -> None:
        buf = IndexBuffer("qtown-events")
        buf.add({"event_id": "e1"})
        old_flush = buf._last_flush - 100.0
        buf._last_flush = old_flush
        buf.drain()
        assert buf._last_flush > old_flush


# ---------------------------------------------------------------------------
# LibraryConsumer routing tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_es() -> MagicMock:
    es = MagicMock()
    es.bulk_index = AsyncMock(return_value={"success": 1, "errors": []})
    return es


@pytest.fixture()
def consumer() -> LibraryConsumer:
    return LibraryConsumer()


class TestLibraryConsumerRouting:
    @pytest.mark.asyncio()
    async def test_route_broadcast_event(
        self, consumer: LibraryConsumer, mock_es: MagicMock
    ) -> None:
        payload: dict[str, Any] = {
            "event_id": "evt-1",
            "type": "npc_travel",
            "description": "Bob walked to the tavern",
        }
        await consumer._route("events.broadcast", payload)
        assert not consumer._buffers["qtown-events"].is_empty()

    @pytest.mark.asyncio()
    async def test_route_newspaper_content(
        self, consumer: LibraryConsumer
    ) -> None:
        payload: dict[str, Any] = {
            "content_type": "newspaper",
            "day": 10,
            "headline": "Big news today",
        }
        await consumer._route("ai.content.generated", payload)
        assert not consumer._buffers["qtown-newspapers"].is_empty()
        assert consumer._buffers["qtown-dialogues"].is_empty()

    @pytest.mark.asyncio()
    async def test_route_dialogue_content(
        self, consumer: LibraryConsumer
    ) -> None:
        payload: dict[str, Any] = {
            "content_type": "dialogue",
            "dialogue_id": "dlg-1",
            "npc_id": "npc-bob",
            "text": "Howdy, stranger!",
        }
        await consumer._route("ai.content.generated", payload)
        assert not consumer._buffers["qtown-dialogues"].is_empty()
        assert consumer._buffers["qtown-newspapers"].is_empty()

    @pytest.mark.asyncio()
    async def test_route_unknown_content_type_ignored(
        self, consumer: LibraryConsumer
    ) -> None:
        payload: dict[str, Any] = {"content_type": "video", "url": "http://example.com"}
        await consumer._route("ai.content.generated", payload)
        # All dialogue and newspaper buffers should remain empty
        assert consumer._buffers["qtown-dialogues"].is_empty()
        assert consumer._buffers["qtown-newspapers"].is_empty()

    @pytest.mark.asyncio()
    async def test_route_trade_settled(
        self, consumer: LibraryConsumer
    ) -> None:
        payload: dict[str, Any] = {
            "trade_id": "trade-99",
            "buyer_id": "npc-alice",
            "seller_id": "npc-bob",
            "resource": "wheat",
            "price": 5.0,
            "quantity": 10.0,
        }
        await consumer._route("economy.trade.settled", payload)
        assert not consumer._buffers["qtown-transactions"].is_empty()


# ---------------------------------------------------------------------------
# Flush logic tests
# ---------------------------------------------------------------------------


class TestFlushLogic:
    @pytest.mark.asyncio()
    async def test_flush_buffer_calls_bulk_index(
        self, consumer: LibraryConsumer, mock_es: MagicMock
    ) -> None:
        consumer._buffers["qtown-events"].add({"event_id": "e1"})
        consumer._buffers["qtown-events"].add({"event_id": "e2"})

        with patch("library.kafka_consumer.get_es_client", return_value=mock_es):
            await consumer._flush_buffer(consumer._buffers["qtown-events"])

        mock_es.bulk_index.assert_awaited_once()
        call_args = mock_es.bulk_index.call_args
        assert call_args[0][0] == "qtown-events"
        assert len(call_args[0][1]) == 2

    @pytest.mark.asyncio()
    async def test_flush_buffer_requeues_on_error(
        self, consumer: LibraryConsumer
    ) -> None:
        failing_es = MagicMock()
        failing_es.bulk_index = AsyncMock(side_effect=Exception("ES error"))

        consumer._buffers["qtown-events"].add({"event_id": "e1"})

        with patch("library.kafka_consumer.get_es_client", return_value=failing_es):
            await consumer._flush_buffer(consumer._buffers["qtown-events"])

        # Doc should have been re-queued
        assert not consumer._buffers["qtown-events"].is_empty()

    @pytest.mark.asyncio()
    async def test_flush_all_flushes_non_empty_buffers(
        self, consumer: LibraryConsumer, mock_es: MagicMock
    ) -> None:
        consumer._buffers["qtown-events"].add({"event_id": "e1"})
        consumer._buffers["qtown-transactions"].add({"trade_id": "t1"})

        with patch("library.kafka_consumer.get_es_client", return_value=mock_es):
            await consumer._flush_all()

        assert mock_es.bulk_index.await_count == 2

    @pytest.mark.asyncio()
    async def test_flush_all_skips_empty_buffers(
        self, consumer: LibraryConsumer, mock_es: MagicMock
    ) -> None:
        # Only events buffer has data
        consumer._buffers["qtown-events"].add({"event_id": "e1"})

        with patch("library.kafka_consumer.get_es_client", return_value=mock_es):
            await consumer._flush_all()

        # Only one bulk_index call, not four
        assert mock_es.bulk_index.await_count == 1
