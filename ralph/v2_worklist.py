"""
v2_worklist.py — Worklist parser for Ralph v2.

Replaces prd.json for multi-agent orchestration. Parses worklist.json,
tracks story status, and exposes dependency-aware scheduling helpers.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Story:
    """Represents a single unit of work for Ralph v2."""

    id: str
    title: str
    service: str
    language: str
    deps: list[str] = field(default_factory=list)
    status: str = "pending"       # pending | in_progress | complete | failed
    attempts: int = 0
    last_error: Optional[str] = None

    # Optional metadata
    description: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Story":
        return cls(
            id=data["id"],
            title=data["title"],
            service=data.get("service", "unknown"),
            language=data.get("language", "python"),
            deps=data.get("deps", []),
            status=data.get("status", "pending"),
            attempts=data.get("attempts", 0),
            last_error=data.get("last_error"),
            description=data.get("description", ""),
            acceptance_criteria=data.get("acceptance_criteria", []),
            labels=data.get("labels", []),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "service": self.service,
            "language": self.language,
            "deps": self.deps,
            "status": self.status,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "labels": self.labels,
        }


class Worklist:
    """
    Manages a worklist.json file with dependency-aware story scheduling.

    File format::

        {
          "stories": [
            {
              "id": "P5-001",
              "title": "Add health endpoint to town-core",
              "service": "town-core",
              "language": "python",
              "deps": [],
              "status": "pending"
            }
          ]
        }
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._stories: dict[str, Story] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: str) -> list[Story]:
        """(Re)load from *path* and return all stories."""
        self.path = Path(path)
        self._load()
        return list(self._stories.values())

    def all_stories(self) -> list[Story]:
        return list(self._stories.values())

    def next_available(self, completed: set[str]) -> list[Story]:
        """
        Return stories whose dependencies are all satisfied by *completed*.

        A story is available if:
        - status == 'pending'
        - every dep id is in *completed*
        """
        available = []
        for story in self._stories.values():
            if story.status != "pending":
                continue
            if all(dep in completed for dep in story.deps):
                available.append(story)
        return available

    def mark_complete(self, story_id: str) -> None:
        story = self._get(story_id)
        story.status = "complete"
        self._save()
        logger.info("Story %s marked complete", story_id)

    def mark_failed(self, story_id: str, error: str) -> None:
        story = self._get(story_id)
        story.status = "failed"
        story.last_error = error
        self._save()
        logger.warning("Story %s marked failed: %s", story_id, error)

    def mark_in_progress(self, story_id: str) -> None:
        story = self._get(story_id)
        story.status = "in_progress"
        story.attempts += 1
        self._save()

    def reset_to_pending(self, story_id: str) -> None:
        """Reset a failed or stuck story back to pending for retry."""
        story = self._get(story_id)
        story.status = "pending"
        self._save()

    def get_progress(self) -> dict:
        """Return counts grouped by status plus per-status story lists."""
        by_status: dict[str, list[str]] = {
            "pending": [],
            "in_progress": [],
            "complete": [],
            "failed": [],
        }
        for story in self._stories.values():
            bucket = by_status.setdefault(story.status, [])
            bucket.append(story.id)

        total = len(self._stories)
        complete_count = len(by_status.get("complete", []))
        return {
            "total": total,
            "complete": complete_count,
            "pending": len(by_status.get("pending", [])),
            "in_progress": len(by_status.get("in_progress", [])),
            "failed": len(by_status.get("failed", [])),
            "pct_complete": round(complete_count / total * 100, 1) if total else 0,
            "by_status": by_status,
        }

    def get_story(self, story_id: str) -> Story:
        return self._get(story_id)

    def completed_ids(self) -> set[str]:
        return {s.id for s in self._stories.values() if s.status == "complete"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            logger.warning("Worklist file not found: %s — starting empty", self.path)
            self._stories = {}
            return

        with self.path.open() as fh:
            raw = json.load(fh)

        stories_raw = raw.get("stories", raw) if isinstance(raw, dict) else raw
        self._stories = {s["id"]: Story.from_dict(s) for s in stories_raw}
        logger.info("Loaded %d stories from %s", len(self._stories), self.path)

    def _save(self) -> None:
        """Atomically write updated worklist back to disk."""
        tmp = self.path.with_suffix(".tmp")
        payload = {"stories": [s.to_dict() for s in self._stories.values()]}
        with tmp.open("w") as fh:
            json.dump(payload, fh, indent=2)
        tmp.replace(self.path)

    def _get(self, story_id: str) -> Story:
        if story_id not in self._stories:
            raise KeyError(f"Story {story_id!r} not found in worklist")
        return self._stories[story_id]


# ---------------------------------------------------------------------------
# Module-level convenience functions (mirrors original prd.json helpers)
# ---------------------------------------------------------------------------

def load(path: str) -> list[Story]:
    """Load worklist from *path* and return all stories."""
    return Worklist(path).all_stories()


def next_available(path: str, completed: set[str]) -> list[Story]:
    """Return stories ready to work on given the *completed* set."""
    return Worklist(path).next_available(completed)
