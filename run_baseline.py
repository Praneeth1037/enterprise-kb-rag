#!/usr/bin/env python3
"""Run one question through the baseline RAG pipeline.

Examples
--------
    python run_baseline.py --input examples/test1.txt
    python run_baseline.py --question "How many PTO days do I get?" --role employee
    python run_baseline.py --input examples/test3.txt --role contractor --show-context
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from src.pipeline import DEFAULT_ABSTAIN_THRESHOLD, DEFAULT_TOP_K, KnowledgeBase

ROOT = pathlib.Path(__file__).resolve().parent
BAR = "=" * 78


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Baseline RAG over the Northwind Robotics knowledge base.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="path to a text file containing the question")
    src.add_argument("--question", help="the question, given inline")

    p.add_argument("--role", default="employee",
                   choices=["employee", "contractor", "manager", "hr", "executive"],
                   help="who is asking (recorded, but NOT enforced by the baseline)")
    p.add_argument("--corpus", default=str(ROOT / "data" / "corpus"))
    p.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p.add_argument("--embedder", default="tfidf", choices=["tfidf", "minilm", "auto"],
                   help="tfidf is offline and deterministic; minilm needs sentence-transformers")
    p.add_argument("--provider", default="auto",
                   choices=["auto", "openai", "anthropic", "gemini", "extractive"])
    p.add_argument("--model", default="", help="override the provider's default model")
    p.add_argument("--abstain-threshold", type=float,
                   default=DEFAULT_ABSTAIN_THRESHOLD)
    p.add_argument("--show-context", action="store_true",
                   help="print the retrieved passages in full")
    p.add_argument("--out", default=str(ROOT / "outputs" / "last_run.json"))
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.input:
        path = pathlib.Path(args.input)
        if not path.is_file():
            print(f"error: input file not found: {path}", file=sys.stderr)
            return 2
        question = path.read_text(encoding="utf-8").strip()
    else:
        question = args.question.strip()

    if not question:
        print("error: empty question", file=sys.stderr)
        return 2

    print(BAR)
    print("ENTERPRISE KNOWLEDGE BASE - BASELINE RAG")
    print(BAR)

    kb = KnowledgeBase(args.corpus, embedder_kind=args.embedder)
    st = kb.stats()
    print(f"corpus     : {st['documents']} documents -> {st['chunks']} chunks "
          f"(mean {st['mean_chunk_chars']} chars)")
    print(f"embedder   : {st['embedder_detail']}  [{st['dims']} dims]")
    print(f"index build: {st['build_seconds']}s\n")

    print(f"ROLE       : {args.role}")
    print(f"QUESTION   : {question}\n")

    res = kb.answer(
        question,
        role=args.role,
        k=args.top_k,
        provider=args.provider,
        model=args.model,
        abstain_threshold=args.abstain_threshold,
    )

    print(f"RETRIEVED TOP-{res['top_k']}")
    print("-" * 78)
    for h in res["retrieved"]:
        flag = "  <-- ABOVE ASKER'S CLEARANCE" if h["doc_id"] in res[
            "retrieved_above_clearance"] else ""
        print(f"  [C{h['rank']}] {h['score']:+.3f}  {h['chunk_id']:<12} "
              f"{h['department']:<12} {h['sensitivity']:<12} "
              f"{h['title'][:34]}{flag}")

    if args.show_context:
        print("\nCONTEXT PASSAGES")
        print("-" * 78)
        for h in kb.retrieve(question, k=args.top_k):
            print(f"\n[C{h['rank']}] {h['title']} > {h['heading']}")
            print(h["raw_text"])

    print(f"\nANSWER  (provider={res['provider']}, {res['latency_ms']} ms)")
    print("-" * 78)
    print(res["answer"])

    if res["citations"]:
        print("\nCITATIONS")
        print("-" * 78)
        for c in res["citations"]:
            print(f"  {c['chunk_id']:<12} {c['title']} > {c['heading']}  "
                  f"({c['sensitivity']})")
    elif res["abstained"]:
        print("\n[abstained - top score "
              f"{res['top_score']:.3f} < threshold {args.abstain_threshold}]")

    if res["retrieved_above_clearance"]:
        print("\n!! ACCESS-CONTROL LEAK: retrieved "
              f"{', '.join(res['retrieved_above_clearance'])} which a "
              f"'{args.role}' is not cleared to read.")
        print("   The baseline has no ACL filter. This is a known gap, not a surprise.")

    if res["error"]:
        print(f"\n[note] {res['error']}")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    try:
        shown = out_path.resolve().relative_to(ROOT)
    except ValueError:
        shown = out_path
    print(f"\nfull JSON written to {shown}")
    print(BAR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
