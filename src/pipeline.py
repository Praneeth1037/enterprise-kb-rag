"""The baseline pipeline, end to end.

    ingest -> chunk -> embed -> index -> retrieve top-k -> generate with citations

One pass, no query rewriting, no hybrid search, no reranking, no agents, and --
importantly -- no access control. ``role`` is carried through the request and
written to the output, but the baseline never uses it to filter retrieval. That
gap is measured by the eval harness as ``acl_leaks`` and is the first thing
Phase 2 fixes.
"""

from __future__ import annotations

import time
from typing import Dict, List

from .chunker import chunk_documents
from .embedder import get_embedder
from .generator import ABSTAIN_TOKEN, generate
from .index import VectorIndex
from .ingest import load_corpus

DEFAULT_TOP_K = 4
DEFAULT_ABSTAIN_THRESHOLD = 0.25

# Which sensitivity classes each role is allowed to see. The baseline does NOT
# enforce this; the evaluator uses it to count leaks.
ROLE_CLEARANCE: Dict[str, set] = {
    "contractor": {"public", "internal"},
    "employee": {"public", "internal"},
    "manager": {"public", "internal", "confidential"},
    "hr": {"public", "internal", "confidential"},
    "executive": {"public", "internal", "confidential", "restricted"},
}


class KnowledgeBase:
    def __init__(self, corpus_dir: str, embedder_kind: str = "auto") -> None:
        t0 = time.perf_counter()
        self.documents = load_corpus(corpus_dir)
        self.chunks = chunk_documents(self.documents)
        self.index = VectorIndex.build(self.chunks, get_embedder(embedder_kind))
        self.build_seconds = round(time.perf_counter() - t0, 2)

    def stats(self) -> dict:
        out = self.index.stats()
        out["build_seconds"] = self.build_seconds
        return out

    def retrieve(self, question: str, k: int = DEFAULT_TOP_K) -> List[dict]:
        hits = []
        for rank, (idx, score) in enumerate(self.index.search(question, k=k), start=1):
            c = self.chunks[idx]
            hits.append(
                {
                    "rank": rank,
                    "score": round(score, 4),
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "title": c.title,
                    "heading": c.heading,
                    "department": c.department,
                    "sensitivity": c.sensitivity,
                    "source_name": c.source_name,
                    "raw_text": c.raw_text,
                }
            )
        return hits

    def answer(
        self,
        question: str,
        role: str = "employee",
        k: int = DEFAULT_TOP_K,
        provider: str = "auto",
        model: str = "",
        abstain_threshold: float = DEFAULT_ABSTAIN_THRESHOLD,
    ) -> dict:
        t_start = time.perf_counter()

        t0 = time.perf_counter()
        hits = self.retrieve(question, k=k)
        retrieve_ms = (time.perf_counter() - t0) * 1000

        top_score = hits[0]["score"] if hits else 0.0

        # Crude single global cutoff. It is the only abstention mechanism the
        # baseline has, and it is one of the things the eval is meant to expose.
        if top_score < abstain_threshold:
            answer_text = ABSTAIN_TOKEN
            provider_used = "threshold"
            cited: List[int] = []
            generate_ms = 0.0
            error = None
        else:
            t0 = time.perf_counter()
            result = generate(question, hits, provider=provider, model=model)
            generate_ms = (time.perf_counter() - t0) * 1000
            answer_text = str(result["text"])
            provider_used = str(result["provider"])
            cited = list(result["cited_indices"])  # type: ignore[arg-type]
            error = result["error"]

        abstained = answer_text.strip().upper().startswith(ABSTAIN_TOKEN)
        citations = [] if abstained else [
            {key: hits[i][key] for key in
             ("chunk_id", "doc_id", "title", "heading", "department",
              "sensitivity", "score")}
            for i in cited
        ]

        allowed = ROLE_CLEARANCE.get(role, {"public", "internal"})
        over_clearance = sorted({h["doc_id"] for h in hits
                                 if h["sensitivity"] not in allowed})

        return {
            "question": question,
            "role": role,
            "answer": ("I could not find this in the knowledge base."
                       if abstained else answer_text),
            "abstained": abstained,
            "provider": provider_used,
            "top_k": k,
            "top_score": top_score,
            "citations": citations,
            "retrieved": [
                {key: h[key] for key in
                 ("rank", "score", "chunk_id", "doc_id", "title", "heading",
                  "department", "sensitivity")}
                for h in hits
            ],
            # Diagnostic only. The baseline retrieved these anyway.
            "retrieved_above_clearance": over_clearance,
            "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "timings_ms": {
                "retrieve": round(retrieve_ms, 1),
                "generate": round(generate_ms, 1),
            },
            "error": error,
        }
