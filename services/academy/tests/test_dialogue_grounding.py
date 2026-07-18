"""Unit tests for GenerateDialogue's town-history grounding (grounding slice 3).

Tests the pure injection/attribution helpers directly, so no gRPC/Kafka/DB.
"""
from academy.grpc_server import AcademyServicer
from academy.rag.retriever import Document


def _event(doc_id: str, content: str, meta: dict) -> Document:
    return Document(
        doc_id=doc_id, doc_type="event", content=content,
        metadata=meta, similarity=0.8, final_score=0.8,
    )


def test_prompt_injects_town_history() -> None:
    hist = [_event("42", "[Tick 5] fire — A fire broke out in the market", {"tick": 5})]
    prompt = AcademyServicer._build_dialogue_prompt(1, 2, "friendly", "They meet.", hist)
    assert "Recent town history" in prompt
    assert "A fire broke out in the market" in prompt


def test_prompt_without_history_has_no_block() -> None:
    prompt = AcademyServicer._build_dialogue_prompt(1, 2, "friendly", "They meet.", [])
    assert "Recent town history" not in prompt
    assert "Context: They meet." in prompt


def test_history_refs_are_attributable() -> None:
    hist = [
        _event("42", "[Tick 5] fire — blaze", {"event_id": "42", "tick": 5, "event_type": "fire"})
    ]
    refs = AcademyServicer._history_refs(hist)
    assert refs[0]["event_id"] == "42"
    assert refs[0]["event_type"] == "fire"
    assert refs[0]["tick"] == 5
    assert "blaze" in refs[0]["snippet"]
    assert refs[0]["score"] == 0.8
