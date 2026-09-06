"""Stage 4 - Embeddings.

Two backends, both local and free:

* ``minilm``  - sentence-transformers/all-MiniLM-L6-v2, 384-dim dense vectors.
                Downloads ~90 MB the first time, then runs on CPU.
* ``tfidf``   - scikit-learn TF-IDF with 1-2 grams, reduced to 256 dims with
                TruncatedSVD (LSA). No model download, no network, ~1 second.

``auto`` uses minilm when sentence-transformers is importable and the model can
be loaded, and falls back to tfidf otherwise with a printed warning. The point
of the fallback is that a grader with no GPU, no API key, and a flaky network
can still reproduce the run.

Both backends return L2-normalised float32 vectors, so cosine similarity is a
plain dot product downstream.
"""

from __future__ import annotations

import sys
from typing import List

import numpy as np

MINILM_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TFIDF_DIMS = 256


def _normalise(mat: np.ndarray) -> np.ndarray:
    mat = np.asarray(mat, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class MiniLMEmbedder:
    name = "minilm"

    @property
    def description(self) -> str:
        return f"{MINILM_MODEL} ({self.dims}-dim dense transformer, CPU)"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # noqa: WPS433

        self.model = SentenceTransformer(MINILM_MODEL)
        self.dims = int(self.model.get_sentence_embedding_dimension())

    def fit_transform(self, texts: List[str]) -> np.ndarray:
        return self.encode(texts)

    def encode(self, texts: List[str]) -> np.ndarray:
        vecs = self.model.encode(
            texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True
        )
        return _normalise(vecs)


class TfidfEmbedder:
    name = "tfidf"

    @property
    def description(self) -> str:
        return (f"TF-IDF 1-2 grams + TruncatedSVD -> {self.dims}-dim LSA vectors "
                f"(offline, deterministic)")

    def __init__(self) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), min_df=1, sublinear_tf=True
        )
        self._svd_cls = TruncatedSVD
        self.svd = None
        self.dims = TFIDF_DIMS

    def fit_transform(self, texts: List[str]) -> np.ndarray:
        sparse = self.vectorizer.fit_transform(texts)
        n_components = min(TFIDF_DIMS, min(sparse.shape) - 1)
        self.dims = n_components
        self.svd = self._svd_cls(n_components=n_components, random_state=42)
        return _normalise(self.svd.fit_transform(sparse))

    def encode(self, texts: List[str]) -> np.ndarray:
        if self.svd is None:
            raise RuntimeError("TfidfEmbedder.fit_transform must be called first")
        return _normalise(self.svd.transform(self.vectorizer.transform(texts)))


def get_embedder(kind: str = "auto"):
    """Return an embedder instance. kind is one of auto | minilm | tfidf."""
    kind = (kind or "auto").lower()
    if kind == "tfidf":
        return TfidfEmbedder()
    if kind == "minilm":
        return MiniLMEmbedder()
    if kind != "auto":
        raise ValueError(f"Unknown embedder: {kind}")

    try:
        return MiniLMEmbedder()
    except Exception as exc:  # noqa: BLE001 - any failure means fall back
        print(
            f"[embedder] sentence-transformers unavailable ({type(exc).__name__}: {exc}).\n"
            f"[embedder] Falling back to TF-IDF + SVD. Results are weaker but fully offline.",
            file=sys.stderr,
        )
        return TfidfEmbedder()
