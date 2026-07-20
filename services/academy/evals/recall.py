"""
recall@k retrieval-quality gate (W1-A3) — deterministic, no model.

Loads the committed fixture (evals/fixture.npz) + golden set (evals/golden.json),
ranks the corpus by cosine similarity per question, and computes recall@k of the
expected source docs. With --assert it exits 1 when mean recall@k is below the
threshold in golden.json — this is the blocking CI gate. Only the *vector
retrieval* layer is measured here (deterministic); generation faithfulness is the
separate local eval (evals/faithfulness.py).

    python -m evals.recall            # report
    python -m evals.recall --assert   # report + exit 1 if below threshold
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


def evaluate() -> tuple[int, float, float, list[tuple[str, float, list[str]]]]:
    golden = json.loads((EVALS_DIR / "golden.json").read_text(encoding="utf-8"))
    fx = np.load(EVALS_DIR / "fixture.npz", allow_pickle=False)

    k = int(golden.get("k", 5))
    threshold = float(golden.get("recall_threshold", 0.75))
    items_by_id = {it["id"]: it for it in golden["items"]}

    corpus_sources = [str(s) for s in fx["corpus_sources"]]
    corpus_vecs = _normalize(fx["corpus_vecs"].astype(np.float64))
    query_ids = [str(q) for q in fx["query_ids"]]
    query_vecs = _normalize(fx["query_vecs"].astype(np.float64))

    results: list[tuple[str, float, list[str]]] = []
    for qid, qv in zip(query_ids, query_vecs):
        sims = corpus_vecs @ qv
        topk_idx = np.argsort(-sims)[:k]
        topk_sources = [corpus_sources[i] for i in topk_idx]
        topk_set = set(topk_sources)
        expected = items_by_id[qid]["expected_sources"]
        hits = sum(1 for s in expected if s in topk_set)
        recall = hits / len(expected) if expected else 0.0
        results.append((qid, recall, topk_sources))

    mean_recall = sum(r for _, r, _ in results) / len(results) if results else 0.0
    return k, mean_recall, threshold, results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assert", dest="do_assert", action="store_true")
    args = ap.parse_args()

    k, mean_recall, threshold, results = evaluate()
    print(f"recall@{k} over {len(results)} golden queries: {mean_recall:.3f}  (threshold {threshold})")
    for qid, recall, _tops in results:
        mark = "PASS" if recall >= 1.0 else ("part" if recall > 0 else "MISS")
        print(f"  [{mark:>4}] {qid:22s} recall={recall:.2f}")

    if args.do_assert and mean_recall < threshold:
        print(f"\nFAIL: recall@{k} {mean_recall:.3f} < threshold {threshold}")
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
