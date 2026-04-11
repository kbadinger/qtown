"""
Reranker for the Academy RAG pipeline.

Strategy:
  1. Retrieve top-K (default 20) candidates from pgvector similarity search.
  2. Rerank using a cross-encoder prompt sent to Ollama (fast local model).
  3. Fall back to BM25 term-overlap scoring if Ollama is unavailable.
  4. Return top-N (default 5) results with final scores.

Cross-encoder prompt asks the local model to score relevance 0-10 for each
candidate; results are normalised to [0, 1].
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

logger = logging.getLogger("academy.rag.reranker")

RERANK_TOP_K = 20     # how many candidates to feed the reranker
RERANK_TOP_N = 5      # how many to return after reranking
RERANK_MODEL = "qwen3-coder-next"  # fast local model for scoring


# ---------------------------------------------------------------------------
# BM25 fallback
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Simple whitespace + punctuation tokeniser."""
    return re.findall(r"\b\w+\b", text.lower())


def bm25_score(
    query_terms: list[str],
    doc_terms: list[str],
    k1: float = 1.5,
    b: float = 0.75,
    avg_doc_len: float = 50.0,
) -> float:
    """
    Compute a single BM25 score for a document against a query.

    Uses a simplified single-document formulation (no IDF correction).
    """
    doc_len = len(doc_terms)
    tf_map = Counter(doc_terms)
    score = 0.0
    for term in query_terms:
        tf = tf_map.get(term, 0)
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += numerator / max(denominator, 1e-9)
    return score


# ---------------------------------------------------------------------------
# Document container
# ---------------------------------------------------------------------------


class RankedResult:
    """A reranked search result with a normalised relevance score."""

    __slots__ = ("doc_id", "doc_type", "content", "metadata", "vector_score", "final_score")

    def __init__(
        self,
        doc_id: str,
        doc_type: str,
        content: str,
        metadata: dict[str, Any],
        vector_score: float,
        final_score: float = 0.0,
    ) -> None:
        self.doc_id = doc_id
        self.doc_type = doc_type
        self.content = content
        self.metadata = metadata
        self.vector_score = vector_score
        self.final_score = final_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "content": self.content,
            "metadata": self.metadata,
            "vector_score": self.vector_score,
            "final_score": self.final_score,
        }


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------


class Reranker:
    """
    Two-stage reranker: cross-encoder via Ollama → BM25 fallback.

    Usage::

        reranker = Reranker()
        results = await reranker.rerank(query, candidates, top_n=5)
    """

    def __init__(self, model: str = RERANK_MODEL) -> None:
        self.model = model

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_n: int = RERANK_TOP_N,
    ) -> list[RankedResult]:
        """
        Rerank ``candidates`` against ``query``.

        ``candidates`` is a list of dicts with at minimum:
          ``doc_id``, ``doc_type``, ``content``, ``metadata``, ``similarity``

        Returns up to ``top_n`` RankedResult objects sorted by final_score desc.
        """
        if not candidates:
            return []

        # Attempt cross-encoder reranking; fall back to BM25 on error
        try:
            return await self._cross_encoder_rerank(query, candidates, top_n=top_n)
        except Exception as exc:
            logger.warning("Cross-encoder rerank failed (%s) — falling back to BM25", exc)
            return self._bm25_rerank(query, candidates, top_n=top_n)

    # ------------------------------------------------------------------
    # Cross-encoder via Ollama
    # ------------------------------------------------------------------

    async def _cross_encoder_rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_n: int,
    ) -> list[RankedResult]:
        """
        Ask a local LLM to score each candidate's relevance to the query.

        The prompt requests a JSON array of integer scores (0-10).
        """
        from academy.ollama_client import OllamaClient

        client = OllamaClient()

        # Build a compact prompt listing all candidates
        candidate_block = "\n".join(
            f"{i + 1}. {c['content'][:200]}" for i, c in enumerate(candidates)
        )

        prompt = (
            f"Query: {query}\n\n"
            "Score each passage's relevance to the query on a scale 0-10 "
            "(10 = perfectly relevant, 0 = completely irrelevant).\n"
            f"Passages:\n{candidate_block}\n\n"
            "Respond ONLY with a JSON array of integers, one per passage, e.g. [7,3,9,2]."
        )

        raw = await client.generate(
            self.model,
            prompt,
            temperature=0.0,
            max_tokens=64,
        )

        scores = self._parse_scores(raw, expected_count=len(candidates))
        max_score = max(scores) if scores else 10

        ranked = [
            RankedResult(
                doc_id=c["doc_id"],
                doc_type=c.get("doc_type", ""),
                content=c["content"],
                metadata=c.get("metadata", {}),
                vector_score=float(c.get("similarity", 0.0)),
                final_score=score / max(max_score, 1),
            )
            for c, score in zip(candidates, scores)
        ]
        ranked.sort(key=lambda r: r.final_score, reverse=True)
        return ranked[:top_n]

    @staticmethod
    def _parse_scores(raw: str, expected_count: int) -> list[float]:
        """
        Extract a list of numeric scores from LLM output.

        Falls back to all-zeros if parsing fails.
        """
        try:
            import json

            # Find the first [...] block
            match = re.search(r"\[([^\]]+)\]", raw)
            if match:
                scores = json.loads(f"[{match.group(1)}]")
                scores = [float(s) for s in scores]
                if len(scores) == expected_count:
                    return scores
        except Exception:
            pass

        # Try scanning for standalone numbers
        nums = re.findall(r"\b([0-9]+(?:\.[0-9]+)?)\b", raw)
        if len(nums) == expected_count:
            return [float(n) for n in nums]

        logger.debug("Could not parse %d scores from: %r", expected_count, raw)
        return [0.0] * expected_count

    # ------------------------------------------------------------------
    # BM25 fallback
    # ------------------------------------------------------------------

    def _bm25_rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_n: int,
    ) -> list[RankedResult]:
        """Pure-Python BM25 reranking — no external deps."""
        query_terms = _tokenise(query)
        all_doc_terms = [_tokenise(c["content"]) for c in candidates]
        avg_len = sum(len(t) for t in all_doc_terms) / max(len(all_doc_terms), 1)

        raw_scores = [
            bm25_score(query_terms, doc_terms, avg_doc_len=avg_len)
            for doc_terms in all_doc_terms
        ]
        max_raw = max(raw_scores) if raw_scores else 1.0

        ranked = [
            RankedResult(
                doc_id=c["doc_id"],
                doc_type=c.get("doc_type", ""),
                content=c["content"],
                metadata=c.get("metadata", {}),
                vector_score=float(c.get("similarity", 0.0)),
                final_score=score / max(max_raw, 1e-9),
            )
            for c, score in zip(candidates, raw_scores)
        ]
        ranked.sort(key=lambda r: r.final_score, reverse=True)
        return ranked[:top_n]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
