import json, time, pathlib
from urllib import request

# This script generates a daily report combining offline evaluation results and online stats from the API.
OUT_DIR = pathlib.Path("reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_MD = OUT_DIR / f"report-{time.strftime('%Y-%m-%d')}.md"

def http_get_json(url, timeout=20):
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    offline = {"summary": {}, "items": []}
    if pathlib.Path("output_offline.json").exists():
        offline = json.loads(pathlib.Path("output_offline.json").read_text(encoding="utf-8"))

    try:
        online = http_get_json(f"http://localhost:8000/stats")
    except Exception:
        online = {"counts": {"A":0,"B":0,"tie":0,"total":0}, "win_rate": {"A":0,"B":0,"tie":0}}

    s = offline.get("summary", {})
    num = s.get("num_samples", 0)
    b_wins = s.get("b_wins", 0)
    dur = s.get("duration_secs", "-")

    c = online.get("counts", {})
    w = online.get("win_rate", {})

    md = []
    md.append(f"# Daily RAG Report — {time.strftime('%Y-%m-%d')}\n")
    md.append("## Offline (Cosine Similarity)\n")
    md.append(f"- Samples: **{num}**")
    md.append(f"- B wins (offline): **{b_wins}**")
    md.append(f"- Duration: **{dur}s**\n")
    md.append("## Online Win-Rate\n")
    md.append(f"- Counts → A: **{c.get('A',0)}**, B: **{c.get('B',0)}**, tie: **{c.get('tie',0)}**, total: **{c.get('total',0)}**")
    md.append(f"- Win Rate → A: **{round(w.get('A',0)*100,1)}%**, B: **{round(w.get('B',0)*100,1)}%**, tie: **{round(w.get('tie',0)*100,1)}%**\n")
    md.append(f"_API: http://localhost:8000_\n")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"[daily_report] wrote {OUT_MD}")

if __name__ == "__main__":
    main()
