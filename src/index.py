"""Stage 5 - Vector store (baseline version).

The baseline stores the whole matrix in memory and scores with a single dot
product. With ~120 chunks that is faster than any real vector database and has
zero setup cost, which matters more than scale for a reproducible baseline.

Swapping this for Chroma / Qdrant / pgvector is Phase 2 work, and the interface
here (``search`` returning ``(index, score)`` pairs) is what the replacement has
to satisfy.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .chunker import Chunk


class VectorIndex:
    def __init__(self, chunks: List[Chunk], matrix: np.ndarray, embedder) -> None:
        if len(chunks) != matrix.shape[0]:
            raise ValueError("chunk count and matrix row count disagree")
        self.chunks = chunks
        self.matrix = matrix.astype(np.float32)
        self.embedder = embedder

    @classmethod
    def build(cls, chunks: List[Chunk], embedder) -> "VectorIndex":
        matrix = embedder.fit_transform([c.text for c in chunks])
        return cls(chunks, matrix, embedder)

    def search(self, query: str, k: int = 4) -> List[Tuple[int, float]]:
        """Cosine similarity over every chunk. No filtering, no reranking."""
        qvec = self.embedder.encode([query])[0]
        scores = self.matrix @ qvec
        k = min(k, len(self.chunks))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top]

    def __len__(self) -> int:
        return len(self.chunks)

    def stats(self) -> dict:
        return {
            "chunks": len(self.chunks),
            "documents": len({c.doc_id for c in self.chunks}),
            "dims": int(self.matrix.shape[1]),
            "embedder": self.embedder.name,
            "embedder_detail": self.embedder.description,
            "mean_chunk_chars": round(
                sum(len(c.raw_text) for c in self.chunks) / len(self.chunks), 1
            ),
        }
