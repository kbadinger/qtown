"""
Town-EVENT recall@k gate (grounding slice 4) — deterministic, no model.

Loads the committed events fixture (evals/events_fixture.npz) + golden set
(evals/events_golden.json), ranks the synthetic town events by cosine similarity
per query, and computes recall@k of the expected event doc_ids. With --assert it
exits 1 when mean recall@k is below the threshold in events_golden.json — this is
the blocking gate proving that dialogue grounding can actually retrieve the right
town events. Kept SEPARATE from the docs recall gate (recall.py): different corpus,
different fixture, so neither conflates the other.

    python -m evals.events_recall            # report
    python -m evals.events_recall --assert   # report + exit 1 if below threshold
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

EVALS_DIR = Path(__file__).resolve().parent


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def evaluate() -> tuple[int, float, float, list[tuple[str, float]]]:
    golden = json.loads((EVALS_DIR / "events_golden.json").read_text(encoding="utf-8"))
    fx = np.load(EVALS_DIR / "events_fixture.npz", allow_pickle=False)

    k = int(golden.get("k", 3))
    threshold = float(golden.get("recall_threshold", 0.75))
    expected_by_id = {q["id"]: q["expected"] for q in golden["queries"]}

    event_ids = [str(e) for e in fx["event_ids"]]
    event_vecs = _normalize(fx["event_vecs"].astype(np.float64))
    query_ids = [str(q) for q in fx["query_ids"]]
    query_vecs = _normalize(fx["query_vecs"].astype(np.float64))

    results: list[tuple[str, float]] = []
    for qid, qv in zip(query_ids, query_vecs):
        sims = event_vecs @ qv
        topk_idx = np.argsort(-sims)[:k]
        topk = {event_ids[i] for i in topk_idx}
        expected = expected_by_id[qid]
        hits = sum(1 for e in expected if e in topk)
        recall = hits / len(expected) if expected else 0.0
        results.append((qid, recall))

    mean_recall = sum(r for _, r in results) / len(results) if results else 0.0
    return k, mean_recall, threshold, results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assert", dest="do_assert", action="store_true")
    args = ap.parse_args()

    k, mean_recall, threshold, results = evaluate()
    print(f"events recall@{k} over {len(results)} golden queries: {mean_recall:.3f}  (threshold {threshold})")
    for qid, recall in results:
        mark = "PASS" if recall >= 1.0 else ("part" if recall > 0 else "MISS")
        print(f"  [{mark:>4}] {qid:14s} recall={recall:.2f}")

    if args.do_assert and mean_recall < threshold:
        print(f"\nFAIL: events recall@{k} {mean_recall:.3f} < threshold {threshold}")
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
