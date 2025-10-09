import json, sys, time
from urllib import request
from numpy import dot
from numpy.linalg import norm

import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# this file is for offline evaluation a file
def cos(a, b):
    na, nb = float(norm(a)), float(norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot(a, b) / (na * nb))


def http_post_json(url, body, headers=None, timeout=120):
    data = json.dumps(body).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = request.Request(url, data=data, headers=hdrs, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def load_embedder():
    sys.path.append("__path__")
    from rag.embedder import get_embedder
    model_name = "BAAI/bge-small-en-v1.5"
    return get_embedder(model_name)

def main():
    with open("data/qd_test.json", "r", encoding="utf-8") as f:
        data = json.loads(f.read())

    embed = load_embedder()

    out_list = []
    ok = 0
    t0 = time.time()

    for qa in data:
        q = qa["q"]
        gold = qa["a"]

        # A
        resA = http_post_json(f"http://localhost:8000/query", {"query": q, "top_k": 5}, headers={"X-Variant": "A"})
        ansA = resA.get("answer", "")
        vec_g = embed.encode(gold)
        vec_A = embed.encode(ansA)
        score_A = cos(vec_g, vec_A)

        # B
        resB = http_post_json(f"http://localhost:8000/query", {"query": q, "top_k": 5}, headers={"X-Variant": "B"})
        ansB = resB.get("answer", "")
        vec_B = embed.encode(ansB)
        score_B = cos(vec_g, vec_B)

        if score_A > score_B:
            winner = "A"
        elif score_B > score_A:
            winner = "B"
        else:
            winner = "tie"

        if winner == "B":
            ok += 1  # örnek bir "B kazandı sayacı" (istersen A için de say)

        out_list.append({
            "question": q,
            "gold": gold,
            "answer_A": ansA,
            "answer_B": ansB,
            "score_A": round(score_A, 4),
            "score_B": round(score_B, 4),
            "winner": winner
        })

    took = round(time.time() - t0, 2)
    summary = {
        "num_samples": len(data),
        "b_wins": ok,
        "duration_secs": took
    }

    with open("output_offline.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "items": out_list}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
