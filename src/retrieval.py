"""Knowledge base: split manuals, SOPs and work orders into chunks, then search them.

Three search methods, compared in the evaluation:
- BM25 (keyword search, the classic search-engine formula). Strong for exact codes like A-217.
  "bm25_raw" uses the question as typed; "bm25" first adds plant-glossary words.
- Dense (embeddings from a local Ollama model). Strong for meaning ("machine shakes" ~ "vibration").
- Hybrid: both rankings fused with Reciprocal Rank Fusion (RRF).
"""
from __future__ import annotations

import hashlib
import time
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import requests

from src import config


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    source_type: str          # manual / sop / work_order
    title: str
    section: str
    text: str
    machines: list[str] = field(default_factory=list)   # ["all"] for plant-wide documents
    date: str | None = None

    def citation(self) -> str:
        if self.source_type == "work_order":
            return f"{self.doc_id} ({self.machines[0]}, {self.date})"
        return f"{self.doc_id}: {self.section}"


# --------------------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------------------
def _frontmatter(md: str) -> tuple[dict, str]:
    meta = {}
    if md.startswith("---"):
        head, body = md[3:].split("\n---", 1)
        for line in head.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
        return meta, body
    return meta, md


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def chunk_markdown(md: str, source_type: str) -> list[Chunk]:
    """One chunk per '## ' section. The document title is added to each chunk so that a
    chunk still makes sense on its own (e.g. which machine an alarm belongs to)."""
    meta, body = _frontmatter(md)
    machines = [m.strip() for m in meta.get("machines", "all").split(",")]
    chunks = []
    for part in re.split(r"\n(?=## )", body):
        lines = part.strip().splitlines()
        if not lines or not lines[0].startswith("## "):
            continue
        section = lines[0][3:].strip()
        text = "\n".join(lines[1:]).strip()
        chunks.append(Chunk(
            chunk_id=f"{meta['doc_id']}#{_slug(section)}", doc_id=meta["doc_id"],
            source_type=source_type, title=meta.get("title", meta["doc_id"]), section=section,
            text=text, machines=machines))
    return chunks


def chunk_work_orders(wo: pd.DataFrame) -> list[Chunk]:
    chunks = []
    for r in wo.itertuples():
        day = pd.Timestamp(r.created_ts).strftime("%Y-%m-%d")
        parts = f" Parts: {r.parts_used}." if r.parts_used else ""
        text = (f"{r.type} work order on {r.machine_id}, {day}, priority {r.priority}. "
                f"Symptom: {r.symptom} Cause: {r.cause} Action: {r.action}{parts} "
                f"Downtime: {r.downtime_min} min. Technician {r.technician}.")
        chunks.append(Chunk(chunk_id=f"WO:{r.wo_id}", doc_id=r.wo_id, source_type="work_order",
                            title=f"Work order {r.wo_id}", section=r.type, text=text,
                            machines=[r.machine_id], date=day))
    return chunks


def build_chunks(work_orders: pd.DataFrame | None = None) -> list[Chunk]:
    chunks = []
    for sub, kind in (("manuals", "manual"), ("sops", "sop")):
        for p in sorted((config.KNOWLEDGE_DIR / sub).glob("*.md")):
            chunks += chunk_markdown(p.read_text(encoding="utf-8"), kind)
    if work_orders is not None:
        chunks += chunk_work_orders(work_orders)
    return chunks


# --------------------------------------------------------------------------------------
# BM25
# --------------------------------------------------------------------------------------
STOPWORDS = set("""a an and are as at be by do does for from has have how i in is it its of on or
that the this to was were what when where which who why will with you your my we our me can
should could would there their them they after before about into than then so if not no""".split())
CODE = re.compile(r"\b[a-z]{1,5}-\d{2,6}(?:-\d+)?\b")


def _stem(w: str) -> str:
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(w) > len(suf) + 3 and w.endswith(suf) and not w.endswith("ss"):
            return w[: -len(suf)] + rep
    return w


def tokenize(text: str) -> list[str]:
    text = text.lower()
    codes = CODE.findall(text)                     # keep "a-217" as one token ...
    words = re.findall(r"[a-z0-9]+", text)         # ... and also its parts
    return codes + [_stem(w) for w in words if w not in STOPWORDS]


# Plant glossary: words people use -> words the manuals use. Small, curated, versioned.
# This is cheap and transparent; dense embeddings learn such links automatically.
GLOSSARY = {
    "overheat": "temperature high hot", "hot": "temperature", "heat": "temperature",
    "shake": "vibration", "shak": "vibration", "vibrat": "vibration", "noisy": "noise vibration",
    "rattl": "vibration noise", "stuck": "jam", "jammed": "jam", "block": "jam",
    "leak": "leak hose seal", "oil": "hydraulic oil", "curtain": "light curtain s-310",
    "sensor": "sensor fault", "screw": "screwdriver torque", "torque": "screwdriver torque",
    "changeover": "setup die change", "setup": "changeover die change", "die": "die change",
    "slow": "speed performance", "scrap": "scrap reject quality", "reject": "scrap quality",
    "lockout": "loto lockout tagout", "loto": "lockout tagout", "lathe": "turning tl-400",
    "bearing": "spindle bearing", "coolant": "coolant a-101", "feeder": "coil feeder h-220",
    "bypass": "bypass bridge safety", "emergency": "emergency stop",
    "reach": "lockout tagout", "trip": "fault stop", "humm": "noise vibration",
}


