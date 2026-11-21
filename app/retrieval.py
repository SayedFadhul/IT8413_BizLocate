"""F5 - Retrieval: embedding the passages and finding the ones closest to a question (lead: Mohamed Alradhi).

Method (Labs 3.1 and 3.3):
  - Each passage is embedded once as "title: <document, articles, pages> | text: <passage>".
  - A question is embedded as "task: search result | query: <question>".
  - Passages are ranked by cosine similarity (dot product ÷ the two magnitudes) and the
    top k are given to the model with their ids.
The index (vectors + passage text) is saved in documents/index/, which Git ignores, because
it contains the documents' text. scripts/build_index.py builds it once (a few batched requests).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import INDEX_DIR, Settings
from app.documents import Chunk, build_chunks


def passage_input(chunk: Chunk) -> str:
    """Formats a passage for embedding, using its document, articles and pages as the title."""
    return f"title: {chunk.title()} | text: {chunk.text}"


def question_input(question: str) -> str:
    """Formats a question for embedding, starting with its task prefix."""
    return f"task: search result | query: {question}"


def index_path(settings: Settings) -> Path:
    return INDEX_DIR / f"index_{settings.embedding_model}_{settings.chunk_words}w.json"


@dataclass
class Index:
    chunks: list[Chunk]
    vectors: np.ndarray            # one row per passage
    info: dict

    def by_id(self, cid: str) -> Chunk | None:
        i = int(cid[1:]) - 1 if cid[1:].isdigit() else -1
        return self.chunks[i] if 0 <= i < len(self.chunks) and self.chunks[i].id == cid else None

    def search(self, question_vector: list[float], k: int) -> list[tuple[float, Chunk]]:
        """The k passages with the highest cosine similarity to the question, best first."""
        q = np.asarray(question_vector, dtype=float)
        # cosine similarity = dot product / (magnitude of a × magnitude of b), for every passage at once
        scores = self.vectors @ q / (np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(q))
        top = np.argsort(-scores)[:k]
        return [(round(float(scores[i]), 3), self.chunks[i]) for i in top]


def build_index(gemini, settings: Settings, batch_size: int = 20, progress=print) -> Path:
    """Embed every passage (in batches, one request per batch) and save the index."""
    chunks = build_chunks(settings.chunk_words)
    vectors: list[list[float]] = []
    start = time.time()
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        vectors += gemini.embed([passage_input(c) for c in batch])
        progress(f"{min(i + batch_size, len(chunks))} of {len(chunks)} passages embedded")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    path = index_path(settings)
    data = {"info": {"embedding_model": settings.embedding_model, "chunk_words": settings.chunk_words,
                     "passages": len(chunks), "dimensions": len(vectors[0]) if vectors else 0,
                     "built": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - start)},
            "chunks": [c.as_dict() for c in chunks], "vectors": vectors}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


COMMON = set("a an the is are was be to of and or in on for my i do does how what with after at by from can it "
             "this that not will many much each there which who where when shall any its their as".split())


def keyword_words(text: str) -> set[str]:
    """The words of a text without common words, for keyword search (Lab 3.1, Part 5)."""
    import re
    return {w.rstrip("s") if len(w) > 4 else w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in COMMON}


def keyword_search(chunks: list[Chunk], query: str, k: int = 3) -> list[tuple[float, Chunk]]:
    """Passages that share the most (rare) words with the query, weighted as in Lab 3.1, Part 6.
    Used where no model call is wanted, e.g. the passages printed in the report."""
    import math
    words = [keyword_words(c.text + " " + " ".join(c.sections)) for c in chunks]
    doc_count: dict[str, int] = {}
    for ws in words:
        for w in ws:
            doc_count[w] = doc_count.get(w, 0) + 1
    q = keyword_words(query)
    n = len(chunks)
    scored = []
    for c, ws in zip(chunks, words):
        shared = q & ws
        if shared:
            scored.append((round(sum(math.log(n / doc_count[w]) for w in shared), 2), c))
    scored.sort(key=lambda t: -t[0])
    return scored[:k]


def load_index(settings: Settings) -> Index | None:
    """The saved index for these settings, or None if it has not been built yet."""
    path = index_path(settings)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks = [Chunk(**c) for c in data["chunks"]]
    return Index(chunks=chunks, vectors=np.asarray(data["vectors"], dtype=float), info=data["info"])
