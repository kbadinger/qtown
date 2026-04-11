"""
v2_model_router.py — Model routing for Ralph v2.

Routes story execution to the appropriate Ollama model based on service,
language, and task type. Tracks per-model success rates and implements
a fallback chain when the primary model fails.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service-level configuration (mirrors worklist SERVICE_CONFIG)
# ---------------------------------------------------------------------------

# Languages that route to the fast code-generation model
CODE_LANGUAGES = {"python", "go", "rust", "typescript", "ts", "proto", "dockerfile", "yaml"}

# Tier definitions (ordered from fastest/cheapest to most capable)
TIER_1_CODE = "qwen3-coder-next"          # default for all code tasks
TIER_2_ARCHITECTURE = "qwen3.5:27b"       # architecture / design changes
TIER_3_DEBUG = "deepseek-r1:14b"          # debugging / root cause analysis
TIER_FALLBACK = "llama3.1:8b"             # last-resort fallback

# Keywords that signal an architecture-level change
ARCHITECTURE_KEYWORDS = {
    "architect", "design", "refactor", "restructure", "migrate",
    "schema", "interface", "api contract", "grpc service", "service mesh",
    "multi-region", "cross-service", "orchestrat",
}

# Keywords that signal debugging work
DEBUG_KEYWORDS = {
    "debug", "fix", "bug", "flaky", "intermittent", "race condition",
    "deadlock", "memory leak", "timeout", "panic", "crash", "traceback",
    "root cause", "investigate",
}

# Fallback chain per tier
FALLBACK_CHAIN: dict[str, list[str]] = {
    TIER_1_CODE: [TIER_2_ARCHITECTURE, TIER_3_DEBUG, TIER_FALLBACK],
    TIER_2_ARCHITECTURE: [TIER_1_CODE, TIER_3_DEBUG, TIER_FALLBACK],
    TIER_3_DEBUG: [TIER_2_ARCHITECTURE, TIER_1_CODE, TIER_FALLBACK],
    TIER_FALLBACK: [],
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ModelStats:
    """Per-(model, language) success tracking."""
    model: str
    language: str
    successes: int = 0
    failures: int = 0
    total_duration_seconds: float = 0.0

    @property
    def attempts(self) -> int:
        return self.successes + self.failures

    @property
    def success_rate(self) -> float:
        if self.attempts == 0:
            return 1.0  # optimistic default
        return self.successes / self.attempts

    @property
    def avg_duration(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_duration_seconds / self.successes


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class ModelRouter:
    """
    Routes a Story to an Ollama model name.

    Usage::

        router = ModelRouter()
        model = router.route(story)
        # ... run generation ...
        router.record_result(model, story.language, success=True, duration=12.3)
        # If primary fails:
        fallback = router.next_fallback(model)
    """

    def __init__(self) -> None:
        # key: (model, language) → ModelStats
        self._stats: dict[tuple[str, str], ModelStats] = defaultdict(
            lambda: ModelStats(model="", language="")
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, story) -> str:  # story: Story (avoid circular import)
        """
        Return the best Ollama model name for this story.

        Priority order:
        1. Debug task → TIER_3_DEBUG
        2. Architecture task → TIER_2_ARCHITECTURE
        3. Code language → TIER_1_CODE
        4. Default → TIER_1_CODE
        """
        title_lower = story.title.lower()
        lang = story.language.lower()

        if self._matches_keywords(title_lower, DEBUG_KEYWORDS):
            primary = TIER_3_DEBUG
        elif self._matches_keywords(title_lower, ARCHITECTURE_KEYWORDS):
            primary = TIER_2_ARCHITECTURE
        elif lang in CODE_LANGUAGES:
            primary = TIER_1_CODE
        else:
            primary = TIER_1_CODE

        # Prefer model with higher success rate if we have data
        primary = self._prefer_by_success_rate(primary, lang)

        logger.debug(
            "Routing story %s (lang=%s) → %s", story.id, lang, primary
        )
        return primary

    def next_fallback(self, failed_model: str) -> Optional[str]:
        """Return the next model in the fallback chain, or None if exhausted."""
        chain = FALLBACK_CHAIN.get(failed_model, [])
        return chain[0] if chain else None

    def full_fallback_chain(self, primary: str) -> list[str]:
        """Return [primary] + all fallbacks in order."""
        return [primary] + FALLBACK_CHAIN.get(primary, [])

    def record_result(
        self,
        model: str,
        language: str,
        *,
        success: bool,
        duration_seconds: float = 0.0,
    ) -> None:
        """Update success-rate tracking after a generation attempt."""
        key = (model, language.lower())
        stats = self._stats[key]
        stats.model = model
        stats.language = language.lower()
        if success:
            stats.successes += 1
            stats.total_duration_seconds += duration_seconds
        else:
            stats.failures += 1

    def get_stats(self) -> list[ModelStats]:
        return list(self._stats.values())

    def success_rate(self, model: str, language: str) -> float:
        key = (model, language.lower())
        if key not in self._stats:
            return 1.0
        return self._stats[key].success_rate

    def summary(self) -> dict:
        """Return a summary dict suitable for logging."""
        out: dict[str, dict] = {}
        for (model, lang), stats in self._stats.items():
            out.setdefault(model, {})[lang] = {
                "success_rate": round(stats.success_rate, 3),
                "attempts": stats.attempts,
                "avg_duration_s": round(stats.avg_duration, 1),
            }
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_keywords(text: str, keywords: set[str]) -> bool:
        return any(kw in text for kw in keywords)

    def _prefer_by_success_rate(self, primary: str, language: str) -> str:
        """
        If the primary model has a poor success rate (< 0.5) and a fallback
        has a better rate, prefer the fallback proactively.
        """
        primary_rate = self.success_rate(primary, language)
        if primary_rate >= 0.5:
            return primary

        best_model = primary
        best_rate = primary_rate
        for candidate in FALLBACK_CHAIN.get(primary, []):
            rate = self.success_rate(candidate, language)
            if rate > best_rate:
                best_rate = rate
                best_model = candidate

        if best_model != primary:
            logger.info(
                "Proactively routing to %s (rate=%.2f) over %s (rate=%.2f) for lang=%s",
                best_model, best_rate, primary, primary_rate, language,
            )
        return best_model
