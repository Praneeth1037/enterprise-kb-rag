#!/usr/bin/env python3
"""Score the baseline on the gold question set.

    python run_eval.py
    python run_eval.py --provider extractive --limit 10

Metrics
-------
retrieval_hit@k     answerable questions where at least one gold document was retrieved
retrieval_recall    mean fraction of a question's gold documents that were retrieved
key_fact_coverage   mean fraction of the required facts that appear in the answer
answer_correct      answerable questions where every required fact appears
abstain_correct     unanswerable/restricted questions where the system abstained
false_abstain       answerable questions the system refused anyway
acl_leaks           questions where a document above the asker's clearance was retrieved

Fact checking is exact substring matching against a short list of required
strings per question. It is crude, but it is deterministic and free, which is
what a baseline needs. An LLM-as-judge scorer is Phase 2 work.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import statistics
import time

from src.pipeline import DEFAULT_ABSTAIN_THRESHOLD, DEFAULT_TOP_K, KnowledgeBase

ROOT = pathlib.Path(__file__).resolve().parent


def normalise(text: str) -> str:
    """Lowercase and squash whitespace so '16  weeks' matches '16 weeks'."""
    return re.sub(r"\s+", " ", text.lower())


def fact_present(fact: str, answer: str) -> bool:
    return normalise(fact) in normalise(answer)


def load_gold(path: pathlib.Path, limit: int = 0) -> list:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return rows[:limit] if limit else rows


def main() -> int:
    p = argparse.ArgumentParser(description="Evaluate the baseline RAG pipeline.")
    p.add_argument("--corpus", default=str(ROOT / "data" / "corpus"))
    p.add_argument("--gold", default=str(ROOT / "data" / "gold" / "questions.jsonl"))
    p.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p.add_argument("--embedder", default="tfidf", choices=["tfidf", "minilm", "auto"],
                   help="tfidf is offline and deterministic; minilm needs sentence-transformers")
    p.add_argument("--provider", default="auto",
                   choices=["auto", "openai", "anthropic", "gemini", "extractive"])
    p.add_argument("--abstain-threshold", type=float,
                   default=DEFAULT_ABSTAIN_THRESHOLD)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", default=str(ROOT / "outputs" / "eval_report.json"))
    args = p.parse_args()

    gold = load_gold(pathlib.Path(args.gold), args.limit)
    kb = KnowledgeBase(args.corpus, embedder_kind=args.embedder)
    st = kb.stats()

    print("=" * 92)
    print("BASELINE EVALUATION - Enterprise Knowledge Base RAG")
    print("=" * 92)
    print(f"corpus   : {st['documents']} docs / {st['chunks']} chunks    "
          f"embedder: {st['embedder']} ({st['dims']}d)    top_k: {args.top_k}")
    print(f"questions: {len(gold)}    abstain threshold: {args.abstain_threshold}")
    print("-" * 92)
    print(f"{'QID':<5}{'TYPE':<16}{'ROLE':<11}{'RETR':<7}{'FACTS':<8}"
          f"{'ABSTAIN':<9}{'ACL':<6}{'ms':>7}  VERDICT")
    print("-" * 92)

    rows, latencies = [], []
    t_wall = time.perf_counter()

    for g in gold:
        res = kb.answer(
            g["question"], role=g.get("role", "employee"), k=args.top_k,
            provider=args.provider, abstain_threshold=args.abstain_threshold,
        )
        retrieved_docs = {h["doc_id"] for h in res["retrieved"]}
        gold_docs = set(g.get("gold_doc_ids", []))
        forbidden = set(g.get("forbidden_doc_ids", []))

        recall = (len(gold_docs & retrieved_docs) / len(gold_docs)) if gold_docs else None
        hit = bool(gold_docs & retrieved_docs) if gold_docs else None

        facts = g.get("key_facts", [])
        found = [f for f in facts if fact_present(f, res["answer"])]
        coverage = (len(found) / len(facts)) if facts else None

        leaked = sorted(forbidden & retrieved_docs) or res["retrieved_above_clearance"]
        should_abstain = bool(g.get("should_abstain"))
        abstained = bool(res["abstained"])

        if should_abstain:
            ok = abstained and not leaked
            verdict = "PASS" if ok else ("FAIL leaked" if leaked else "FAIL answered anyway")
        else:
            ok = bool(facts) and len(found) == len(facts) and not abstained
            if abstained:
                verdict = "FAIL false abstain"
            elif ok:
                # Answer is right, but the retriever still pulled a document the
                # asker is not cleared to read. Flagged, not silently passed.
                verdict = "PASS (acl leak)" if leaked else "PASS"
            else:
                missing = [f for f in facts if f not in found]
                verdict = f"FAIL missing {missing}"

        latencies.append(res["latency_ms"])
        rows.append({
            "qid": g["qid"], "type": g["type"], "role": g.get("role", "employee"),
            "question": g["question"], "gold_doc_ids": sorted(gold_docs),
            "retrieved_doc_ids": sorted(retrieved_docs), "retrieval_hit": hit,
            "retrieval_recall": recall, "key_facts": facts, "facts_found": found,
            "key_fact_coverage": coverage, "should_abstain": should_abstain,
            "abstained": abstained, "acl_leak_docs": leaked, "passed": bool(ok),
            "verdict": verdict, "latency_ms": res["latency_ms"],
            "answer": res["answer"],
        })

        print(f"{g['qid']:<5}{g['type']:<16}{g.get('role','employee'):<11}"
              f"{('-' if hit is None else ('hit' if hit else 'MISS')):<7}"
              f"{('-' if coverage is None else f'{coverage:.0%}'):<8}"
              f"{('yes' if abstained else 'no'):<9}"
              f"{('LEAK' if leaked else 'ok'):<6}"
              f"{res['latency_ms']:>7.0f}  {verdict}")

    wall = time.perf_counter() - t_wall

    answerable = [r for r in rows if not r["should_abstain"]]
    refusals = [r for r in rows if r["should_abstain"]]
    hits = [r for r in answerable if r["retrieval_hit"] is not None]

    def mean(xs):
        return round(statistics.fmean(xs), 3) if xs else 0.0

    summary = {
        "questions": len(rows),
        "answerable": len(answerable),
        "should_abstain": len(refusals),
        "retrieval_hit_at_k": mean([1.0 if r["retrieval_hit"] else 0.0 for r in hits]),
        "retrieval_recall": mean([r["retrieval_recall"] for r in hits]),
        "key_fact_coverage": mean([r["key_fact_coverage"] for r in answerable
                                   if r["key_fact_coverage"] is not None]),
        "answer_correct": mean([1.0 if r["passed"] else 0.0 for r in answerable]),
        "abstain_correct": mean([1.0 if r["passed"] else 0.0 for r in refusals]),
        "false_abstain": sum(1 for r in answerable if r["abstained"]),
        "acl_leaks": sum(1 for r in rows if r["acl_leak_docs"]),
        "overall_pass_rate": mean([1.0 if r["passed"] else 0.0 for r in rows]),
        "latency_p50_ms": round(statistics.median(latencies), 1),
        "latency_p95_ms": round(sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)], 1),
        "wall_seconds": round(wall, 1),
        "config": {
            "embedder": st["embedder"], "dims": st["dims"], "top_k": args.top_k,
            "abstain_threshold": args.abstain_threshold,
            "provider": rows and "mixed" or args.provider,
            "documents": st["documents"], "chunks": st["chunks"],
        },
    }

    print("-" * 92)
    print("SUMMARY")
    print("-" * 92)
    print(f"  retrieval hit@{args.top_k}      {summary['retrieval_hit_at_k']:.1%}"
          f"   ({len(hits)} answerable questions)")
    print(f"  retrieval recall       {summary['retrieval_recall']:.1%}")
    print(f"  key-fact coverage      {summary['key_fact_coverage']:.1%}")
    print(f"  answer correct         {summary['answer_correct']:.1%}"
          f"   ({sum(1 for r in answerable if r['passed'])}/{len(answerable)})")
    print(f"  correct abstentions    {summary['abstain_correct']:.1%}"
          f"   ({sum(1 for r in refusals if r['passed'])}/{len(refusals)})")
    print(f"  false abstentions      {summary['false_abstain']}")
    print(f"  ACCESS-CONTROL LEAKS   {summary['acl_leaks']}  "
          f"<-- baseline has no ACL filter")
    print(f"  overall pass rate      {summary['overall_pass_rate']:.1%}")
    print(f"  latency p50 / p95      {summary['latency_p50_ms']:.0f} ms / "
          f"{summary['latency_p95_ms']:.0f} ms      total {summary['wall_seconds']}s")
    print("=" * 92)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": rows}, indent=2),
                   encoding="utf-8")
    try:
        shown = out.resolve().relative_to(ROOT)
    except ValueError:
        shown = out
    print(f"report written to {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
