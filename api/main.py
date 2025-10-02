from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from rag.embedder import get_embedder
from rag.retriever_qdrant import QdrantRetriever

app = FastAPI(title="RAG API (basic)")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
QDRANT_URL = "http://qdrant:6333" 
COLLECTION = "docs"

encode = get_embedder(EMBED_MODEL)
retriever = QdrantRetriever(QDRANT_URL, COLLECTION, encode)

# ---- PYDANTIC MODELS ----
class QueryIn(BaseModel):
    query: str
    top_k: int = 5
    lang: Optional[str] = None   # "en" gibi

class ContextOut(BaseModel):
    text: str
    score: float
    url: Optional[str] = None
    lang: Optional[str] = None
    section: Optional[str] = None

class QueryOut(BaseModel):
    variant: str          # A veya B
    contexts: List[ContextOut]

# ---- ENDPOINT'LER ----
@app.get("/test")
def test():
    return {"ok": True}

@app.post("/query", response_model=QueryOut)
def query(body: QueryIn, x_variant: str = Header(default="A")):
    if x_variant not in ("A", "B"):
        raise HTTPException(status_code=400, detail="X-Variant must be 'A' or 'B'")

    results = retriever.search(
        query=body.query,
        top_k=body.top_k,
        variant=x_variant,
        lang=body.lang,
    )

    return {
        "variant": x_variant,
        "contexts": results
    }
