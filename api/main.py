from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional

from numpy import dot
from numpy.linalg import norm

from rag.generator import generate_answer
import time, uuid
import json

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

def run_query_core(q: str, top_k: int, variant: str, lang: Optional[str]):
    _ensure_services()
    t0 = time.time()
    ctx = _retriever.search(query=q, top_k=top_k, variant=variant, lang=lang)
    ctx_texts = [c["text"] for c in ctx if c.get("text")]
    if variant == "A":
        answer = " ".join(ctx_texts[:2]) if ctx_texts else "(no hits)"
    else:
        try:
            answer = generate_answer(q, ctx_texts)
        except Exception:
            answer = " ".join(ctx_texts[:2]) if ctx_texts else "(no hits)"
    latency = int((time.time() - t0) * 1000)
    return {"contexts": ctx, "answer": answer, "latency_ms": latency}

@app.post("/query", response_model=QueryOut)
def query(body: QueryIn, x_variant: str = Header(default="A")):
    if x_variant not in ("A","B"):
        raise HTTPException(400, "X-Variant must be 'A' or 'B'")
    out = run_query_core(body.query, body.top_k, x_variant, body.lang)
    qid = str(uuid.uuid4())
    QUERIES[qid] = {"variant": x_variant, "question": body.query, **out}
    return {"variant": x_variant, "query_id": qid, **out}


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
    filename = (x_filename or "").lower()
    ctype    = (content_type or "").lower()
    is_pdf = "pdf" in ctype or filename.endswith(".pdf")

    try:
        if is_pdf:
            try:
                from pypdf import PdfReader
                import io
                max_pages = 50
                reader = PdfReader(io.BytesIO(content))
                pages = reader.pages[:max_pages]
                text = "\n".join((p.extract_text() or "") for p in pages)
            except Exception:
                text = ""

            if printable_ratio(text) < 0.6:
                try:
                    import fitz
                    import io
                    max_pages = 50
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

@app.get("/online-stats")
def online_stats():
    a, b, t, tot = STATS["A"], STATS["B"], STATS["tie"], STATS["total"]
    if tot == 0:
        return {
            "counts": {"A": 0, "B": 0, "tie": 0, "total": 0},
            "win_rate": {"A": 0, "B": 0, "tie": 0}
            }
    return {
        "counts": {"A": a, "B": b, "tie": t, "total": tot},
        "win_rate": {"A": a/tot, "B": b/tot, "tie": t/tot}
    }

@app.get("/get_queries")
def get_queries():
    return QUERIES

def cos(a, b):
    na, nb = float(norm(a)), float(norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot(a, b) / (na * nb))

@app.get("/offline_eval")
def offline_eval():
    file_path = "data/qd_test.json"
    with open(file_path, "r") as f:
        data =json.loads(f.read())
    
    out_list = list()
    for qa in data:
        outA = run_query_core(qa["q"], 5, "A", None)
        outB = run_query_core(qa["q"], 5, "B", None)
        vec_g = _embed.encode(qa["a"])
        score_A = cos(vec_g, _embed.encode(outA["answer"]))
        score_B = cos(vec_g, _embed.encode(outB["answer"]))
        if score_A > score_B:
            winner = "A"
        elif score_A < score_B:
            winner = "B"
        else:
            winner = "tie"
        out_list.append({"question":qa["q"], "answer_A":outA["answer"], "answer_B":outB["answer"], "winner":winner})
    
    with open('output.json', 'w', encoding='utf-8') as f:
        json.dump(out_list, f, ensure_ascii=False, indent=4)



