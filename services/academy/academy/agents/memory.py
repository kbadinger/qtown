"""
NPC Memory Consolidation — P5-006.

Periodically summarises large volumes of raw NPC memory events into compact
"consolidated memory" records backed by pgvector, using ModelRouter for LLM
summarisation and Kafka for trigger/result events.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("academy.agents.memory")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONSOLIDATION_INTERVAL: int = 50    # ticks between consolidation runs per NPC
MIN_EVENTS_PER_CATEGORY: int = 10   # minimum events before a category is summarised

MEMORY_CATEGORIES: tuple[str, ...] = (
    "trade",
    "social",
    "travel",
    "combat",
    "work",
)

# Kafka topics
TOPIC_CONSOLIDATE_TRIGGER = "npc.memory.consolidate"
TOPIC_CONSOLIDATED_RESULT = "npc.memory.consolidated"

# Importance score assigned to consolidated memories (higher than raw events).
CONSOLIDATED_IMPORTANCE: float = 0.8


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ConsolidatedMemory:
    """A summarised memory block stored in pgvector with a higher retrieval weight."""

    npc_id: str
    category: str
    summary_text: str
    event_count: int
    tick_range: tuple[int, int]   # (start_tick, end_tick) of the source events
    embedding: list[float]        # pgvector embedding of summary_text
    importance_score: float = CONSOLIDATED_IMPORTANCE  # 0–1


@dataclass
class ConsolidationResult:
    """Output of a single MemoryConsolidator.consolidate() call."""

    npc_id: str
    tick: int
    new_summaries: list[ConsolidatedMemory]
    events_processed: int
    categories_consolidated: list[str]


# ---------------------------------------------------------------------------
# MemoryConsolidator
# ---------------------------------------------------------------------------


class MemoryConsolidator:
    """
    Batches raw NPC memory events into condensed summaries.

    Usage::

        consolidator = MemoryConsolidator()
        result = await consolidator.consolidate(
            npc_id="42",
            raw_memories=[{"event_type": "trade", "tick": 150, ...}, ...],
            tick=200,
        )
    """

    def __init__(self) -> None:
        from academy.models.router import ModelRouter

        self._router = ModelRouter()
        # In-memory store of consolidated memories per NPC.
        # In production this would be written to/read from pgvector.
        self._store: dict[str, list[ConsolidatedMemory]] = {}
        # Track the last consolidation tick per NPC
        self._last_consolidation: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_consolidate(
        self,
        npc_id: str,
        current_tick: int,
        last_consolidation_tick: int | None = None,
    ) -> bool:
        """
        Return True if it is time to consolidate this NPC's memories.

        Uses a 50-tick interval.  ``last_consolidation_tick`` may be provided
        directly; if omitted the internal record is consulted.
        """
        if last_consolidation_tick is None:
            last_consolidation_tick = self._last_consolidation.get(npc_id, -CONSOLIDATION_INTERVAL)
        return (current_tick - last_consolidation_tick) >= CONSOLIDATION_INTERVAL

    async def consolidate(
        self,
        npc_id: str,
        raw_memories: list[dict[str, Any]],
        tick: int,
    ) -> ConsolidationResult:
        """
        Group raw memories by category, summarise categories with >10 events,
        and store summaries in pgvector.

        Parameters
        ----------
        npc_id:
            Unique NPC identifier.
        raw_memories:
            List of raw event dicts, each with at least ``event_type`` and
            optionally ``tick``, ``description``, ``outcome``, etc.
        tick:
            Current simulation tick.

        Returns
        -------
        ConsolidationResult
        """
        # Group events by category
        by_category: dict[str, list[dict[str, Any]]] = {cat: [] for cat in MEMORY_CATEGORIES}
        for event in raw_memories:
            cat = self._categorise(event)
            by_category[cat].append(event)

        new_summaries: list[ConsolidatedMemory] = []
        categories_consolidated: list[str] = []
        events_processed = 0

        for category, events in by_category.items():
            if len(events) < MIN_EVENTS_PER_CATEGORY:
                continue  # not enough events to warrant summarisation

            summary_text = await self._summarise_category(npc_id, category, events, tick)
            embedding = await self._embed(summary_text)

            ticks_in_batch = [e.get("tick", tick) for e in events if isinstance(e.get("tick"), int)]
            tick_range = (min(ticks_in_batch, default=tick), max(ticks_in_batch, default=tick))

            mem = ConsolidatedMemory(
                npc_id=npc_id,
                category=category,
                summary_text=summary_text,
                event_count=len(events),
                tick_range=tick_range,
                embedding=embedding,
                importance_score=CONSOLIDATED_IMPORTANCE,
            )
            new_summaries.append(mem)
            categories_consolidated.append(category)
            events_processed += len(events)

            # Persist to in-memory store (pgvector in production)
            if npc_id not in self._store:
                self._store[npc_id] = []
            self._store[npc_id].append(mem)

            # Mark raw events as consolidated by adding a flag
            for event in events:
                event["consolidated"] = True

        # Update last consolidation tick
        self._last_consolidation[npc_id] = tick

        return ConsolidationResult(
            npc_id=npc_id,
            tick=tick,
            new_summaries=new_summaries,
            events_processed=events_processed,
            categories_consolidated=categories_consolidated,
        )

    def get_consolidated_memories(
        self,
        npc_id: str,
        limit: int = 10,
    ) -> list[ConsolidatedMemory]:
        """
        Return up to ``limit`` consolidated memories for an NPC, ordered by
        importance_score descending (most relevant first).

        In a production system these would be fetched from pgvector using
        embedding similarity; here we return the stored summaries ordered
        by importance (consistent with the specification's "higher retrieval
        weight" requirement).
        """
        all_mems = self._store.get(npc_id, [])
        # Sort by importance descending, then by recency (tick_range end)
        sorted_mems = sorted(
            all_mems,
            key=lambda m: (m.importance_score, m.tick_range[1]),
            reverse=True,
        )
        return sorted_mems[:limit]

    # ------------------------------------------------------------------
    # Kafka integration helpers
    # ------------------------------------------------------------------

    async def handle_kafka_trigger(self, payload: dict[str, Any]) -> None:
        """
        Handle a ``npc.memory.consolidate`` Kafka message.

        Expected payload keys: npc_id, raw_memories (list), tick.
        Publishes a ``npc.memory.consolidated`` message on completion.
        """
        npc_id = str(payload.get("npc_id", ""))
        raw_memories = payload.get("raw_memories", [])
        tick = int(payload.get("tick", 0))

        if not npc_id:
            logger.warning("Received consolidation trigger with missing npc_id")
            return

        result = await self.consolidate(npc_id, raw_memories, tick)

        await self._publish_result(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _categorise(event: dict[str, Any]) -> str:
        """Map a raw event to one of the five memory categories."""
        event_type = event.get("event_type", "").lower()
        category_keywords: dict[str, list[str]] = {
            "trade": ["trade", "buy", "sell", "market", "barter", "coin"],
            "social": ["social", "talk", "gossip", "chat", "meet", "greet", "friend", "reputation"],
            "travel": ["travel", "walk", "journey", "move", "explore", "road"],
            "combat": ["combat", "fight", "attack", "battle", "wound", "kill", "defend"],
            "work": ["work", "craft", "build", "farm", "harvest", "labour", "job"],
        }
        for cat, keywords in category_keywords.items():
            if any(kw in event_type for kw in keywords):
                return cat
        return "work"  # default category

    async def _summarise_category(
        self,
        npc_id: str,
        category: str,
        events: list[dict[str, Any]],
        tick: int,
    ) -> str:
        """Call ModelRouter(task_type='memory_summary') to produce a concise summary."""
        system_prompt = (
            "You are a memory consolidator for an NPC in a medieval town simulation. "
            "Summarise the provided list of events into 2-3 sentences capturing "
            "the most significant patterns and outcomes. Be concise and factual."
        )

        # Truncate event list to avoid overwhelming the model
        sample = events[:20]
        events_text = "\n".join(
            f"- tick {e.get('tick', '?')}: {e.get('event_type', 'unknown')} — "
            f"{e.get('description', e.get('outcome', ''))}"
            for e in sample
        )
        prompt = (
            f"NPC {npc_id} — {category} memories (current tick: {tick}):\n"
            f"{events_text}\n\n"
            "Write a concise summary of this NPC's {category} experiences."
        )

        try:
            summary = await self._router.route("memory_summary", prompt, system=system_prompt)
            return summary.strip()[:1000]  # cap summary length
        except Exception as exc:
            logger.warning("Memory summary failed for %s/%s: %s", npc_id, category, exc)
            return (
                f"NPC {npc_id} had {len(events)} {category} events between "
                f"tick {events[0].get('tick', '?')} and tick {events[-1].get('tick', '?')}."
            )

    async def _embed(self, text: str) -> list[float]:
        """Embed a summary string via OllamaClient."""
        try:
            from academy.ollama_client import OllamaClient

            client = OllamaClient()
            return await client.embed(text)
        except Exception as exc:
            logger.warning("Embedding failed: %s — using zero vector", exc)
            return [0.0] * 768  # nomic-embed-text is 768-dimensional

    async def _publish_result(self, result: ConsolidationResult) -> None:
        """Publish consolidation result to the npc.memory.consolidated Kafka topic."""
        try:
            from academy.kafka_producer import get_producer

            producer = await get_producer()
            payload: dict[str, Any] = {
                "npc_id": result.npc_id,
                "tick": result.tick,
                "events_processed": result.events_processed,
                "categories_consolidated": result.categories_consolidated,
                "summary_count": len(result.new_summaries),
                "summaries": [
                    {
                        "category": m.category,
                        "summary_text": m.summary_text,
                        "event_count": m.event_count,
                        "tick_range": list(m.tick_range),
                        "importance_score": m.importance_score,
                    }
                    for m in result.new_summaries
                ],
                "timestamp": time.time(),
            }
            await producer._send(TOPIC_CONSOLIDATED_RESULT, payload, key=result.npc_id)
            logger.info(
                "Published consolidation result for NPC %s (%d categories)",
                result.npc_id,
                len(result.categories_consolidated),
            )
        except Exception as exc:
            logger.warning("Failed to publish consolidation result: %s", exc)
