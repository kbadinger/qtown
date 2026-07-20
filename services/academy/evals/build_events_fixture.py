"""
Build the committed town-EVENT eval fixture (grounding slice 4).

Embeds the synthetic events + queries from events_golden.json with
nomic-embed-text and saves the vectors to evals/events_fixture.npz. Run LOCALLY
(needs Ollama); the output is committed so the events-recall gate
(evals/events_recall.py) runs deterministically in CI with no model. Kept separate
from the docs fixture (build_fixture.py) so the two corpora never mix.

    python -m evals.build_events_fixture
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np

from academy.ollama_client import OllamaClient

EVALS_DIR = Path(__file__).resolve().parent
GOLDEN = EVALS_DIR / "events_golden.json"
FIXTURE = EVALS_DIR / "events_fixture.npz"
EMBED_MODEL = "nomic-embed-text"


async def main() -> None:
    ollama = OllamaClient()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    events = golden["events"]
    queries = golden["queries"]
    print(f"events: {len(events)}, queries: {len(queries)} — embedding...")

    event_vecs = [await ollama.embed(e["content"], model=EMBED_MODEL) for e in events]
    query_vecs = [await ollama.embed(q["question"], model=EMBED_MODEL) for q in queries]

    np.savez_compressed(
        FIXTURE,
        event_ids=np.array([e["doc_id"] for e in events]),
        event_vecs=np.array(event_vecs, dtype=np.float32),
        query_ids=np.array([q["id"] for q in queries]),
        query_vecs=np.array(query_vecs, dtype=np.float32),
    )
    print(f"wrote {FIXTURE.name}: {len(events)} events x {len(queries)} queries")


if __name__ == "__main__":
    asyncio.run(main())
