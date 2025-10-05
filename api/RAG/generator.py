from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

_LLM_MODEL = "google/flan-t5-small"
_tokenizer = None
_model = None

# Lazy load the model and tokenizer
def _ensure_loaded():
    global _tokenizer, _model
    if _tokenizer is None or _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(_LLM_MODEL)
        _model = AutoModelForSeq2SeqLM.from_pretrained(_LLM_MODEL)

def build_prompt(question: str, contexts: list[str]) -> str:
    # since working on cpu we limit to 3 contexts with max 500 chars each
    ctx = "\n\n".join(f"- {c[:500]}" for c in contexts[:3])
    return (
        "Answer the question using ONLY the context. If unknown, say 'I don't know'.\n\n"
        f"Context:\n{ctx}\n\n"
        f"Question: {question}\nAnswer:"
    )

def generate_answer(question: str, contexts: list[str], max_new_tokens: int = 128) -> str:
    _ensure_loaded()
    prompt = build_prompt(question, contexts)
    inputs = _tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
    outputs = _model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        num_beams=1
    )
    return _tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
