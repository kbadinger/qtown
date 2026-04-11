"""
Full gRPC server implementation for the Academy service.

Implements all RPCs defined in proto/qtown/academy.proto:
  - Health
  - NPCDecide
  - GenerateDialogue
  - GenerateNewspaper
  - SearchHistory
  - GetModelStats
  - NPCArrive / NPCDepart (travel)

Runs on port 50053 (configurable via GRPC_PORT env var).
Each RPC records cost metrics via cost_tracker.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from concurrent import futures
from typing import Any

import grpc

from academy.qtown import academy_pb2, academy_pb2_grpc, common_pb2
from academy.models.router import ModelRouter
from academy.rag.retriever import TownHistoryRetriever

logger = logging.getLogger("academy.grpc_server")

GRPC_PORT = int(os.environ.get("GRPC_PORT", "50053"))
GRPC_MAX_WORKERS = int(os.environ.get("GRPC_MAX_WORKERS", "10"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ms(t0: float) -> float:
    """Return elapsed milliseconds since monotonic timestamp t0."""
    return (time.monotonic() - t0) * 1000.0


# ---------------------------------------------------------------------------
# Servicer implementation
# ---------------------------------------------------------------------------


class AcademyServicer(academy_pb2_grpc.AcademyServicer):
    """
    Full implementation of the Academy gRPC service.

    Each RPC:
      1. Validates input
      2. Calls the appropriate ModelRouter / RAG component
      3. Records cost metrics
      4. Returns the proto response
    """

    def __init__(self) -> None:
        self._router = ModelRouter()
        self._retriever = TownHistoryRetriever()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def Health(
        self, request: common_pb2.HealthRequest, context: grpc.ServicerContext
    ) -> common_pb2.HealthResponse:
        return common_pb2.HealthResponse(
            status="ok",
            service="academy",
            version="2.0.0",
            details={
                "grpc_port": str(GRPC_PORT),
                "model_router": "ready",
            },
        )

    # ------------------------------------------------------------------
    # GenerateDialogue
    # ------------------------------------------------------------------

    def GenerateDialogue(
        self, request: academy_pb2.DialogueRequest, context: grpc.ServicerContext
    ) -> academy_pb2.DialogueResponse:
        """Generate a multi-turn dialogue between two NPCs."""
        t0 = time.monotonic()

        npc_a = request.npc_id_a
        npc_b = request.npc_id_b
        tone = request.tone or "friendly"
        ctx = request.context or "They meet in the town square."

        system_prompt = (
            "You are a dialogue writer for a medieval fantasy town simulation. "
            "Write natural, character-appropriate dialogue. "
            "Return exactly 4 lines, alternating between NPC A and NPC B. "
            "Format each line as: NPC_ID|EMOTION|TEXT"
        )
        user_prompt = (
            f"Write a {tone} conversation between NPC #{npc_a} and NPC #{npc_b}.\n"
            f"Context: {ctx}\n"
            "Format: NPC_ID|EMOTION|TEXT (one line per speaker, 4 lines total)"
        )

        loop = asyncio.new_event_loop()
        try:
            raw_response, model_used = loop.run_until_complete(
                self._generate_dialogue_async(user_prompt, system_prompt, tone)
            )
        finally:
            loop.close()

        latency_ms = _ms(t0)

        lines = self._parse_dialogue_lines(raw_response, npc_a, npc_b)

        # Record cost asynchronously (best-effort)
        self._record_cost_sync("npc_dialogue", model_used, 0, 0, latency_ms)

        # Embed dialogue for RAG
        self._embed_dialogue_sync(
            f"dialogue-{npc_a}-{npc_b}-{int(time.time())}",
            lines,
            {"npc_a": npc_a, "npc_b": npc_b, "tone": tone},
        )

        return academy_pb2.DialogueResponse(
            lines=lines,
            model_used=model_used,
            latency_ms=latency_ms,
        )

    async def _generate_dialogue_async(
        self, prompt: str, system: str, tone: str
    ) -> tuple[str, str]:
        task_type = "npc_dialogue"
        cfg = self._router.ROUTES.get(task_type, self._router.ROUTES["npc_chatter"])
        response = await self._router.route(task_type, prompt, system=system)
        return response, cfg.model_id

    def _parse_dialogue_lines(
        self,
        raw: str,
        npc_a: int,
        npc_b: int,
    ) -> list[academy_pb2.DialogueLine]:
        """
        Parse LLM output into DialogueLine protos.

        Expected format per line: ``NPC_ID|EMOTION|TEXT``
        Falls back to alternating NPC assignment if format is unrecognised.
        """
        lines: list[academy_pb2.DialogueLine] = []
        speakers = [npc_a, npc_b]
        speaker_idx = 0

        for raw_line in raw.strip().splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            parts = raw_line.split("|")
            if len(parts) >= 3:
                try:
                    npc_id = int(parts[0].strip().replace("NPC", "").replace("#", "").strip())
                except ValueError:
                    npc_id = speakers[speaker_idx % 2]
                emotion = parts[1].strip()
                text = "|".join(parts[2:]).strip()
            elif len(parts) == 2:
                npc_id = speakers[speaker_idx % 2]
                emotion = parts[0].strip()
                text = parts[1].strip()
            else:
                npc_id = speakers[speaker_idx % 2]
                emotion = "neutral"
                text = raw_line

            lines.append(
                academy_pb2.DialogueLine(npc_id=npc_id, text=text, emotion=emotion)
            )
            speaker_idx += 1

        return lines[:8]  # cap at 8 lines

    # ------------------------------------------------------------------
    # GenerateNewspaper
    # ------------------------------------------------------------------

    def GenerateNewspaper(
        self, request: academy_pb2.NewspaperRequest, context: grpc.ServicerContext
    ) -> academy_pb2.NewspaperResponse:
        """Generate newspaper articles for the current game tick."""
        t0 = time.monotonic()
        tick = request.tick
        max_articles = request.max_articles or 3

        loop = asyncio.new_event_loop()
        try:
            articles_data, model_used = loop.run_until_complete(
                self._generate_newspaper_async(tick, max_articles)
            )
        finally:
            loop.close()

        latency_ms = _ms(t0)
        self._record_cost_sync("newspaper", model_used, 0, 0, latency_ms)

        articles = [
            academy_pb2.Article(
                headline=a["headline"],
                body=a["body"],
                category=a.get("category", "general"),
            )
            for a in articles_data
        ]

        # Embed articles for RAG
        for i, article in enumerate(articles_data):
            self._embed_article_sync(
                f"newspaper-tick{tick}-{i}",
                article["headline"],
                article["body"],
                tick,
                article.get("category", "general"),
            )

        return academy_pb2.NewspaperResponse(
            articles=articles,
            model_used=model_used,
            latency_ms=latency_ms,
        )

    async def _generate_newspaper_async(
        self, tick: int, max_articles: int
    ) -> tuple[list[dict[str, Any]], str]:
        system = (
            "You are the editor of The Qtown Gazette, a medieval fantasy newspaper. "
            "Write concise, engaging articles about events in a simulated town. "
            "Each article should feel grounded in a living world."
        )
        prompt = (
            f"Generate {max_articles} newspaper articles for Tick {tick} of Qtown. "
            "Include a mix of: economy, crime, weather, politics. "
            "For each article output:\n"
            "HEADLINE: ...\nCATEGORY: ...\nBODY: ...\n---\n"
            f"Generate all {max_articles} articles now."
        )

        cfg = self._router.ROUTES["newspaper"]
        raw = await self._router.route("newspaper", prompt, system=system)
        articles = self._parse_articles(raw)

        # Ensure we have at least one article
        if not articles:
            articles = [
                {
                    "headline": f"Quiet Day in Qtown (Tick {tick})",
                    "body": "The town was peaceful today with little to report.",
                    "category": "general",
                }
            ]
        return articles[:max_articles], cfg.model_id

    def _parse_articles(self, raw: str) -> list[dict[str, Any]]:
        """Parse LLM output into a list of article dicts."""
        articles: list[dict[str, Any]] = []
        current: dict[str, Any] = {}

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue

            if line == "---":
                if current.get("headline"):
                    articles.append(current)
                current = {}
                continue

            if line.upper().startswith("HEADLINE:"):
                current["headline"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("CATEGORY:"):
                current["category"] = line.split(":", 1)[1].strip().lower()
            elif line.upper().startswith("BODY:"):
                current["body"] = line.split(":", 1)[1].strip()
            elif "body" in current:
                # continuation of body
                current["body"] = current["body"] + " " + line

        if current.get("headline"):
            articles.append(current)

        return articles

    # ------------------------------------------------------------------
    # SearchHistory (RAG)
    # ------------------------------------------------------------------

    def SearchHistory(
        self, request: academy_pb2.SearchHistoryRequest, context: grpc.ServicerContext
    ) -> academy_pb2.SearchHistoryResponse:
        """RAG-powered semantic search over town history."""
        t0 = time.monotonic()
        query = request.query
        top_k = request.top_k or 5

        if not query:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("query must not be empty")
            return academy_pb2.SearchHistoryResponse()

        loop = asyncio.new_event_loop()
        try:
            docs = loop.run_until_complete(self._retriever.search(query, k=top_k))
        except Exception as exc:
            logger.error("SearchHistory failed: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return academy_pb2.SearchHistoryResponse()
        finally:
            loop.close()

        search_latency_ms = _ms(t0)

        results = [
            academy_pb2.SearchResult(
                event_id=int(d.metadata.get("event_id", 0)) if d.metadata.get("event_id") else 0,
                text=d.content,
                score=d.final_score,
                tick=int(d.metadata.get("tick", 0)) if d.metadata.get("tick") else 0,
                event_type=d.metadata.get("event_type", d.doc_type),
            )
            for d in docs
        ]

        return academy_pb2.SearchHistoryResponse(
            results=results,
            search_latency_ms=search_latency_ms,
        )

    # ------------------------------------------------------------------
    # NPCDecide
    # ------------------------------------------------------------------

    def NPCDecide(
        self, request: academy_pb2.NPCDecideRequest, context: grpc.ServicerContext
    ) -> academy_pb2.NPCDecideResponse:
        """Run the LangGraph NPC decision agent."""
        t0 = time.monotonic()
        npc_state = request.npc_state
        tick = request.current_tick
        ctx_events = list(request.context)

        event_data = {
            "tick": tick,
            "context": ctx_events,
            "npc_name": npc_state.name,
            "occupation": npc_state.occupation,
        }

        loop = asyncio.new_event_loop()
        try:
            from academy.agents.npc import run_npc_cycle
            result = loop.run_until_complete(run_npc_cycle(str(npc_state.id), event_data))
        except Exception as exc:
            logger.error("NPCDecide agent error: %s", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return academy_pb2.NPCDecideResponse()
        finally:
            loop.close()

        latency_ms = _ms(t0)

        return academy_pb2.NPCDecideResponse(
            decision=result.decision,
            narration=result.narration,
            model_used="langgraph+deepseek-r1:14b",
            latency_ms=latency_ms,
            trace=[],
        )

    # ------------------------------------------------------------------
    # GetModelStats
    # ------------------------------------------------------------------

    def GetModelStats(
        self, request: academy_pb2.ModelStatsRequest, context: grpc.ServicerContext
    ) -> academy_pb2.ModelStatsResponse:
        """Return aggregate model routing statistics."""
        stats = self._router.get_routing_stats()
        total = max(stats["total_requests"], 1)

        by_model = [
            academy_pb2.ModelUsage(
                model_name=m["model_name"],
                request_count=m["request_count"],
                avg_latency_ms=m["avg_latency_ms"],
                cost_usd=m["cost_usd"],
            )
            for m in stats.get("by_model", [])
        ]

        return academy_pb2.ModelStatsResponse(
            total_requests=stats["total_requests"],
            local_pct=stats["local_pct"],
            cloud_pct=stats["cloud_pct"],
            cost_today_usd=stats["cost_today_usd"],
            by_model=by_model,
        )

    # ------------------------------------------------------------------
    # Travel RPCs
    # ------------------------------------------------------------------

    def NPCArrive(
        self, request: common_pb2.TravelRequest, context: grpc.ServicerContext
    ) -> common_pb2.TravelResponse:
        """Accept NPC arrival — log and acknowledge."""
        logger.info(
            "NPC %d arrived from %s", request.npc_id, getattr(request, 'from', request.npc_id)
        )
        return common_pb2.TravelResponse(accepted=True, eta_ticks=0)

    def NPCDepart(
        self, request: common_pb2.TravelRequest, context: grpc.ServicerContext
    ) -> common_pb2.TravelResponse:
        """Accept NPC departure — log and acknowledge."""
        logger.info(
            "NPC %d departing to %s", request.npc_id, request.to
        )
        return common_pb2.TravelResponse(accepted=True, eta_ticks=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_cost_sync(
        self,
        task_type: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
    ) -> None:
        """Fire-and-forget cost record in a new event loop."""
        from academy.cost_tracker import record_request
        from academy.models.router import ROUTE_TABLE

        cfg = ROUTE_TABLE.get(task_type)
        cost_per_1k = cfg.cost_per_1k_tokens if cfg else 0.0
        total_tokens = tokens_in + tokens_out
        cost_usd = (total_tokens / 1000.0) * cost_per_1k

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                record_request(
                    task_type=task_type,
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )
            )
        except Exception as exc:
            logger.debug("Cost record failed (non-critical): %s", exc)
        finally:
            loop.close()

    def _embed_dialogue_sync(
        self,
        dialogue_id: str,
        lines: list[academy_pb2.DialogueLine],
        metadata: dict[str, Any],
    ) -> None:
        """Best-effort background embedding for dialogue."""
        from academy.rag.embeddings import get_dialogue_embedder

        lines_dicts = [{"npc_id": ln.npc_id, "text": ln.text} for ln in lines]
        loop = asyncio.new_event_loop()
        try:
            embedder = get_dialogue_embedder()
            loop.run_until_complete(embedder.process_dialogue(dialogue_id, lines_dicts, metadata))
        except Exception as exc:
            logger.debug("Dialogue embedding failed (non-critical): %s", exc)
        finally:
            loop.close()

    def _embed_article_sync(
        self,
        article_id: str,
        headline: str,
        body: str,
        tick: int,
        category: str,
    ) -> None:
        """Best-effort background embedding for newspaper articles."""
        from academy.rag.embeddings import get_newspaper_embedder

        loop = asyncio.new_event_loop()
        try:
            embedder = get_newspaper_embedder()
            loop.run_until_complete(
                embedder.process_article(article_id, headline, body, tick, category)
            )
        except Exception as exc:
            logger.debug("Article embedding failed (non-critical): %s", exc)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def create_server(port: int = GRPC_PORT) -> grpc.Server:
    """Create and configure the gRPC server (does not start it)."""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=GRPC_MAX_WORKERS),
        options=[
            ("grpc.max_send_message_length", 16 * 1024 * 1024),   # 16 MB
            ("grpc.max_receive_message_length", 16 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 10_000),
            ("grpc.keepalive_timeout_ms", 5_000),
            ("grpc.keepalive_permit_without_calls", True),
        ],
    )
    academy_pb2_grpc.add_AcademyServicer_to_server(AcademyServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    return server


def serve(port: int = GRPC_PORT) -> None:
    """Blocking: start the gRPC server and wait for termination."""
    server = create_server(port)
    server.start()
    logger.info("Academy gRPC server started on port %d", port)
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    serve()
