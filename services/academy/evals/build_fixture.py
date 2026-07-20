"""
Build the committed eval fixture (W1-A3).

Embeds the docs corpus + the golden questions with nomic-embed-text and saves the
vectors to evals/fixture.npz. Run LOCALLY (needs Ollama); the output is committed
so the recall@k gate (evals/recall.py) runs deterministically in CI with no model
— the same "measure then check" pattern as the M7 perf report.

    python -m evals.build_fixture
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np

from academy.ollama_client import OllamaClient
from academy.rag.corpus import build_corpus, repo_root

EVALS_DIR = Path(__file__).resolve().parent
FIXTURE = EVALS_DIR / "fixture.npz"
GOLDEN = EVALS_DIR / "golden.json"
EMBED_MODEL = "nomic-embed-text"


async def main() -> None:
    ollama = OllamaClient()
    corpus = build_corpus(repo_root())
    print(f"corpus: {len(corpus)} chunks — embedding...")

    corpus_vecs: list[list[float]] = []
    for i, doc in enumerate(corpus):
        corpus_vecs.append(await ollama.embed(doc["content"], model=EMBED_MODEL))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(corpus)}")

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    items = golden["items"]
    print(f"golden: {len(items)} questions — embedding...")
    query_vecs = [await ollama.embed(it["question"], model=EMBED_MODEL) for it in items]

    np.savez_compressed(
        FIXTURE,
        corpus_doc_ids=np.array([d["doc_id"] for d in corpus]),
        corpus_sources=np.array([d["metadata"]["source"] for d in corpus]),
        corpus_vecs=np.array(corpus_vecs, dtype=np.float32),
        query_ids=np.array([it["id"] for it in items]),
        query_vecs=np.array(query_vecs, dtype=np.float32),
    )
    print(f"wrote {FIXTURE.name}: {len(corpus)} corpus x {len(items)} queries")


if __name__ == "__main__":
    asyncio.run(main())
