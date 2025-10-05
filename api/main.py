from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional

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

# ---- ENDPOINTS ----
@app.get("/test")
def test():
    return {"ok": True}

@app.post("/query", response_model=QueryOut)
def query(body: QueryIn, x_variant: str = Header(default="A")):
    if x_variant not in ("A", "B"):
        raise HTTPException(status_code=400, detail="X-Variant must be 'A' or 'B'")
    _ensure_services()
    results = _retriever.search(
        query=body.query,
        top_k=body.top_k,
        variant=x_variant,
        lang=body.lang,
    )

    return {
        "variant": x_variant,
        "contexts": results
    }
