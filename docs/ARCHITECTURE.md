# Architecture: baseline now, multi-agent next

## Baseline (what is in this repository)

```
question + role
      |
      v
  [ retrieve ]  cosine top-4 over 56 chunks, no filter, no rerank
      |
      v
  [ generate ]  one pass: answer only from the 4 passages, cite [C1]..[C4],
      |         or reply INSUFFICIENT_CONTEXT
      v
  answer + citations + latency
```

One retrieval call, one generation call, one global similarity threshold for abstention.
`role` is recorded but never used to filter. Everything is synchronous and stateless.

## Where the baseline breaks

The evaluation (`run_eval.py`, 32 questions) locates the failures precisely:

| Failure | Evidence | Root cause |
|---------|----------|------------|
| Confidential document reaches an unauthorised asker | 7 / 32 questions leak `HR-002`; a contractor asking for salary bands receives the full table | No authorisation anywhere in the retrieval path |
| Multi-hop questions answered halfway | Q16: both `IT-001` and `SEC-001` are retrieved, but the answer never mentions the second required approver | One flat top-k list; nothing decides that a second sub-question exists |
| Never says "I don't know" | 0 / 8 correct abstentions | A single cosine threshold cannot separate "no answer exists" from "answer exists but is worded differently" |
| Answers drift to adjacent topics | key-fact coverage 68% vs. answer-correct 50% | Sentences are selected by similarity to the *question*, with nothing checking that the claim is responsive |

Retrieval recall is 100% at this corpus size, so at Phase 1 the bottleneck is not finding the
text — it is deciding what to do with it.

## Planned multi-agent system (Phase 2)

```
question + role
      |
      v
[ Planner ]------- decomposes into sub-questions, chooses which domains to search
      |
      +--> [ HR retriever ]        \
      +--> [ IT / Eng retriever ]   >  each: ACL filter -> hybrid BM25 + dense -> rerank
      +--> [ Security retriever ]  /
      |
      v
[ Verifier ] ----- checks every claim against its cited passage; unsupported claims
      |            are dropped and the sub-question is re-sent to its retriever
      v
[ Composer ] ----- merges verified claims into one cited answer, or abstains
```

Built on LangGraph so the loop between Verifier and the retrievers is an explicit graph edge
with a bounded retry count, and so intermediate state (sub-questions, per-hop citations,
retry count) is inspectable when a run goes wrong.

**Design commitments carried over from the baseline's failures:**

1. **Authorisation is a filter applied before ranking, not a prompt instruction.** A chunk the
   asker cannot read is never scored, never retrieved, and never enters a context window. The
   `acl_leaks` metric must go to 0 and stay there.
2. **Abstention becomes a decision the Verifier makes** from citation support, not a similarity
   threshold on the retriever.
3. **Each hop keeps its own citations** so a partially-answered multi-hop question is visible
   as "hop 2 unsupported" instead of quietly returning half an answer.

## Interfaces the replacements must satisfy

- `VectorIndex.search(query, k) -> [(chunk_index, score)]` — swapping the numpy matrix for
  Chroma or Qdrant means implementing this and nothing else.
- `generate(question, hits, provider, model) -> {text, provider, cited_indices, error}` —
  the multi-agent composer plugs in here.
- `run_eval.py` is fixed. Any Phase 2 configuration is scored by the same script against the
  same 32 questions, so improvements are attributable to the component that changed.
