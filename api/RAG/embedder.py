# api/rag/embedder.py
from sentence_transformers import SentenceTransformer

_model_cache = {}

def get_embedder(model_name: str):
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    model = _model_cache[model_name]
    def encode(texts):
        return model.encode(texts, normalize_embeddings=True).tolist()
    return encode
