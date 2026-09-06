"""Stage 6 - Generation, with citations and an explicit abstain path.

Four providers:

* ``openai``     - gpt-4o-mini via OPENAI_API_KEY
* ``anthropic``  - claude via ANTHROPIC_API_KEY
* ``gemini``     - gemini-2.0-flash via GOOGLE_API_KEY
* ``extractive`` - no API key, no network. Ranks sentences inside the retrieved
                   chunks against the query and stitches the best ones together
                   with citation markers.

``auto`` picks the first provider whose key is present in the environment and
falls back to ``extractive``. That fallback is the reason this baseline is
reproducible by a grader who has no keys at all.

HTTP is done with urllib from the standard library on purpose, so the only
third-party dependencies in the whole project are numpy, PyYAML and
scikit-learn.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from typing import Dict, List, Tuple

ABSTAIN_TOKEN = "INSUFFICIENT_CONTEXT"
REQUEST_TIMEOUT = 60

SYSTEM_PROMPT = """You are an internal knowledge-base assistant for Northwind Robotics.
Answer ONLY from the numbered context passages you are given.

Rules:
1. Every factual sentence must end with at least one citation marker like [C1] or [C2][C3].
2. Never state a fact that is not in the context, even if you believe it is true.
3. If the context does not contain the answer, reply with exactly INSUFFICIENT_CONTEXT and nothing else.
4. Be direct. 120 words maximum. No preamble.
"""

USER_TEMPLATE = """Context passages:
{context}

Question: {question}

Answer:"""

_STOPWORDS = {
    "a", "about", "am", "an", "and", "any", "are", "as", "at", "be", "but", "by",
    "can", "do", "does", "for", "from", "get", "give", "has", "have", "how", "i",
    "if", "in", "is", "it", "long", "many", "me", "much", "my", "need", "of", "on",
    "or", "our", "should", "so", "that", "the", "their", "them", "there", "they",
    "this", "to", "we", "what", "when", "where", "which", "who", "will", "with",
    "you", "your",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS]


def build_context(hits: List[dict]) -> str:
    """Render retrieved chunks as numbered passages the model can cite."""
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(f"[C{i}] ({hit['title']} - {hit['heading']})\n{hit['raw_text']}")
    return "\n\n".join(blocks)


def detect_provider(requested: str = "auto") -> str:
    requested = (requested or "auto").lower()
    if requested != "auto":
        return requested
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return "extractive"


def _post_json(url: str, payload: dict, headers: Dict[str, str]) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------- #
# extractive (no key) generator
# --------------------------------------------------------------------------- #

def _redundant(candidate_tokens: set, previous: str, threshold: float = 0.7) -> bool:
    """True if `candidate_tokens` mostly restates an already-selected sentence."""
    prev_tokens = set(re.findall(r"[a-z0-9]+", previous.lower()))
    if not candidate_tokens or not prev_tokens:
        return False
    shared = len(candidate_tokens & prev_tokens)
    return shared / min(len(candidate_tokens), len(prev_tokens)) >= threshold


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text.replace("|", " | ")).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in parts if len(p.strip()) > 25]


def extractive_answer(question: str, hits: List[dict], max_sentences: int = 3
                      ) -> Tuple[str, List[int]]:
    """Pick the sentences inside the retrieved chunks that best match the query.

    Scoring is IDF-weighted token overlap, with a small bonus for sentences that
    contain a number when the question asks 'how many / how much / how long'.
    """
    q_tokens = set(_tokens(question))
    if not q_tokens:
        return ABSTAIN_TOKEN, []

    sentences: List[Tuple[str, int]] = []
    for idx, hit in enumerate(hits):
        for sent in _split_sentences(hit["raw_text"]):
            sentences.append((sent, idx))
    if not sentences:
        return ABSTAIN_TOKEN, []

    df = Counter()
    for sent, _ in sentences:
        for tok in set(_tokens(sent)):
            df[tok] += 1
    n_docs = len(sentences)
    idf = {tok: math.log((n_docs + 1) / (df[tok] + 1)) + 1.0 for tok in df}

    wants_number = bool(re.search(r"how (many|much|long)|what (is|are) the (limit|deadline|threshold)",
                                  question.lower()))

    scored = []
    for sent, hit_idx in sentences:
        s_tokens = set(_tokens(sent))
        overlap = q_tokens & s_tokens
        if not overlap:
            continue
        score = sum(idf.get(tok, 1.0) for tok in overlap) / math.sqrt(len(s_tokens) + 1)
        if wants_number and re.search(r"\d", sent):
            score *= 1.15
        scored.append((score, sent, hit_idx))

    if not scored:
        return ABSTAIN_TOKEN, []

    scored.sort(key=lambda x: -x[0])
    chosen: List[Tuple[str, int]] = []
    for _score, sent, hit_idx in scored:
        # Overlapping chunk windows repeat text, so drop a candidate that mostly
        # restates something already picked (70% token overlap or containment).
        cand = set(re.findall(r"[a-z0-9]+", sent.lower()))
        if any(_redundant(cand, prev) for prev, _ in chosen):
            continue
        chosen.append((sent, hit_idx))
        if len(chosen) >= max_sentences:
            break

    used = sorted({hit_idx for _s, hit_idx in chosen})
    answer = " ".join(f"{sent} [C{hit_idx + 1}]" for sent, hit_idx in chosen)
    return answer, used


# --------------------------------------------------------------------------- #
# hosted providers
# --------------------------------------------------------------------------- #

def _openai(question: str, context: str, model: str) -> str:
    data = _post_json(
        "https://api.openai.com/v1/chat/completions",
        {
            "model": model or "gpt-4o-mini",
            "temperature": 0,
            "max_tokens": 400,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(
                    context=context, question=question)},
            ],
        },
        {
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    return data["choices"][0]["message"]["content"].strip()


def _anthropic(question: str, context: str, model: str) -> str:
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": model or "claude-3-5-haiku-latest",
            "max_tokens": 400,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": USER_TEMPLATE.format(
                    context=context, question=question)}
            ],
        },
        {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    return data["content"][0]["text"].strip()


def _gemini(question: str, context: str, model: str) -> str:
    model = model or "gemini-2.0-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={os.environ['GOOGLE_API_KEY']}"
    )
    data = _post_json(
        url,
        {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": USER_TEMPLATE.format(
                context=context, question=question)}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 400},
        },
        {"Content-Type": "application/json"},
    )
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def generate(question: str, hits: List[dict], provider: str = "auto",
             model: str = "") -> Dict[str, object]:
    """Return {'text', 'provider', 'cited_indices', 'error'}."""
    provider = detect_provider(provider)
    context = build_context(hits)

    if provider == "extractive":
        text, used = extractive_answer(question, hits)
        return {"text": text, "provider": "extractive", "cited_indices": used,
                "error": None}

    fn = {"openai": _openai, "anthropic": _anthropic, "gemini": _gemini}.get(provider)
    if fn is None:
        raise ValueError(f"Unknown provider: {provider}")

    try:
        text = fn(question, context, model)
        error = None
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError) as exc:
        # A dead key or no network must not break the run; degrade to extractive.
        text, used = extractive_answer(question, hits)
        return {
            "text": text,
            "provider": "extractive",
            "cited_indices": used,
            "error": f"{provider} call failed ({type(exc).__name__}); used extractive fallback",
        }

    cited = sorted({int(m) - 1 for m in re.findall(r"\[C(\d+)\]", text)
                    if 0 < int(m) <= len(hits)})
    return {"text": text, "provider": provider, "cited_indices": cited, "error": error}
