"""Stage 2/3 - Preprocessing and chunking.

Heading-aware fixed-window chunking:

1. Split the document body on markdown headings so a chunk never straddles two
   unrelated sections.
2. If a section is longer than MAX_CHARS, cut it into overlapping windows on
   paragraph boundaries.
3. Prefix every chunk with its document title and heading path, so the heading
   context survives into the embedding and into whatever the model reads.

This is intentionally the naive strategy. Semantic / late chunking and
table-aware splitting are Phase 2 work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from .ingest import Document

MAX_CHARS = 900
OVERLAP_CHARS = 150
MIN_CHARS = 60

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    department: str
    sensitivity: str
    heading: str
    text: str          # heading-prefixed text, what gets embedded
    raw_text: str      # section text on its own, what gets quoted back
    source_name: str

    def label(self) -> str:
        return f"{self.title} > {self.heading}" if self.heading else self.title


def _sections(body: str) -> List[tuple[str, str]]:
    """Split a markdown body into (heading_path, section_text) pairs."""
    sections: List[tuple[str, str]] = []
    stack: List[str] = []
    current: List[str] = []
    heading_path = ""

    def flush() -> None:
        text = "\n".join(current).strip()
        if text:
            sections.append((heading_path, text))

    for line in body.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            current = []
            level = len(m.group(1))
            title = m.group(2).strip()
            stack = stack[: level - 1]
            stack.append(title)
            heading_path = " > ".join(stack[1:]) if len(stack) > 1 else stack[0]
        else:
            current.append(line)
    flush()
    return sections


def _windows(text: str) -> List[str]:
    """Cut an over-long section into overlapping windows on paragraph breaks."""
    if len(text) <= MAX_CHARS:
        return [text]

    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    windows: List[str] = []
    buf = ""
    for para in paragraphs:
        candidate = f"{buf}\n\n{para}".strip() if buf else para
        if len(candidate) <= MAX_CHARS or not buf:
            buf = candidate
        else:
            windows.append(buf)
            # Snap the overlap to a sentence boundary where there is one, and
            # otherwise to a word boundary, so a window never begins mid-word or
            # mid-sentence. Without this the overlap produced partial-sentence
            # duplicates that the generator then quoted twice.
            tail = buf[-OVERLAP_CHARS:]
            sentence_break = re.search(r"(?<=[.!?])\s+", tail)
            if sentence_break:
                tail = tail[sentence_break.end():]
            else:
                space = tail.find(" ")
                if space != -1:
                    tail = tail[space + 1:]
            buf = f"{tail}\n\n{para}".strip()
    if buf:
        windows.append(buf)
    return windows


def chunk_documents(docs: List[Document]) -> List[Chunk]:
    chunks: List[Chunk] = []
    for doc in docs:
        idx = 0
        for heading, section in _sections(doc.body):
            for window in _windows(section):
                if len(window.strip()) < MIN_CHARS:
                    continue
                prefix = f"{doc.title}"
                if heading:
                    prefix += f" - {heading}"
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}#{idx}",
                        doc_id=doc.doc_id,
                        title=doc.title,
                        department=doc.department,
                        sensitivity=doc.sensitivity,
                        heading=heading,
                        text=f"{prefix}\n{window}",
                        raw_text=window,
                        source_name=doc.source_name,
                    )
                )
                idx += 1
    return chunks
