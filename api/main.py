from fastapi import FastAPI

app = FastAPI(title="RAG API (skeleton)")

@app.get("/test")
def test():
    return {"ok": True}