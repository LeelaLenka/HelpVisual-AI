"""Knowledge base: an account's approved support documents, searched with BM25.

BM25 is keyword ranking: it scores a passage by how many of the question's words it contains,
weighting rare words more and long passages less. It needs no model and no GPU, which suits a
laptop-and-Kaggle setup; its limit is that it matches words, not meanings ("sign in" does not find
"log in"). Documents are split into overlapping passages of about 120 words so an answer can
quote the relevant part rather than a whole document.
"""
from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CHUNK_WORDS, OVERLAP_WORDS = 120, 30
K1, B = 1.5, 0.75  # standard BM25 parameters
STOPWORDS = {
    "a", "an", "the", "to", "of", "on", "in", "at", "for", "and", "or", "your", "you", "it", "is", "are",
    "be", "with", "from", "this", "that", "by", "as", "will", "can", "i", "my", "me", "do", "how", "what",
    "if", "then", "not", "no", "yes", "we", "our", "they", "their", "there", "here",
}


class Document(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    words: int = 0
    chunks: list[str] = []


class Passage(BaseModel):
    document_id: str
    title: str
    text: str
    score: float


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def chunk(text: str) -> list[str]:
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        return [" ".join(words)] if words else []
    step = CHUNK_WORDS - OVERLAP_WORDS
    return [" ".join(words[i:i + CHUNK_WORDS]) for i in range(0, max(1, len(words) - OVERLAP_WORDS), step)]


class KnowledgeBase:
    """One JSON file per account under data/kb/."""

    def __init__(self, data_dir: Path):
        self.folder = Path(data_dir) / "kb"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, owner_id: str) -> Path:
        if not owner_id.isalnum():
            raise ValueError("bad owner id")
        return self.folder / f"{owner_id}.json"

    def documents(self, owner_id: str) -> list[Document]:
        path = self._path(owner_id)
        with self._lock:
            if not path.exists():
                return []
            return [Document(**d) for d in json.loads(path.read_text(encoding="utf-8"))]

    def _write(self, owner_id: str, docs: list[Document]) -> None:
        path = self._path(owner_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps([d.model_dump() for d in docs], indent=1), encoding="utf-8")
        tmp.replace(path)

    def add(self, owner_id: str, title: str, text: str) -> Document:
        doc = Document(title=title.strip()[:120] or "Untitled", words=len(text.split()), chunks=chunk(text))
        with self._lock:
            path = self._path(owner_id)
            docs = [Document(**d) for d in json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []
            docs.insert(0, doc)
            self._write(owner_id, docs)
        return doc

    def delete(self, owner_id: str, document_id: str) -> bool:
        with self._lock:
            path = self._path(owner_id)
            if not path.exists():
                return False
            docs = [Document(**d) for d in json.loads(path.read_text(encoding="utf-8"))]
            kept = [d for d in docs if d.id != document_id]
            self._write(owner_id, kept)
            return len(kept) != len(docs)

    def search(self, owner_id: str, query: str, limit: int = 5) -> list[Passage]:
        passages = [(d, c) for d in self.documents(owner_id) for c in d.chunks]
        terms = set(tokens(query))
        if not passages or not terms:
            return []
        docs_tokens = [Counter(tokens(c)) for _, c in passages]
        n = len(passages)
        avg_len = sum(sum(t.values()) for t in docs_tokens) / n or 1
        frequency = Counter(term for t in docs_tokens for term in set(t) if term in terms)
        results = []
        for (doc, text), counts in zip(passages, docs_tokens):
            length = sum(counts.values()) or 1
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf:
                    idf = math.log(1 + (n - frequency[term] + 0.5) / (frequency[term] + 0.5))
                    score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / avg_len))
            if score > 0:
                results.append(Passage(document_id=doc.id, title=doc.title, text=text, score=round(score, 3)))
        return sorted(results, key=lambda p: p.score, reverse=True)[:limit]
