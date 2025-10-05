from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from rag.generator import generate_answer
import time

app = FastAPI(title="RAG API")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
QDRANT_URL = "http://qdrant:6333" 
COLLECTION = "docs"

#since it takes long time to start I will try lazy-load
_embed = None
_retriever = None

def _ensure_services():
    """İlk çağrıda embedder ve retriever'ı hazırlar."""
    global _embed, _retriever
    if _embed is None:
        from rag.embedder import get_embedder
        _embed = get_embedder(EMBED_MODEL)
    if _retriever is None:
        from rag.retriever import QdrantRetriever
        _retriever = QdrantRetriever(QDRANT_URL, COLLECTION, _embed)

# ---- PYDANTIC MODELS ----
class QueryIn(BaseModel):
    query: str
    top_k: int = 5
    lang: Optional[str] = None

class ContextOut(BaseModel):
    text: str
    score: float
    url: Optional[str] = None
    lang: Optional[str] = None
    section: Optional[str] = None

class QueryOut(BaseModel):
    variant: str
    contexts: List[ContextOut]

class UpsertIn(BaseModel):
    text: str
    lang: Optional[str] = None
    url: Optional[str] = None
    section: Optional[str] = None

# ---- ENDPOINTS ----
@app.get("/test")
def test():
    return {"ok": True}

@app.post("/query", response_model=QueryOut)
def query(body: QueryIn, x_variant: str = Header(default="A")):
    if x_variant not in ("A","B"):
        raise HTTPException(400, "X-Variant must be 'A' or 'B'")
    _ensure_services()

    t0 = time.time()
    ctx = _retriever.search(
        query=body.query, top_k=body.top_k, variant=x_variant, lang=body.lang
    )

    ctx_texts = [c["text"] for c in ctx if c.get("text")]

    if x_variant == "A":
        # variant A: just the context without LLM
        answer = " ".join(ctx_texts[:2]) if ctx_texts else "(no hits)"
    else:
        # variant B: with LLM answer generation
        try:
            answer = generate_answer(body.query, ctx_texts)
        except Exception as e:
            # graceful degrade to no llm
            answer = f"(llm error, fallback) {' '.join(ctx_texts[:2]) if ctx_texts else '(no hits)'}"

    latency = int((time.time() - t0) * 1000)
    return {"variant": x_variant, "contexts": ctx, "latency_ms": latency, "answer": answer}


@app.post("/upsert")
def upsert(body: UpsertIn):
    _ensure_services()
    payload = {
        "lang": body.lang,
        "url": body.url,
        "section": body.section,
        "text": body.text,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    retr = _retriever
    retr.upsert_doc(body.text, payload)
    return {"ok": True}
