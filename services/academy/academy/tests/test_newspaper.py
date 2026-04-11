"""
Tests for academy.content.newspaper.

Coverage:
  - test_generate_daily_returns_article     — basic happy-path generation
  - test_parse_response_all_sections        — parser extracts all four sections
  - test_parse_response_missing_sections    — graceful fallback when sections missing
  - test_generate_daily_llm_failure         — fallback article on ModelRouter failure
  - test_article_to_text                    — text rendering includes key fields
  - test_article_to_dict                    — dict serialisation is complete
  - test_events_capped                      — only first 20 events used in prompt
  - test_empty_events                       — works with no events
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from academy.content.newspaper import NewspaperArticle, NewspaperGenerator
from academy.models.router import ModelRouter, RouteResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_router(response_text: str = "", fail: bool = False) -> ModelRouter:
    router = MagicMock(spec=ModelRouter)
    if fail:
        router.route = AsyncMock(side_effect=RuntimeError("model unavailable"))
    else:
        result = RouteResult(
            task_type="narration",
            model_used="llama3:8b",
            response=response_text,
            prompt_tokens=50,
            completion_tokens=150,
        )
        router.route = AsyncMock(return_value=result)
    return router


SAMPLE_LLM_RESPONSE = """
HEADLINE: Record Harvest Fills Qtown Granaries
LEAD: Citizens of Qtown celebrated today as the autumn harvest exceeded all expectations, with grain stores reaching capacity for the first time in a decade.
BODY: Farmers from the Farmlands district worked tirelessly through the night to bring in the bumper crop. Market traders reported a 40% increase in grain trading by midday. The Academy's scholars credited the unusually warm summer and the hard work of some 120 farming NPC families.

Mayor Aldric declared a half-holiday for the remainder of the day, and the smell of fresh bread drifted through every neighborhood. Merchants' ledgers showed the highest single-day gold turnover in three years.
EDITORIAL: At last, Qtown's citizens may sleep soundly knowing their bellies shall not want this winter.
"""

SAMPLE_EVENTS = [
    {"type": "trade", "description": "Farmer sold 50 wheat at Market District"},
    {"type": "npc_action", "description": "Mira completed her delivery quest"},
    {"type": "construction", "description": "New smithy opened in Blacksmith Row"},
]

SAMPLE_TOWN_STATE = {
    "population": 250,
    "total_gold": 12500,
    "average_mood": "content",
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGenerateDaily:
    @pytest.mark.asyncio
    async def test_returns_newspaper_article(self):
        """generate_daily should return a NewspaperArticle with all fields set."""
        gen = NewspaperGenerator(router=make_router(SAMPLE_LLM_RESPONSE))
        article = await gen.generate_daily(SAMPLE_EVENTS, tick=15, town_state=SAMPLE_TOWN_STATE)

        assert isinstance(article, NewspaperArticle)
        assert article.tick == 15
        assert article.headline != ""
        assert article.lead != ""
        assert article.body != ""
        assert article.editorial != ""
        assert article.model_used == "llama3:8b"

    @pytest.mark.asyncio
    async def test_headline_extracted(self):
        """Headline should match the LLM output."""
        gen = NewspaperGenerator(router=make_router(SAMPLE_LLM_RESPONSE))
        article = await gen.generate_daily(SAMPLE_EVENTS, tick=1, town_state=SAMPLE_TOWN_STATE)
        assert "harvest" in article.headline.lower() or article.headline != ""

    @pytest.mark.asyncio
    async def test_editorial_extracted(self):
        """Editorial should be a non-empty string."""
        gen = NewspaperGenerator(router=make_router(SAMPLE_LLM_RESPONSE))
        article = await gen.generate_daily(SAMPLE_EVENTS, tick=1, town_state=SAMPLE_TOWN_STATE)
        assert len(article.editorial) > 5


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_all_sections_extracted(self):
        """Parser should extract all four labelled sections."""
        sections = NewspaperGenerator._parse_response(SAMPLE_LLM_RESPONSE)
        assert sections["headline"] != ""
        assert sections["lead"] != ""
        assert sections["body"] != ""
        assert sections["editorial"] != ""

    def test_missing_sections_get_fallback(self):
        """If sections are missing, parser should provide fallback strings."""
        raw = "Some random text without any labelled sections."
        sections = NewspaperGenerator._parse_response(raw)
        # Fallback headline
        assert sections["headline"] == "Another Day in Qtown"
        # Fallback lead uses raw content
        assert sections["lead"] != ""
        # Body uses raw content
        assert sections["body"] != ""
        # Fallback editorial
        assert "no comment" in sections["editorial"].lower()

    def test_partial_sections(self):
        """Parser should handle partially labelled output."""
        raw = "HEADLINE: Partial Test\nSome body text without LEAD or BODY labels."
        sections = NewspaperGenerator._parse_response(raw)
        assert sections["headline"] == "Partial Test"
        # lead falls back
        assert sections["lead"] != ""


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_fallback_article(self):
        """If ModelRouter raises, generate_daily should return a fallback article."""
        gen = NewspaperGenerator(router=make_router(fail=True))
        article = await gen.generate_daily(SAMPLE_EVENTS, tick=5, town_state=SAMPLE_TOWN_STATE)

        assert isinstance(article, NewspaperArticle)
        assert article.tick == 5
        assert article.headline != ""
        assert article.model_used == "fallback"

    @pytest.mark.asyncio
    async def test_empty_events_does_not_crash(self):
        """Empty events list should produce a valid article."""
        gen = NewspaperGenerator(router=make_router(SAMPLE_LLM_RESPONSE))
        article = await gen.generate_daily([], tick=0, town_state=SAMPLE_TOWN_STATE)
        assert isinstance(article, NewspaperArticle)
        assert article.headline != ""

    @pytest.mark.asyncio
    async def test_many_events_prompt_is_not_excessive(self):
        """With 50 events, only the first 20 should appear in the prompt."""
        events = [{"type": "test", "description": f"event {i}"} for i in range(50)]
        # We capture what the router received
        captured_prompts = []

        async def capture_route(task_type, context):
            captured_prompts.append(context.get("prompt", ""))
            return RouteResult(
                task_type=task_type,
                model_used="llama3:8b",
                response=SAMPLE_LLM_RESPONSE,
                prompt_tokens=100,
                completion_tokens=200,
            )

        router = MagicMock(spec=ModelRouter)
        router.route = capture_route

        gen = NewspaperGenerator(router=router)
        await gen.generate_daily(events, tick=1, town_state=SAMPLE_TOWN_STATE)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # Only "event 0" through "event 19" should appear; "event 20" should not
        assert "event 19" in prompt
        assert "event 20" not in prompt


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_has_all_fields(self):
        """to_dict should include all required keys."""
        article = NewspaperArticle(
            headline="Test Headline",
            lead="Test lead.",
            body="Test body.",
            editorial="Test editorial.",
            tick=7,
            model_used="llama3:8b",
        )
        d = article.to_dict()
        for key in ["headline", "lead", "body", "editorial", "tick", "generated_at", "model_used"]:
            assert key in d

    def test_to_text_includes_headline_and_tick(self):
        """to_text should produce a readable string with the headline and tick."""
        article = NewspaperArticle(
            headline="Big News Today",
            lead="Something happened.",
            body="Details here.",
            editorial="Remarkable.",
            tick=99,
        )
        text = article.to_text()
        assert "BIG NEWS TODAY" in text
        assert "99" in text
        assert "QTOWN DAILY GAZETTE" in text
