from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from rag.generator import generate_answer
import time, uuid

app = FastAPI(title="RAG API")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
QDRANT_URL = "http://qdrant:6333" 
COLLECTION = "docs"

STATS = {"A": 0, "B": 0, "tie": 0, "total": 0}
QUERIES = {}

#since it takes long time to start I will try lazy-load
_embed = None
_retriever = None

def _ensure_services():
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
    latency_ms: int
    answer: str
    query_id: Optional[str] = None

class UpsertIn(BaseModel):
    text: str
    lang: Optional[str] = None
    url: Optional[str] = None
    section: Optional[str] = None

class FeedbackIn(BaseModel):
    query_id: str
    winner: str  

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
            # graceful degrade if llm fails
            answer = f"{' '.join(ctx_texts[:2]) if ctx_texts else '(no hits)'}"

    latency = int((time.time() - t0) * 1000)
    qid = str(uuid.uuid4())
    query_output = {"variant": x_variant, "contexts": ctx, "latency_ms": latency, "answer": answer, "query_id": qid}
    QUERIES[qid] = query_output
    return query_output

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

@app.post("/ingest-file")
async def ingest_file(
    request: Request,
    lang: Optional[str] = None,
    url: Optional[str] = None,
    section: Optional[str] = None,
    content_type: Optional[str] = Header(None),
    x_filename: Optional[str] = Header(None),
):
    _ensure_services()

    content: bytes = await request.body()
    if not content:
        return {"ok": False, "error": "empty-body"}

    def printable_ratio(s: str) -> float:
        if not s:
            return 0.0
        printable = sum(ch.isprintable() and ch not in "\x0b\x0c" for ch in s)
        return printable / max(1, len(s))

    text = ""
    filename = x_filename.lower()
    ctype = content_type.lower()
    is_pdf = "pdf" in ctype or filename.endswith(".pdf")

    try:
        if is_pdf:
            try:
                from pypdf import PdfReader
                import io, os
                max_pages = int(os.getenv("INGEST_MAX_PAGES", "50"))
                reader = PdfReader(io.BytesIO(content))
                pages = reader.pages[:max_pages]
                text = "\n".join((p.extract_text() or "") for p in pages)
            except Exception:
                text = ""

            if printable_ratio(text) < 0.6:
                try:
                    import fitz
                    import io, os
                    max_pages = int(os.getenv("INGEST_MAX_PAGES", "50"))
                    doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
                    parts = []
                    for i, page in enumerate(doc):
                        if i >= max_pages:
                            break
                        parts.append(page.get_text("text"))
                    doc.close()
                    alt = "\n".join(parts)
                    if printable_ratio(alt) >= printable_ratio(text):
                        text = alt
                except Exception:
                    pass
        else:
            text = content.decode("utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error": f"parse-failed: {e}"}

    text = text.strip()
    if printable_ratio(text) < 0.3:
        return {"ok": False, "error": "parsed-text-unreadable"}

    if not text:
        return {"ok": False, "error": "parsed-text-empty"}

    import re
    sentences = re.split(r'(?<=[\.\!\?])\s+', text)
    MAX = 480
    chunks, buf, L = [], [], 0
    for s in sentences:
        s = (s or "").strip()
        if not s:
            continue
        if L + len(s) + 1 <= MAX:
            buf.append(s); L += len(s) + 1
        else:
            if buf: chunks.append(" ".join(buf))
            buf = [s]; L = len(s)
    if buf: chunks.append(" ".join(buf))

    meta = {"lang": lang, "url": url or (f"upload:{x_filename}" if x_filename else None), "section": section}
    meta = {k: v for k, v in meta.items() if v is not None}

    n_upsert = 0
    for c in chunks:
        _retriever.upsert_doc(c, {**meta, "text": c})
        n_upsert += 1

    return {"ok": True, "chunks": n_upsert, "content_type": content_type, "filename": x_filename}

@app.post("/feedback")
def feedback(body: FeedbackIn):
    qid = body.query_id
    winner = body.winner
    if winner not in ("A","B","tie"):
        raise HTTPException(400, "winner must be 'A', 'B' or 'tie'")
    if qid not in QUERIES:
        raise HTTPException(400, "unknown query_id")
    global STATS
    STATS[winner] += 1
    STATS["total"] += 1
    return {"ok": True}

@app.get("/stats")
def stats():
    a, b, t, tot = STATS["A"], STATS["B"], STATS["tie"], STATS["total"]
    return {
        "counts": {"A": a, "B": b, "tie": t, "total": tot},
        "win_rate": {"A": a/tot, "B": b/tot, "tie": t/tot}
    }