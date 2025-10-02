from typing import List, Dict, Optional
import hashlib

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

class QdrantRetriever:
    def __init__(self, url: str, collection: str, embedder):
        self.client = QdrantClient(url=url)
        self.collection = collection
        self.embed = embedder
        self._ensure_collection()

    def _ensure_collection(self):
        exists = self.client.collection_exists(self.collection)
        if exists:
            return
        dim = len(self.embed(["probe"])[0])
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


    def _make_id(self, text: str) -> int:
        return int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % (10**16)

    def upsert_doc(self, text: str, payload: Dict):
        vec = self.embed([text])[0]
        pid = self._make_id(text)
        data = {**payload, "text": text}

        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=pid, vector=vec, payload=data)],
        )

    def search(self, query: str, top_k: int = 5, variant: str = "A", lang: Optional[str] = None) -> List[Dict]:
        qvec = self.embed([query])[0]

        qfilter = None
        if lang:
            qfilter = Filter(must=[FieldCondition(key="lang", match=MatchValue(value=lang))])

        limit = top_k * 2 if variant == "B" else top_k

        hits = self.client.search(
            collection_name=self.collection,
            query_vector=qvec,
            limit=limit,
            query_filter=qfilter
        )

        out = []
        for h in hits:
            p = h.payload or {}
            out.append({
                "text": p.get("text", ""),
                "score": float(h.score),
                "url": p.get("url"),
                "lang": p.get("lang"),
                "section": p.get("section"),
            })

        if variant == "B":
            out = out[:top_k]

        return out
