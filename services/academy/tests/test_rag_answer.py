"""Unit tests for the grounded RAG answerer (W1-A1/A2).

The retriever and Ollama client are mocked, so these run in CI without a live DB
or model — they lock the structured-output parsing, citation mapping, and the
honest "not grounded" behaviour.
"""

import asyncio
from unittest.mock import AsyncMock

from academy.rag.answer import GroundedAnswerer, _parse
from academy.rag.retriever import Document


def _doc(i: int, source: str, content: str) -> Document:
    return Document(
        doc_id=f"{source}#{i}",
        doc_type="doc",
        content=content,
        metadata={"source": source, "heading": "H"},
        similarity=0.9,
        final_score=0.9,
    )


def _answerer(docs: list[Document], response: str) -> GroundedAnswerer:
    # Bypass __init__ (which wires real singletons) and inject mocks.
    a = GroundedAnswerer.__new__(GroundedAnswerer)
    a._retriever = AsyncMock()
    a._retriever.search = AsyncMock(return_value=docs)
    a._ollama = AsyncMock()
    a._ollama.generate_with_metadata = AsyncMock(
        return_value={"response": response, "latency_ms": 12.0}
    )
    return a


def test_grounded_answer_maps_citations() -> None:
    docs = [
        _doc(0, "docs/adr/0001.md", "settlement is at-least-once + idempotent on (trade_id, npc_id)"),
        _doc(1, "services/market-district/README.md", "order book"),
    ]
    a = _answerer(docs, '{"answer": "Settlement is at-least-once [1].", "citations": [1]}')
    res = asyncio.run(a.answer("what guarantees?"))

    assert res.grounded is True
    assert res.retrieved == 2
    assert res.answer.startswith("Settlement")
    assert len(res.citations) == 1
    assert res.citations[0].n == 1
    assert res.citations[0].source == "docs/adr/0001.md"


def test_no_docs_is_not_grounded_and_does_not_fabricate() -> None:
    a = _answerer([], "")
    res = asyncio.run(a.answer("something not in the corpus"))
    assert res.grounded is False
    assert res.retrieved == 0
    # ollama must not even be called when nothing is retrieved
    a._ollama.generate_with_metadata.assert_not_awaited()


def test_out_of_range_citations_are_dropped() -> None:
    docs = [_doc(0, "a.md", "content")]
    a = _answerer(docs, '{"answer": "ans [1]", "citations": [1, 5, 0]}')
    res = asyncio.run(a.answer("q"))
    assert [c.n for c in res.citations] == [1]  # 5 and 0 are out of range


def test_invalid_structured_output_is_not_grounded() -> None:
    docs = [_doc(0, "a.md", "content")]
    a = _answerer(docs, "this is not json at all")
    res = asyncio.run(a.answer("q"))
    assert res.grounded is False
    assert res.citations == []


def test_parse_tolerates_stray_text_around_json() -> None:
    parsed = _parse('Sure! {"answer": "x", "citations": [2]} done')
    assert parsed is not None
    assert parsed.answer == "x"
    assert parsed.citations == [2]


def test_parse_rejects_garbage() -> None:
    assert _parse("no json here") is None
    assert _parse("") is None
