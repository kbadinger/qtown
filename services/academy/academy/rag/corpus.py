"""
Corpus ingestion for the Academy RAG system — the "town explains itself" corpus.

Chunks qtown's own real documentation and embeds it into academy.embeddings
(doc_type='doc') so the RAG can answer grounded, *cited* questions about the
system it is part of. Idempotent: re-running upserts by doc_id.

Run (needs Postgres + Ollama):
    python -m academy.rag.corpus              # ingest into pgvector
    python -m academy.rag.corpus --list       # list files + chunk count, no embedding
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any

from academy.rag.embeddings import BaseEmbedder

logger = logging.getLogger("academy.rag.corpus")

# Curated set of real qtown docs — globs relative to the repo root. These are the
# authoritative WHAT/HOW/status docs; retrieving over them makes the RAG answer
# questions about qtown itself, with verifiable ground truth for the eval set.
CORPUS_GLOBS = [
    "CLAUDE.md",
    "AGENTS.md",
    "docs/REQUIREMENTS.md",
    "docs/v2-audit.md",
    "docs/adr/*.md",
    "docs/perf/*.md",
    "docs/plans/AREA-TECH-TEACHING-PLAN.md",
    "docs/plans/06-FABLE-PLAN.md",
    "services/*/README.md",
]

MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 60
OVERLAP_CHARS = 150

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


class DocsEmbedder(BaseEmbedder):
    """Embeds documentation chunks — the self-referential RAG corpus."""

    doc_type = "doc"


def repo_root() -> Path:
    """Repo root: env override for CI, else four levels up from this file."""
    env = os.environ.get("QTOWN_REPO_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4]


def iter_corpus_files(root: Path) -> list[Path]:
    """Resolve the curated globs to a de-duplicated, sorted file list."""
    seen: dict[Path, None] = {}
    for pattern in CORPUS_GLOBS:
        for p in sorted(root.glob(pattern)):
            if p.is_file():
                seen.setdefault(p.resolve(), None)
    return list(seen.keys())


def _doc_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) == 1:
            return m.group(2).strip()
    return fallback


def _window(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text] if text else []
    out: list[str] = []
    start = 0
    while start < len(text):
        out.append(text[start : start + size])
        if start + size >= len(text):
            break
        start += size - overlap
    return out


def chunk_markdown(text: str, source: str, title: str) -> list[dict[str, Any]]:
    """
    Split markdown into section chunks on h1/h2 boundaries (h3+ stay within their
    section for coherence). Each chunk is prefixed with "title › heading" so a
    retrieved snippet carries its own context, and long sections are windowed.
    """
    sections: list[tuple[str, list[str]]] = []
    cur_heading = ""
    cur_lines: list[str] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) <= 2:
            if cur_lines or cur_heading:
                sections.append((cur_heading, cur_lines))
            cur_heading = m.group(2).strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    if cur_lines or cur_heading:
        sections.append((cur_heading, cur_lines))

    chunks: list[dict[str, Any]] = []
    idx = 0
    for heading, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        prefix = f"{title} › {heading}" if heading else title
        for window in _window(body, MAX_CHUNK_CHARS, OVERLAP_CHARS):
            content = f"{prefix}\n\n{window}".strip()
            if len(content) < MIN_CHUNK_CHARS:
                continue
            chunks.append(
                {
                    "doc_id": f"{source}#{idx}",
                    "content": content,
                    "metadata": {"source": source, "title": title, "heading": heading},
                }
            )
            idx += 1
    return chunks


def build_corpus(root: Path) -> list[dict[str, Any]]:
    """Chunk every corpus file into embeddable documents."""
    docs: list[dict[str, Any]] = []
    for path in iter_corpus_files(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        title = _doc_title(text, path.stem)
        docs.extend(chunk_markdown(text, rel, title))
    return docs


async def ingest_corpus(root: Path | None = None) -> int:
    """Chunk + embed + upsert the whole corpus. Returns the chunk count."""
    root = root or repo_root()
    docs = build_corpus(root)
    logger.info("corpus: %d chunks from %s", len(docs), root)
    embedder = DocsEmbedder()
    # Embed in batches (sequential Ollama calls); upsert each by doc_id.
    for i in range(0, len(docs), 32):
        await embedder.embed_and_store_batch(docs[i : i + 32])
        logger.info("  embedded %d/%d", min(i + 32, len(docs)), len(docs))
    return len(docs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest the qtown-docs RAG corpus.")
    ap.add_argument("--list", action="store_true", help="list files + chunk count, no embedding")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = repo_root()

    if args.list:
        files = iter_corpus_files(root)
        for p in files:
            print(p.relative_to(root).as_posix())
        print(f"\n{len(files)} files -> {len(build_corpus(root))} chunks")
        return

    n = asyncio.run(ingest_corpus(root))
    print(f"ingested {n} chunks into academy.embeddings")


if __name__ == "__main__":
    main()
