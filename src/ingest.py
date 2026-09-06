"""Stage 1 - Data ingestion.

Reads every markdown file in the corpus directory and splits it into
(metadata, body). Metadata comes from a YAML front-matter block delimited by
'---' lines, which is how the corpus records department, sensitivity and owner.

Keeping ingestion this dumb is deliberate: the baseline should have no hidden
cleverness that later phases get credit for.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

REQUIRED_FIELDS = ("doc_id", "title", "department", "sensitivity")


@dataclass
class Document:
    path: pathlib.Path
    doc_id: str
    title: str
    department: str
    sensitivity: str
    body: str
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def source_name(self) -> str:
        return self.path.name


def _split_front_matter(raw: str) -> tuple[Dict[str, Any], str]:
    """Return (front_matter_dict, body). Tolerates files with no front matter."""
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, parts[2].lstrip("\n")


def load_corpus(corpus_dir: str | pathlib.Path) -> List[Document]:
    """Load every .md file under corpus_dir, sorted for deterministic ordering."""
    corpus_dir = pathlib.Path(corpus_dir)
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    docs: List[Document] = []
    for path in sorted(corpus_dir.glob("*.md")):
        meta, body = _split_front_matter(path.read_text(encoding="utf-8"))
        missing = [f for f in REQUIRED_FIELDS if f not in meta]
        if missing:
            raise ValueError(
                f"{path.name} is missing required front-matter field(s): {missing}"
            )
        docs.append(
            Document(
                path=path,
                doc_id=str(meta["doc_id"]),
                title=str(meta["title"]),
                department=str(meta["department"]),
                sensitivity=str(meta["sensitivity"]).lower(),
                body=body,
                meta=meta,
            )
        )

    if not docs:
        raise ValueError(f"No markdown documents found in {corpus_dir}")
    return docs
