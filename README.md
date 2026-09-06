# Enterprise Knowledge Base Assistant — Runnable Baseline

**CSE 598 Capstone, Phase 1 (Proposal + Baseline)**
Pardha Praneeth Pudi

A grounded question-answering baseline over a small internal-documentation corpus.
You ask a work question, it retrieves passages from the company knowledge base and
answers **only** from those passages, with citations back to the exact section it used.

This repository is the **deliberately naive baseline** for the capstone. It is single-pass
RAG with no agents, no reranking, and no access control, so that the multi-agent system I
build next has something honest to be measured against. The evaluation harness in here is
what will do that measuring.

---

## Easiest way to run it: the notebook

`Enterprise_KB_RAG_Baseline.ipynb` is fully self-contained. Open it in Google Colab
(or any Jupyter kernel) and choose **Runtime → Run all**. It writes the corpus, the gold
set and every pipeline module to disk, then runs the same commands documented below —
no clone, no upload, no API key, under a minute on a free CPU runtime. It ships with its
outputs saved, so the results are readable without running anything.

---

## Or run it as a repository — under a minute either way

```bash
git clone <this-repo-url>
cd enterprise-kb-rag

python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt                         # 3 packages, ~20 MB

python3 run_baseline.py --input examples/test1.txt      # one question
python3 run_eval.py                                     # all 32 gold questions
```

