"""
Town anthem generation — flavor content for Qtown.

AnthemGenerator produces a short lyrical anthem for Qtown that reflects the
current town mood, population size, and notable recent events.  Anthems are
generated periodically (every 100 ticks) or triggered by major events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from academy.models.router import ModelRouter

logger = logging.getLogger("academy.content.anthem")

# How many ticks between automatic anthem regenerations
ANTHEM_INTERVAL_TICKS = 100


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Anthem:
    """
    A generated town anthem for Qtown.

    Fields
    ------
    title:
        The anthem's title (e.g. "Ode to the Morning Market").
    verses:
        List of verse strings, each 4–6 lines of rhyming or rhythmic text.
    mood:
        The emotional tone that shaped this anthem (e.g. "joyful", "anxious").
    generated_at:
        UTC ISO-8601 timestamp.
    model_used:
        Model that generated the anthem (for audit).
    notable_events:
        Events that were referenced during generation.
    """

    title: str
    verses: list[str]
    mood: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model_used: str = "unknown"
    notable_events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "verses": self.verses,
            "mood": self.mood,
            "generated_at": self.generated_at,
            "model_used": self.model_used,
            "notable_events": self.notable_events,
        }

    def to_text(self) -> str:
        """Render the anthem as a plain-text scroll."""
        divider = "~" * 50
        parts = [
            f"{divider}",
            f"  {self.title.upper()}",
            f"  Town Mood: {self.mood}",
            f"{divider}",
            "",
        ]
        for i, verse in enumerate(self.verses, 1):
            parts.append(f"[Verse {i}]")
            parts.append(verse)
            parts.append("")
        parts.append(divider)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class AnthemGenerator:
    """
    Generates town anthems using the ModelRouter.

    Usage::

        gen = AnthemGenerator()
        anthem = await gen.generate_anthem(
            town_mood="jubilant",
            population=350,
            notable_events=["The Great Harvest", "Market Day Record"],
        )
    """

    _SYSTEM_PROMPT = (
        "You are the royal bard of Qtown, a thriving medieval fantasy town. "
        "You compose anthems that reflect the spirit of the citizenry — "
        "lyrical, evocative, and grounded in the town's daily life. "
        "Your verses have rhythm and occasional rhyme, never clichéd. "
        "You always capture the specific mood and events of the moment."
    )

    # Mood → tonal guidance mapping
    _MOOD_GUIDE: dict[str, str] = {
        "joyful":    "celebratory, uplifting, full of pride",
        "anxious":   "tense, uncertain, yearning for stability",
        "prosperous": "confident, grand, boastful in good spirit",
        "melancholy": "wistful, slow, reflective on loss or hardship",
        "jubilant":  "ecstatic, triumphant, festival-like",
        "neutral":   "steady, earnest, matter-of-fact",
        "fearful":   "hushed, desperate, calling for courage",
        "hopeful":   "gentle, forward-looking, warming",
    }

    def __init__(self, router: ModelRouter | None = None) -> None:
        self._router = router or ModelRouter()

    def _build_prompt(
        self,
        town_mood: str,
        population: int,
        notable_events: list[str],
    ) -> str:
        mood_desc = self._MOOD_GUIDE.get(town_mood, "earnest and grounded")
        events_text = (
            "\n".join(f"  - {e}" for e in notable_events[:5])
            if notable_events
            else "  - (no major events)"
        )

        pop_desc = (
            "small village" if population < 100
            else "growing town" if population < 500
            else "bustling city"
        )

        return (
            f"Compose a town anthem for Qtown, a {pop_desc} with {population} citizens.\n\n"
            f"CURRENT MOOD: {town_mood} — tone should be {mood_desc}\n\n"
            f"NOTABLE RECENT EVENTS:\n{events_text}\n\n"
            f"Write the anthem with EXACTLY this structure:\n"
            f"TITLE: <anthem title>\n"
            f"VERSE_1:\n<4-6 lines>\n"
            f"VERSE_2:\n<4-6 lines>\n"
            f"VERSE_3:\n<4-6 lines, optional — include only if inspired>\n\n"
            f"Guidelines:\n"
            f"- Reference specific events from the list above\n"
            f"- Keep language accessible but lyrical\n"
            f"- Rhyme scheme optional but maintain clear rhythm\n"
            f"- Each verse should stand alone yet connect thematically\n"
            f"- Mention Qtown by name at least once"
        )

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        """Extract title and verses from LLM output."""
        result: dict[str, Any] = {
            "title": "",
            "verses": [],
        }

        current_verse_lines: list[str] = []
        in_verse = False

        for line in raw.splitlines():
            stripped = line.strip()
            upper = stripped.upper()

            if upper.startswith("TITLE:"):
                result["title"] = stripped[6:].strip()
                in_verse = False
                if current_verse_lines:
                    result["verses"].append("\n".join(current_verse_lines).strip())
                    current_verse_lines = []
            elif upper.startswith("VERSE_"):
                # Save previous verse
                if current_verse_lines:
                    result["verses"].append("\n".join(current_verse_lines).strip())
                    current_verse_lines = []
                in_verse = True
                # Check if the verse content is on the same line
                rest = stripped[len(stripped.split(":")[0]) + 1:].strip()
                if rest:
                    current_verse_lines.append(rest)
            elif in_verse and stripped:
                current_verse_lines.append(stripped)

        # Flush last verse
        if current_verse_lines:
            result["verses"].append("\n".join(current_verse_lines).strip())

        # Filter out empty verses
        result["verses"] = [v for v in result["verses"] if v]

        if not result["title"]:
            result["title"] = "Ode to Qtown"

        return result

    def _fallback_anthem(
        self,
        town_mood: str,
        population: int,
        notable_events: list[str],
    ) -> dict[str, Any]:
        """Template-based anthem when LLM is unavailable."""
        event_ref = notable_events[0] if notable_events else "the passing days"
        return {
            "title": f"Ballad of Qtown ({town_mood.title()})",
            "verses": [
                (
                    f"In Qtown's streets where {population} souls reside,\n"
                    f"We face each dawn with steadfast Qtowner pride.\n"
                    f"Through {event_ref} and seasons' endless turning,\n"
                    f"Our hearths stay warm, our lanterns always burning."
                ),
                (
                    f"The mood is {town_mood} as we gather near,\n"
                    f"Merchants and farmers united, nothing to fear.\n"
                    f"Let every cobblestone ring with our song,\n"
                    f"For Qtown endures — we have all along."
                ),
            ],
        }

    async def generate_anthem(
        self,
        town_mood: str,
        population: int,
        notable_events: list[str],
    ) -> Anthem:
        """
        Generate a town anthem.

        Parameters
        ----------
        town_mood:
            Emotional tone of the town (e.g. "joyful", "anxious", "neutral").
        population:
            Current number of NPCs in the town.
        notable_events:
            List of recent notable event descriptions to weave into the anthem.

        Returns
        -------
        Anthem
        """
        prompt = self._build_prompt(town_mood, population, notable_events)
        logger.info(
            "Generating anthem: mood=%s population=%d events=%d",
            town_mood, population, len(notable_events),
        )

        model_used = "fallback"
        try:
            result = await self._router.route(
                "narration",
                {
                    "prompt": prompt,
                    "system": self._SYSTEM_PROMPT,
                    "temperature": 0.9,
                    "max_tokens": 400,
                },
            )
            raw = result.response
            model_used = result.model_used
            fields = self._parse_response(raw)
        except Exception as exc:
            logger.error("Anthem generation failed: %s", exc)
            fields = self._fallback_anthem(town_mood, population, notable_events)

        # Ensure at least one verse
        if not fields["verses"]:
            fields = self._fallback_anthem(town_mood, population, notable_events)

        return Anthem(
            title=fields["title"],
            verses=fields["verses"],
            mood=town_mood,
            model_used=model_used,
            notable_events=notable_events,
        )

    @staticmethod
    def should_regenerate(current_tick: int, last_anthem_tick: int, major_event: bool = False) -> bool:
        """
        Return True if an anthem should be generated at this tick.

        Regenerates every ANTHEM_INTERVAL_TICKS ticks or immediately after a
        major event.

        Parameters
        ----------
        current_tick:
            Current simulation tick.
        last_anthem_tick:
            Tick when the last anthem was generated.
        major_event:
            True if a major event occurred this tick.
        """
        if major_event:
            return True
        return (current_tick - last_anthem_tick) >= ANTHEM_INTERVAL_TICKS
