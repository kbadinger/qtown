"""
Grounded RAG answering (W1-A1/A2).

The missing join between retrieval and generation: retrieve the top-k passages,
inject them as *numbered* sources, and have the model answer **only** from them,
citing the sources it used. Output is structured (Ollama format=json + Pydantic
validation with a retry), not regex-scraped — so a citation is a real source id,
not a guess.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    from academy.rag.retriever import Document

logger = logging.getLogger("academy.rag.answer")

RAG_ANSWER_MODEL = os.environ.get("RAG_ANSWER_MODEL", "qwen3.5:4b")
RETRIEVE_K = 5
MAX_ATTEMPTS = 2  # A2: retry once on invalid structured output

_SYSTEM = (
    "You are qtown's archivist. Answer the question using ONLY the numbered sources "
    "provided. Cite every source you rely on by its number. If the sources do not "
    "contain the answer, say you don't have that information — never invent facts."
)


class _AnswerSchema(BaseModel):
    """The structured shape the model must return."""

    answer: str
    citations: list[int] = Field(default_factory=list)


@dataclass
class Citation:
    n: int
    doc_id: str
    source: str
    heading: str
    snippet: str
    score: float


@dataclass
class GroundedAnswer:
    question: str
    answer: str
    citations: list[Citation]
    model: str
    retrieved: int
    grounded: bool
    latency_ms: float

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "answer": self.answer,
            "grounded": self.grounded,
            "model": self.model,
            "retrieved": self.retrieved,
            "latency_ms": self.latency_ms,
            "citations": [
                {
                    "n": c.n,
                    "doc_id": c.doc_id,
                    "source": c.source,
                    "heading": c.heading,
                    "snippet": c.snippet,
                    "score": round(c.score, 4),
                }
                for c in self.citations
            ],
        }


def _build_prompt(question: str, docs: list["Document"]) -> str:
    lines = ["Sources:"]
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("source", d.doc_id)
        lines.append(f"[{i}] ({src}) {d.content}")
    lines.append("")
    lines.append(f"Question: {question}")
    lines.append(
        'Respond with a JSON object: '
        '{"answer": "<answer that cites sources as [n]>", '
        '"citations": [<the source numbers you used>]}'
    )
    return "\n".join(lines)


def _parse(raw: str) -> _AnswerSchema | None:
    """Parse the model output into the schema; tolerate stray text around JSON."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return _AnswerSchema.model_validate_json(raw)
    except ValidationError:
        pass
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return _AnswerSchema.model_validate_json(m.group(0))
        except (ValidationError, json.JSONDecodeError):
            return None
    return None


class GroundedAnswerer:
    """retrieve → inject numbered sources → generate structured, cited answer."""

    def __init__(self) -> None:
        from academy.ollama_client import get_client
        from academy.rag.retriever import get_retriever

        self._retriever = get_retriever()
        self._ollama = get_client()

    async def answer(
        self, question: str, *, k: int = RETRIEVE_K, model: str | None = None
    ) -> GroundedAnswer:
        model = model or RAG_ANSWER_MODEL
        docs = await self._retriever.search(question, k=k)

        if not docs:
            return GroundedAnswer(
                question=question,
                answer="I don't have information on that in the town archive.",
                citations=[],
                model=model,
                retrieved=0,
                grounded=False,
                latency_ms=0.0,
            )

        prompt = _build_prompt(question, docs)
        parsed: _AnswerSchema | None = None
        latency_ms = 0.0

        for attempt in range(MAX_ATTEMPTS):
            meta = await self._ollama.generate_with_metadata(
                model,
                prompt,
                system=_SYSTEM,
                temperature=0.2,
                max_tokens=700,
                format="json",
                think=False,
            )
            latency_ms += float(meta.get("latency_ms", 0.0))
            parsed = _parse(str(meta.get("response", "")))
            if parsed is not None and parsed.answer.strip():
                break
            logger.warning("RAG answer: invalid structured output (attempt %d)", attempt + 1)

        if parsed is None or not parsed.answer.strip():
            # Honest failure — do not fabricate an answer.
            return GroundedAnswer(
                question=question,
                answer="I couldn't produce a grounded answer from the retrieved sources.",
                citations=[],
                model=model,
                retrieved=len(docs),
                grounded=False,
                latency_ms=round(latency_ms, 2),
            )

        citations: list[Citation] = []
        for n in parsed.citations:
            if 1 <= n <= len(docs):
                d = docs[n - 1]
                citations.append(
                    Citation(
                        n=n,
                        doc_id=d.doc_id,
                        source=str(d.metadata.get("source", d.doc_id)),
                        heading=str(d.metadata.get("heading", "")),
                        snippet=d.content[:240],
                        score=float(d.final_score or d.similarity),
                    )
                )

        return GroundedAnswer(
            question=question,
            answer=parsed.answer.strip(),
            citations=citations,
            model=model,
            retrieved=len(docs),
            grounded=len(citations) > 0,
            latency_ms=round(latency_ms, 2),
        )


_answerer: GroundedAnswerer | None = None


def get_answerer() -> GroundedAnswerer:
    global _answerer
    if _answerer is None:
        _answerer = GroundedAnswerer()
    return _answerer
