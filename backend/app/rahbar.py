"""Rahbar — Urdu/English Q&A over a static corpus (Qdrant RAG).

Demo scope (LOCKED): static corpus, 10 pre-tested Urdu queries. No corpus
management, no live upload. Groq only verbalizes retrieved snippets.

Language toggle: retrieval always runs over the Urdu corpus (multilingual
embedder, no corpus translation needed). Only the answer's output language
changes per `lang` — the SYSTEM_PROMPT for the requested language instructs
Groq to answer in that language while still grounding in the Urdu context.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .config import settings

COLLECTION = "rahbar_corpus"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384
TOP_K = 3

SAMPLE_QUERIES = [
    "دن کے اختتام پر کیش کیسے ملایا جائے؟",
    "نوٹوں کی گنتی کیسے درج کروں؟",
    "کتنے فرق پر منیجر کو رپورٹ کرنا ضروری ہے؟",
    "کیش کم نکلے تو ذمہ داری کس کی ہے؟",
    "ڈبل پوسٹنگ ہو جائے تو کیا کروں؟",
    "ریورسل کی منظوری کون دیتا ہے؟",
    "جعلی نوٹ ملنے پر کیا کرنا چاہیے؟",
    "ٹیلر کے پاس زیادہ سے زیادہ کتنا کیش ہو سکتا ہے؟",
    "والٹ میں کیش منتقل کرنے کا طریقہ کیا ہے؟",
    "غلط اکاؤنٹ میں رقم چلی جائے تو کیا کریں؟",
]

# English display labels for the same 10 queries, same order. Retrieval always
# runs on the SAMPLE_QUERIES (Urdu) text above — that's what the oracle in
# test_rahbar.py verifies against the corpus. These are labels only.
SAMPLE_QUERIES_EN = [
    "How should cash be reconciled at end of day?",
    "How do I record the denomination count?",
    "At what variance level must I report to the manager?",
    "If cash is short, whose responsibility is it?",
    "What do I do if a transaction was posted twice?",
    "Who approves a reversal?",
    "What should be done if a counterfeit note is found?",
    "What is the maximum cash a teller can hold?",
    "What is the procedure to transfer cash to the vault?",
    "What do I do if money goes to the wrong account?",
]


class QueryPair(BaseModel):
    ur: str
    en: str


def sample_query_pairs() -> list[QueryPair]:
    return [
        QueryPair(ur=ur, en=en)
        for ur, en in zip(SAMPLE_QUERIES, SAMPLE_QUERIES_EN, strict=True)
    ]

SYSTEM_PROMPTS = {
    "ur": (
        "You are Rahbar (رہبر), the branch-operations assistant inside ZeroBalance "
        "for bank tellers in Pakistan. Answer the teller's question ONLY from the provided "
        "context snippets (a synthetic demo corpus of SBP-style circulars and branch SOPs). "
        "Reply in simple Urdu script, 2-4 short sentences, numbers in western digits. "
        "If the context does not contain the answer, say in Urdu that you do not have this "
        "information and to consult the Branch Operations Manager. Never invent policy "
        "numbers or amounts. End with: ماخذ: followed by the source title(s) you used."
    ),
    "en": (
        "You are Rahbar, the branch-operations assistant inside ZeroBalance for bank "
        "tellers in Pakistan. Answer the teller's question ONLY from the provided context "
        "snippets (a synthetic demo corpus of SBP-style circulars and branch SOPs, written "
        "in Urdu — translate the relevant facts, do not quote Urdu script back). "
        "Reply in plain English, 2-4 short sentences, numbers in western digits. "
        "If the context does not contain the answer, say you do not have this information "
        "and to consult the Branch Operations Manager. Never invent policy numbers or "
        "amounts. End with: Source: followed by the source title(s) you used."
    ),
}

Lang = str  # "ur" | "en"


class RahbarSource(BaseModel):
    title: str
    source: str
    score: float


class RahbarAnswer(BaseModel):
    answer: str
    lang: Lang
    sources: list[RahbarSource]


class ChatClient(Protocol):  # the sliver of groq.Groq we use
    chat: Any


@lru_cache(maxsize=1)
def load_corpus() -> list[dict[str, Any]]:
    raw = json.loads((Path(__file__).parent / "rahbar_corpus.json").read_text("utf-8"))
    return raw["documents"]


def _corpus_sha() -> str:
    texts = json.dumps([d["text_ur"] for d in load_corpus()], ensure_ascii=False)
    return hashlib.sha256(texts.encode()).hexdigest()


_embedder: Any = None


def _embed(texts: list[str]) -> list[list[float]]:
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(model_name=EMBED_MODEL)
    return [v.tolist() for v in _embedder.embed(texts)]


def _qdrant() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def ensure_indexed(qc: QdrantClient | None = None) -> None:
    qc = qc or _qdrant()
    docs = load_corpus()
    sha = _corpus_sha()
    if qc.collection_exists(COLLECTION) and qc.count(COLLECTION).count == len(docs):
        first = qc.retrieve(COLLECTION, ids=[docs[0]["id"]])
        if first and (first[0].payload or {}).get("corpus_sha") == sha:
            return
    if qc.collection_exists(COLLECTION):
        qc.delete_collection(COLLECTION)
    qc.create_collection(
        COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE)
    )
    vectors = _embed([d["text_ur"] for d in docs])
    qc.upsert(COLLECTION, points=[
        PointStruct(id=d["id"], vector=v,
                    payload={"title": d["title"], "text_ur": d["text_ur"],
                             "source": d["source"], "corpus_sha": sha})
        for d, v in zip(docs, vectors, strict=True)
    ])


def retrieve(question: str, k: int = TOP_K) -> list[dict[str, Any]]:
    qc = _qdrant()
    ensure_indexed(qc)
    hits = qc.query_points(COLLECTION, query=_embed([question])[0], limit=k).points
    return [
        {"id": h.id, "score": float(h.score), **(h.payload or {})}
        for h in hits
    ]


def _client_factory() -> ChatClient:
    from groq import Groq

    return Groq(api_key=settings.groq_api_key)


def ask(question: str, lang: Lang = "ur", client: ChatClient | None = None) -> RahbarAnswer:
    if lang not in SYSTEM_PROMPTS:
        raise ValueError(f"unsupported lang: {lang!r} (expected 'ur' or 'en')")
    hits = retrieve(question)
    client = client or _client_factory()
    context = "\n\n".join(
        f"[{h['title']}] ({h['source']})\n{h['text_ur']}" for h in hits
    )
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPTS[lang]},
            {"role": "user", "content": f"Context:\n{context}\n\nTeller question:\n{question}"},
        ],
        temperature=0.3,
        max_tokens=400,
    )
    answer = (resp.choices[0].message.content or "").strip()
    return RahbarAnswer(
        answer=answer,
        lang=lang,
        sources=[RahbarSource(title=h["title"], source=h["source"], score=h["score"])
                 for h in hits],
    )