def expand_query(query: str) -> str:
    q = query.lower()
    extra = [v for k, v in GLOSSARY.items() if re.search(rf"\b{re.escape(k)}", q)]
    return query + " " + " ".join(extra)


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=float)
        self.avg = self.len.mean() if len(docs) else 0
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        s = np.zeros(len(self.tf))
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            f = np.array([tf.get(t, 0) for tf in self.tf], dtype=float)
            s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len / self.avg))
        return s


# --------------------------------------------------------------------------------------
# Dense embeddings via Ollama (runs locally, no data leaves the plant)
# --------------------------------------------------------------------------------------
def ollama_models(timeout: float = 2.0) -> list[str] | None:
    """Installed Ollama models, or None if Ollama is not running."""
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=timeout)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError):
        return None


def model_available(name: str, models: list[str] | None) -> bool:
    if not models:
        return False
    if name in models or f"{name}:latest" in models:
        return True
    return ":" not in name and any(m.split(":")[0] == name for m in models)


class OllamaEmbedder:
    def __init__(self, model: str = config.EMBED_MODEL):
        self.model = model

    def embed(self, texts: list[str], retries: int = 2) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 16):
            for attempt in range(retries + 1):
                try:
                    r = requests.post(f"{config.OLLAMA_URL}/api/embed", timeout=120, json={
                        "model": self.model, "input": texts[i:i + 16], "truncate": True,
                        "keep_alive": "10m"})
                    r.raise_for_status()
                    out += r.json()["embeddings"]
                    break
                except requests.RequestException:
                    if attempt == retries:
                        raise
                    time.sleep(2 * (attempt + 1))   # Ollama busy (e.g. swapping models): wait, retry
        v = np.array(out, dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True).clip(1e-9)


# --------------------------------------------------------------------------------------
# Retriever
# --------------------------------------------------------------------------------------
class Retriever:
    def __init__(self, chunks: list[Chunk], embedder: OllamaEmbedder | None = None):
        self.chunks = chunks
        self.bm25 = BM25([tokenize(f"{c.title} {c.section} {c.text}") for c in chunks])
        self.embedder = embedder
        self.dense_failures = 0       # queries that fell back to BM25 because Ollama failed
        self.vectors = None
        if embedder:
            try:
                self.vectors = self._load_or_embed()
            except (requests.RequestException, KeyError, ValueError) as e:
                print(f"WARNING: embeddings unavailable ({type(e).__name__}: {e}). Using BM25 only.")

    @property
    def has_dense(self) -> bool:
        return self.vectors is not None

    def _doc_text(self, c: Chunk) -> str:
        return f"search_document: {c.title}. {c.section}. {c.text}"

    def _load_or_embed(self) -> np.ndarray:
        texts = [self._doc_text(c) for c in self.chunks]
        key = hashlib.sha1(json.dumps([self.embedder.model, texts]).encode()).hexdigest()[:12]
        path = config.MODELS_DIR / f"embeddings_{key}.npy"
        if path.exists():
            return np.load(path)
        v = self.embedder.embed(texts)
        config.MODELS_DIR.mkdir(exist_ok=True)
        np.save(path, v)
        return v

    def _mask(self, machine: str | None, types: set[str] | None = None) -> np.ndarray:
        m = np.ones(len(self.chunks), dtype=bool)
        if machine:
            m &= np.array([("all" in c.machines) or (machine in c.machines) for c in self.chunks])
        if types:
            m &= np.array([c.source_type in types for c in self.chunks])
        return m

    def _rank(self, scores: np.ndarray, mask: np.ndarray) -> np.ndarray:
        scores = np.where(mask, scores, -np.inf)
        return np.argsort(-scores, kind="stable")[: int(mask.sum())]

    def search(self, query: str, k: int = config.TOP_K, method: str = "hybrid",
               machine: str | None = None, types: set[str] | None = None) -> list[tuple[Chunk, float]]:
        """Return the k best chunks with their score. machine= restricts to documents that
        belong to that machine (plus plant-wide documents); types= to source types."""
        mask = self._mask(machine, types)
        if method == "bm25_raw":
            bm = self.bm25.scores(tokenize(query))
            order = self._rank(bm, mask)[:k]
            return [(self.chunks[i], float(bm[i])) for i in order]
        bm = self.bm25.scores(tokenize(expand_query(query)))
        if method == "bm25" or (method == "hybrid" and not self.has_dense):
            order = self._rank(bm, mask)[:k]
            return [(self.chunks[i], float(bm[i])) for i in order]
        try:
            q = self.embedder.embed([f"search_query: {query}"])[0]
        except (requests.RequestException, KeyError, ValueError):
            # Never crash because the embedding server hiccups: fall back to keyword search.
            self.dense_failures += 1
            order = self._rank(bm, mask)[:k]
            return [(self.chunks[i], float(bm[i])) for i in order]
        dense = self.vectors @ q
        if method == "dense":
            order = self._rank(dense, mask)[:k]
            return [(self.chunks[i], float(dense[i])) for i in order]
        # hybrid: Reciprocal Rank Fusion
        fused = np.zeros(len(self.chunks))
        for scores in (bm, dense):
            for rank, i in enumerate(self._rank(scores, mask)):
                fused[i] += 1.0 / (60 + rank + 1)
        order = self._rank(fused, mask)[:k]
        return [(self.chunks[i], float(bm[i])) for i in order]  # keep BM25 score for confidence


def best_bm25(retriever: Retriever, query: str, machine: str | None = None,
              types: set[str] | None = None) -> float:
    s = retriever.bm25.scores(tokenize(expand_query(query)))
    m = retriever._mask(machine, types)
    return float(s[m].max()) if m.any() else 0.0
