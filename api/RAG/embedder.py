from typing import Optional
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"

def _load_model(model_name: str) -> SentenceTransformer:
        model = SentenceTransformer(model_name, device="cpu")
        return model

def get_embedder(model_name: Optional[str] = None):
    name = DEFAULT_MODEL
    if model_name:
        name = model_name
    model = _load_model(name)

    def encode(texts):
        arr = list(texts) if texts is not None else []
        if not arr:
            return []
        embs = model.encode(
            arr,
            normalize_embeddings=True,  # cosine için
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [list(v) for v in embs]
    return encode

def get_dimension(model_name: Optional[str] = None):
    """Probe ile embedding boyutunu döndür (koleksiyon kurarken işine yarar)."""
    enc = get_embedder(model_name)
    vecs = enc(["test"])
    return len(vecs[0]) if vecs and vecs[0] is not None else 0