**No API key is required and no model is downloaded.** The default path is fully offline
and deterministic — you will get the same numbers I did. See
[Optional: dense embeddings and a real LLM](#optional-dense-embeddings-and-a-real-llm)
if you want to run the stronger configuration.

Expected wall time on a laptop: dependency install ~15 s, `run_baseline.py` ~2 s,
`run_eval.py` ~2 s.

---

## What problem this is solving

An employee at a mid-size company has a specific question — *how much parental leave do I
get*, *who approves emergency production database access*, *can I ship during the quarter-end
freeze*. The answer exists, but it is buried in one section of one of eleven policy documents
owned by five different teams. Keyword search returns a list of documents; the employee still
has to read them.

The system takes **a question plus the asker's role** and returns **a short answer with
citations, or an explicit "I don't know."** Two things make it harder than a demo chatbot:

1. **Several real questions span two documents.** The incident runbook says who to page; the
   security policy says who must approve emergency access. Neither document answers the
   question alone.
2. **Not every document is readable by every asker.** The compensation bands are marked
   `confidential`. A contractor asking about salary bands must not get them — and the failure
   has to happen at *retrieval*, not by asking the model nicely.

The corpus is synthetic (a fictional company, "Northwind Robotics") so it can be published
without any licensing or confidentiality problem, but it is written to have the structure
that causes these failures: cross-referencing sections, near-duplicate vocabulary across
departments, and one genuinely restricted document.

---

## Repository layout

```
enterprise-kb-rag/
├── Enterprise_KB_RAG_Baseline.ipynb   # self-contained notebook (Colab-ready)
├── run_baseline.py            # CLI: answer one question
├── run_eval.py                # CLI: score the baseline on the gold set
├── requirements.txt           # numpy, PyYAML, scikit-learn
├── requirements-optional.txt  # sentence-transformers (dense embeddings)
├── src/
│   ├── ingest.py              # 1. load markdown + YAML front matter
│   ├── chunker.py             # 2/3. preprocess + heading-aware chunking
│   ├── embedder.py            # 4. TF-IDF+SVD, or MiniLM if installed
│   ├── index.py               # 5. in-memory vector store, cosine search
│   ├── generator.py           # 6. grounded generation + citations + abstain
│   └── pipeline.py            # glue: the end-to-end baseline
├── data/
│   ├── corpus/                # 11 markdown documents (the knowledge base)
│   └── gold/questions.jsonl   # 32 labelled evaluation questions
├── examples/
│   ├── test1.txt .. test4.txt # the four documented test cases
│   └── run_all.sh             # runs all four, then the eval
├── outputs/                   # generated: JSON + captured terminal transcripts
└── docs/ARCHITECTURE.md       # baseline vs. planned multi-agent design
```

**Input** lives in `data/corpus/` (knowledge base) and `data/gold/questions.jsonl`
(evaluation questions). **Output** is written to `outputs/` — `outputs/last_run.json`
for a single question and `outputs/eval_report.json` for the full evaluation.

---

## How the baseline works

Six stages, one pass, no branching:

| # | Stage | What the baseline does | Deliberately missing |
|---|-------|------------------------|----------------------|
| 1 | Ingest | Read `data/corpus/*.md`, parse YAML front matter for `doc_id`, `department`, `sensitivity` | Connectors, incremental sync, PDFs |
| 2/3 | Chunk | Split on markdown headings; windows of ≤900 chars with 150-char overlap; each chunk keeps its heading path | Semantic / late chunking, table-aware splitting |
| 4 | Embed | TF-IDF (1–2 grams) → TruncatedSVD → 55-dim LSA vectors, L2-normalised | Dense transformer embeddings (available via `--embedder minilm`) |
| 5 | Index | All 56 chunk vectors in one numpy matrix; cosine = one dot product | A real vector DB (Chroma / Qdrant / pgvector) |
| 6 | Retrieve | Top-4 by cosine. No filter, no query rewriting, no reranking | Hybrid BM25+dense, cross-encoder rerank, **ACL filter** |
| 7 | Generate | Prompt an LLM to answer only from the numbered passages, citing `[C1]`…`[C4]`, or reply `INSUFFICIENT_CONTEXT`. With no API key, an extractive fallback picks the best-matching sentences from the retrieved chunks and cites them | Verification pass, multi-agent planning, self-correction |

Abstention is a **single global similarity cutoff** (`--abstain-threshold`, default 0.25).
That is the only guardrail the baseline has, and the evaluation shows it is not enough.

`--role` is accepted, recorded in the output, and **not enforced**. The pipeline computes
which retrieved documents were above the asker's clearance and reports them, so the leak is
measured rather than hidden. Closing that gap is the first item of Phase 2 work.

### Why start here

Every stage a production RAG system has is present in a form simple enough to read in one
sitting, and every planned improvement replaces exactly one of them. Because the harness,
the corpus and the gold set stay fixed, each change in Phase 2 can be attributed to the
component that caused it instead of to "the new system."

---

## Reproducing the results

### 1. Requirements

- Python **3.9+** (developed on 3.11)
- `pip install -r requirements.txt` — numpy, PyYAML, scikit-learn
- **No API keys. No network access needed after install. No GPU.**

### 2. Run one question

```bash
python3 run_baseline.py --input examples/test1.txt
```

or inline, with a role:

```bash
python3 run_baseline.py --question "Who approves a Plus-tier laptop?" --role employee
```

Useful flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `--input FILE` / `--question STR` | — | the question (one is required) |
| `--role` | `employee` | `employee`, `contractor`, `manager`, `hr`, `executive` |
| `--top-k` | `4` | passages retrieved |
| `--embedder` | `tfidf` | `tfidf`, `minilm`, or `auto` |
| `--provider` | `auto` | `auto`, `openai`, `anthropic`, `gemini`, `extractive` |
| `--abstain-threshold` | `0.25` | below this top similarity, refuse to answer |
| `--show-context` | off | print the retrieved passages in full |
| `--out` | `outputs/last_run.json` | where the JSON result goes |

### 3. Run the four documented test cases and the full evaluation

```bash
bash examples/run_all.sh
```

or just the evaluation:

```bash
python3 run_eval.py
```

`run_eval.py` prints a per-question table and a summary, and writes
`outputs/eval_report.json` containing every retrieved document id, every fact checked, and
every answer, so any number in the summary can be traced back to a specific question.

---

## Baseline results (32 questions, reproducible as-is)

```
retrieval hit@4         100.0%    (24 answerable questions)
retrieval recall        100.0%
key-fact coverage        68.1%
answer correct           50.0%    (12/24)
correct abstentions       0.0%    (0/8)
false abstentions           1
ACCESS-CONTROL LEAKS        7     <-- baseline has no ACL filter
overall pass rate        37.5%
latency p50 / p95        1 ms / 2 ms
```

The gold set has four question types: 15 single-hop, 8 multi-hop, 4 unanswerable (the fact is
not in the corpus at all), and 5 access-controlled (4 that must be refused, 1 that a HR user
is allowed to see).

**How to read this.** Retrieval is not the bottleneck yet — with 11 documents the right one is
almost always in the top 4. Everything downstream is. Answers are only half correct because the
generator picks locally-similar sentences rather than the sentence that answers the question;
the system never once abstained on a question it could not answer; and it leaked the confidential
compensation document on 7 of 32 questions, including to a contractor who asked for it directly.

I expect retrieval recall to fall as the corpus grows, which is why the harness measures it now
rather than later.

---

## The four documented test cases

| # | File | Role | What it demonstrates | Result |
|---|------|------|----------------------|--------|
| 1 | `examples/test1.txt` | employee | Single-hop lookup | **Works.** Correct fact, correct citation — but drifts into two unrelated sentences |
| 2 | `examples/test2.txt` | employee | Multi-hop across the runbook and the security policy | **Partial.** Retrieves both documents, answers only the paging half |
| 3 | `examples/test3.txt` | contractor | Access control | **Fails badly.** Prints the entire confidential salary table to a contractor |
| 4 | `examples/test4.txt` | employee | Question the corpus cannot answer | **Fails.** Answers with unrelated benefits text instead of saying "I don't know" |

Captured terminal transcripts for all four are in `outputs/test1.txt` … `outputs/test4.txt`,
with the structured results in `outputs/test1.json` … `outputs/test4.json`.

---

## Optional: dense embeddings and a real LLM

Neither is required, and neither changes the commands above.

**Dense embeddings** — replaces TF-IDF with `all-MiniLM-L6-v2` (~90 MB download on first run):

```bash
pip install -r requirements-optional.txt
python3 run_eval.py --embedder minilm
```

**LLM generation** — set exactly one key and the provider is picked up automatically:

```bash
export OPENAI_API_KEY=sk-...        # gpt-4o-mini
# or ANTHROPIC_API_KEY, or GOOGLE_API_KEY
python3 run_baseline.py --input examples/test2.txt
```

If a key is set but the call fails, the run degrades to the extractive path and says so in the
output rather than crashing. Force either path with `--provider extractive` or
`--provider openai`.

---

## Known limitations

These are properties of the baseline, not bugs to file:

- **No access control.** Retrieval sees every chunk regardless of who is asking. Measured as
  `acl_leaks` in the evaluation; 7 of 32 questions leak.
- **Abstention is one global threshold** on cosine similarity, which does not transfer across
  question types. It produced 0 correct abstentions and 1 false abstention.
- **The no-key extractive generator is not a language model.** It stitches together the
  highest-scoring sentences, so answers can be topically adjacent rather than responsive, and
  it sometimes emits a whole markdown table row.
- **Fact checking is exact substring matching.** It over-credits an answer that dumps a table
  containing the right string without actually answering, so `answer correct = 50%` should be
  read as an upper bound. An LLM-as-judge scorer is Phase 2 work.
- **The corpus is small (11 documents, 56 chunks).** Retrieval metrics are optimistic at this
  size and will move once the corpus grows.
- **`--embedder minilm` needs network access** on first use to fetch the model from Hugging
  Face. On a machine where that is blocked, `--embedder auto` falls back to TF-IDF and prints
  a warning; the default `tfidf` never touches the network.
- **English and markdown only.** No PDFs, images, tables-as-data, or multilingual content.

## Planned next phase

Multi-agent retrieval on LangGraph — a planner that decomposes multi-hop questions, per-domain
retrieval agents, an ACL filter applied before ranking, and a verifier agent that checks every
claim against its citation before the answer is returned. `docs/ARCHITECTURE.md` has the
current design sketch, and the same `run_eval.py` will score it against the numbers above.

## License

MIT — see `LICENSE`. The corpus is synthetic and written for this project.
