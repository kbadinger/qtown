"""
Tests for academy.kafka_producer.

No live Kafka — the underlying ``_send`` is mocked so we can assert the
exact topic and payload each emit helper produces.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from academy.kafka_producer import (
    TOPIC_CONTENT_GENERATED,
    AcademyProducer,
)


# ---------------------------------------------------------------------------
# Topic constants — must match infra/kafka-init.sh (qtown.* prefix)
# ---------------------------------------------------------------------------


def test_content_topic_is_qtown_prefixed():
    assert TOPIC_CONTENT_GENERATED == "qtown.ai.content.generated"


# ---------------------------------------------------------------------------
# emit_content_generated
# ---------------------------------------------------------------------------


class TestEmitContentGenerated:
    @pytest.mark.asyncio
    async def test_emits_expected_topic_and_payload(self):
        producer = AcademyProducer()
        producer._send = AsyncMock()

        await producer.emit_content_generated(
            content_type="dialogue",
            content_id="dialogue-1-2-99",
            content=[{"npc_id": 1, "text": "Hi", "emotion": "happy"}],
            text="NPC 1: Hi",
            metadata={
                "npc_a": 1,
                "npc_b": 2,
                "tone": "friendly",
                "model_used": "deepseek-r1:14b",
            },
        )

        producer._send.assert_awaited_once()
        topic, payload = producer._send.call_args.args
        assert topic == TOPIC_CONTENT_GENERATED == "qtown.ai.content.generated"

        assert payload["content_type"] == "dialogue"
        assert payload["content_id"] == "dialogue-1-2-99"
        assert payload["content"] == [{"npc_id": 1, "text": "Hi", "emotion": "happy"}]
        # `text` is required by Tavern's ContentGenerated type
        assert payload["text"] == "NPC 1: Hi"
        assert payload["metadata"]["model_used"] == "deepseek-r1:14b"

        # Key correlates content_type + id for consumers
        assert producer._send.call_args.kwargs["key"] == "dialogue:dialogue-1-2-99"

    @pytest.mark.asyncio
    async def test_text_defaults_to_empty_string(self):
        producer = AcademyProducer()
        producer._send = AsyncMock()

        await producer.emit_content_generated(
            content_type="newspaper",
            content_id="news-1",
            content={"headline": "Extra"},
        )

        _, payload = producer._send.call_args.args
        assert payload["text"] == ""
