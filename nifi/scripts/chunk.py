import sys, json, re


DEFAULT_LANG = "en"  
DEFAULT_URL = "test" 
DEFAULT_SECTION = "test" 

RAW = sys.stdin.read().strip()
if not RAW:
    sys.exit(0)

# Basic sentence splitter
sentences = re.split(r'(?<=[\.\!\?])\s+', RAW)
MAX_CHARS = 480

chunks = []
buf = []
curr_len = 0

for s in sentences:
    s = s.strip()
    if not s:
        continue
    if curr_len + len(s) + 1 <= MAX_CHARS:
        buf.append(s)
        curr_len += len(s) + 1
    else:
        if buf:
            chunks.append(" ".join(buf))
        buf = [s]
        curr_len = len(s)

if buf:
    chunks.append(" ".join(buf))

for c in chunks:
    payload = {
        "text": c,
        "lang": DEFAULT_LANG,
        "url": DEFAULT_URL,
        "section": DEFAULT_SECTION
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
