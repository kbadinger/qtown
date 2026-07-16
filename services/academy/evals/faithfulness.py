"""
Faithfulness eval (W1-A3) — LOCAL, produces a committed report (needs Ollama +
pgvector).

Runs the grounded answerer over the golden set and scores each answer two ways:
  - keyword correctness: does the answer contain the expected facts
    (golden.answer_contains)?
  - LLM-judge faithfulness: is every claim supported by the cited sources
    (no fabrication)? — a strict judge model returns a 0-1 score.

Writes a dated report to docs/evals/academy-rag-eval.md. This is NOT a CI gate
(it needs live models); the deterministic recall@k gate (evals/recall.py) is what
CI enforces. Same honesty pattern as the M7 perf report: measured locally, dated,
committed.

    python -m evals.faithfulness
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from academy.ollama_client import OllamaClient
from academy.rag.answer import RAG_ANSWER_MODEL, RETRIEVE_K, get_answerer
from academy.rag.retriever import get_retriever

EVALS_DIR = Path(__file__).resolve().parent
GOLDEN = EVALS_DIR / "golden.json"
REPORT = EVALS_DIR.parents[2] / "docs" / "evals" / "academy-rag-eval.md"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen3.5:9b")

@dataclass
class _Row:
    id: str
    grounded: bool
    kw_ok: bool
    kw: str
    faithful: bool
    score: float
    latency_ms: float
    reason: str


def _clip(text: str, limit: int = 200) -> str:
    """Trim to a word boundary with an ellipsis — keeps committed notes readable."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"


_JUDGE_SYSTEM = (
    "You are a strict RAG evaluator. Judge ONLY whether the answer's claims are "
    "supported by the provided sources — no outside knowledge, no benefit of the "
    "doubt. An answer that adds unsupported facts is not faithful."
)


async def _judge(
    ollama: OllamaClient, question: str, answer: str, sources_text: str
) -> tuple[float, bool, str]:
    prompt = (
        f"Question: {question}\n\nSources:\n{sources_text}\n\nAnswer:\n{answer}\n\n"
        "Is every claim in the answer supported by the sources? Respond with JSON: "
        '{"faithful": true|false, "score": 0.0-1.0, "reason": "<short>"}'
    )
    meta = await ollama.generate_with_metadata(
        JUDGE_MODEL,
        prompt,
        system=_JUDGE_SYSTEM,
        temperature=0.0,
        max_tokens=250,
        format="json",
        think=False,
    )
    try:
        data = json.loads(str(meta.get("response", "")))
        return (
            float(data.get("score", 0.0)),
            bool(data.get("faithful", False)),
            _clip(str(data.get("reason", ""))),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0.0, False, "unparseable judge output"


def _stamp() -> str:
    # Date is passed in via env so the module stays import-time deterministic.
    return os.environ.get("EVAL_DATE", "unknown-date")


async def main() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    items = golden["items"]
    answerer = get_answerer()
    retriever = get_retriever()
    ollama = OllamaClient()

    rows: list[_Row] = []
    for it in items:
        res = await answerer.answer(it["question"])
        ans_lower = res.answer.lower()
        keywords = it.get("answer_contains", [])
        kw_hits = sum(1 for k in keywords if k.lower() in ans_lower)
        kw_ok = kw_hits == len(keywords) if keywords else True

        # Judge against the FULL passages the generator saw — not the truncated
        # citation snippets — else the judge penalises support past the preview.
        # Retrieval is deterministic (fixed corpus embeddings), so these match.
        docs = await retriever.search(it["question"], k=RETRIEVE_K)
        src_text = (
            "\n\n".join(
                f"[{i}] ({d.metadata.get('source', d.doc_id)}) {d.content}"
                for i, d in enumerate(docs, 1)
            )
            or "(no sources)"
        )
        score, faithful, reason = await _judge(ollama, it["question"], res.answer, src_text)

        rows.append(
            _Row(
                id=it["id"],
                grounded=res.grounded,
                kw_ok=kw_ok,
                kw=f"{kw_hits}/{len(keywords)}",
                faithful=faithful,
                score=score,
                latency_ms=res.latency_ms,
                reason=reason,
            )
        )
        print(f"  {it['id']:22s} grounded={res.grounded} kw={kw_hits}/{len(keywords)} faith={score:.2f}")

    n = len(rows)
    grounded_rate = sum(1 for r in rows if r.grounded) / n
    kw_rate = sum(1 for r in rows if r.kw_ok) / n
    faith_mean = sum(r.score for r in rows) / n
    faith_rate = sum(1 for r in rows if r.faithful) / n
    lat_mean = sum(r.latency_ms for r in rows) / n

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Academy RAG — faithfulness eval",
        "",
        "**Measured locally, not a CI gate.** The deterministic retrieval gate is",
        "`evals/recall.py` (recall@k over a committed fixture, blocking in CI). This",
        "report measures *generation* quality of the grounded answerer over the golden",
        "set — it needs live Ollama + pgvector, so it is run by hand and committed dated,",
        "the same honesty pattern as the M7 perf report. Generation runs at temperature",
        "0.2, so this is a point-in-time snapshot, not a fixed number.",
        "",
        "| | |",
        "|---|---|",
        f"| Date | {_stamp()} |",
        f"| Answer model | `{RAG_ANSWER_MODEL}` |",
        f"| Judge model | `{JUDGE_MODEL}` |",
        f"| Golden questions | {n} |",
        f"| Grounded (answer cited real retrieved sources) | {grounded_rate:.0%} |",
        f"| Keyword correctness (conservative substring) | {kw_rate:.0%} |",
        f"| Judge faithfulness — mean score | {faith_mean:.2f} |",
        f"| Judge faithfulness — faithful rate | {faith_rate:.0%} |",
        f"| Mean answer latency | {lat_mean:.0f} ms |",
        "",
        "## What each metric means (and its limits)",
        "",
        "- **Grounded** — the answerer emitted at least one citation to a real retrieved",
        "  passage. An answer that can't be grounded is returned as an honest \"I don't",
        "  have that\" (grounded=no), never a fabricated fact (principle #1).",
        "- **Keyword correctness** — a *conservative* check: does the answer contain every",
        "  expected substring? It under-counts, e.g. an answer that says \"retrieval-",
        "  augmented generation\" fails the literal `RAG` check while still being correct.",
        "- **Judge faithfulness** — an independent judge model scores whether every claim",
        "  in the answer is supported by the passages the generator was shown (all k, full",
        "  text — not the truncated UI snippet). It is an LLM judgment, not ground truth.",
        "",
        "## Per-question",
        "",
        "| Question | grounded | keywords | faithful | score | note |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        # Only annotate genuine faithfulness/grounding failures; a keyword partial is
        # already visible in its own column and explained above, so it needs no note.
        note = "" if (r.grounded and r.faithful) else r.reason
        lines.append(
            f"| {r.id} | {'yes' if r.grounded else 'no'} | {r.kw} "
            f"| {'yes' if r.faithful else 'no'} | {r.score:.2f} | {note} |"
        )
    lines.append("")
    lines.append(
        "Reproduce: `cd services/academy && python -m evals.faithfulness` "
        "(regenerate the retrieval fixture first with `python -m evals.build_fixture`)."
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {REPORT}")
    print(
        f"grounded={grounded_rate:.0%} kw={kw_rate:.0%} "
        f"faith_mean={faith_mean:.2f} faith_rate={faith_rate:.0%}"
    )


if __name__ == "__main__":
    asyncio.run(main())
