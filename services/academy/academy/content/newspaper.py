"""
Newspaper generation — Qtown Daily Gazette.

NewspaperGenerator produces in-world news articles from the day's events
using the ModelRouter.  Articles are structured as proper journalism with
a headline, lead paragraph, body paragraphs, and an editorial comment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from academy.models.router import ModelRouter

logger = logging.getLogger("academy.content.newspaper")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class NewspaperArticle:
    """
    A single edition of the Qtown Daily Gazette.

    Fields
    ------
    headline:
        Bold, attention-grabbing headline (< 80 characters).
    lead:
        Opening paragraph summarising who, what, where, when (≤ 3 sentences).
    body:
        2–3 paragraphs of in-depth reporting.
    editorial:
        One opinionated sentence from the editor.
    tick:
        Simulation tick this article covers.
    generated_at:
        UTC ISO-8601 timestamp of generation.
    model_used:
        Ollama model that generated this article (for audit).
    """

    headline: str
    lead: str
    body: str
    editorial: str
    tick: int
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model_used: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "lead": self.lead,
            "body": self.body,
            "editorial": self.editorial,
            "tick": self.tick,
            "generated_at": self.generated_at,
            "model_used": self.model_used,
        }

    def to_text(self) -> str:
        """Render the article as a plain-text newspaper page."""
        divider = "=" * 60
        return (
            f"{divider}\n"
            f"THE QTOWN DAILY GAZETTE  — Tick {self.tick}\n"
            f"{divider}\n\n"
            f"{self.headline.upper()}\n\n"
            f"{self.lead}\n\n"
            f"{self.body}\n\n"
            f"EDITORIAL: {self.editorial}\n"
            f"{divider}"
        )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class NewspaperGenerator:
    """
    Generates a daily newspaper article from simulation events.

    Usage::

        gen = NewspaperGenerator()
        article = await gen.generate_daily(events, tick=42, town_state={...})
    """

    # System prompt that establishes the Gazette's editorial voice
    _SYSTEM_PROMPT = (
        "You are the editor-in-chief of the Qtown Daily Gazette, a respected "
        "broadsheet serving the citizens of Qtown. Your prose is clear, vivid, "
        "and slightly whimsical — fitting for a fantasy medieval town. "
        "You report facts accurately but never miss an opportunity for wry commentary."
    )

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter()

    def _build_prompt(
        self,
        events: list[dict[str, Any]],
        tick: int,
        town_state: dict[str, Any],
    ) -> str:
        """
        Construct the generation prompt.

        The prompt asks the LLM to return a structured article using
        labelled sections so we can reliably parse it.
        """
        event_lines = "\n".join(
            f"  - [{e.get('type', 'event')}] {e.get('description', str(e))}"
            for e in events[:20]  # cap to avoid context overflow
        ) or "  - (no notable events today)"

        pop = town_state.get("population", "unknown")
        gold = town_state.get("total_gold", "unknown")
        mood = town_state.get("average_mood", "neutral")

        return (
            f"You are the editor of the Qtown Daily Gazette. "
            f"Write a newspaper for today's edition (tick {tick}).\n\n"
            f"TOWN STATE:\n"
            f"  Population: {pop}\n"
            f"  Total gold in circulation: {gold}\n"
            f"  Average citizen mood: {mood}\n\n"
            f"TODAY'S EVENTS:\n{event_lines}\n\n"
            f"Write the newspaper with EXACTLY these labelled sections:\n"
            f"HEADLINE: <one punchy headline>\n"
            f"LEAD: <opening paragraph, ≤3 sentences, who/what/where/when>\n"
            f"BODY: <2-3 paragraphs of reporting>\n"
            f"EDITORIAL: <one opinionated sentence from the editor>\n\n"
            f"Use only these labels. Do not add extra sections."
        )

    @staticmethod
    def _parse_response(raw: str) -> dict[str, str]:
        """
        Extract the four labelled sections from the LLM response.

        Falls back to sensible defaults if parsing fails.
        """
        sections: dict[str, str] = {
            "headline": "",
            "lead": "",
            "body": "",
            "editorial": "",
        }

        current_key: str | None = None
        buffer: list[str] = []

        label_map = {
            "HEADLINE:": "headline",
            "LEAD:": "lead",
            "BODY:": "body",
            "EDITORIAL:": "editorial",
        }

        for line in raw.splitlines():
            stripped = line.strip()
            matched = False
            for label, key in label_map.items():
                if stripped.upper().startswith(label):
                    # Save previous section
                    if current_key and buffer:
                        sections[current_key] = " ".join(buffer).strip()
                        buffer = []
                    current_key = key
                    remainder = stripped[len(label):].strip()
                    if remainder:
                        buffer.append(remainder)
                    matched = True
                    break
            if not matched and current_key is not None:
                buffer.append(stripped)

        # Flush last section
        if current_key and buffer:
            sections[current_key] = " ".join(buffer).strip()

        # Fill any missing sections with placeholder text
        if not sections["headline"]:
            sections["headline"] = "Another Day in Qtown"
        if not sections["lead"]:
            sections["lead"] = raw[:200].strip()
        if not sections["body"]:
            sections["body"] = raw.strip()
        if not sections["editorial"]:
            sections["editorial"] = "The editor has no comment at this time."

        return sections

    async def generate_daily(
        self,
        events: list[dict[str, Any]],
        tick: int,
        town_state: dict[str, Any],
    ) -> NewspaperArticle:
        """
        Generate a NewspaperArticle from today's events.

        Parameters
        ----------
        events:
            List of event dicts from the simulation.  Each should have at
            minimum a 'description' key.
        tick:
            Current simulation tick.
        town_state:
            Dict with keys like 'population', 'total_gold', 'average_mood'.

        Returns
        -------
        NewspaperArticle
        """
        prompt = self._build_prompt(events, tick, town_state)
        logger.info("Generating newspaper for tick=%d with %d events", tick, len(events))

        try:
            result = await self._router.route(
                "narration",
                {
                    "prompt": prompt,
                    "system": self._SYSTEM_PROMPT,
                    "temperature": 0.8,
                    "max_tokens": 512,
                },
            )
            raw = result.response
            model_used = result.model_used
        except Exception as exc:
            logger.error("Newspaper generation failed: %s", exc)
            raw = (
                "HEADLINE: Quiet Day in Qtown\n"
                "LEAD: Citizens of Qtown went about their daily routines without incident.\n"
                "BODY: The town remained peaceful today.\n"
                "EDITORIAL: Sometimes no news is good news."
            )
            model_used = "fallback"

        sections = self._parse_response(raw)

        return NewspaperArticle(
            headline=sections["headline"],
            lead=sections["lead"],
            body=sections["body"],
            editorial=sections["editorial"],
            tick=tick,
            model_used=model_used,
        )
