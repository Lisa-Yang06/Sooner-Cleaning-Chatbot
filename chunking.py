# chunk_for_rag.py
import json, re, hashlib
from pathlib import Path

IN  = "data/site_pages_rag.json"       # 你清洗后的文件
OUT = "data/site_pages_chunks.json"    # 分块输出

MAX_CHARS = 1100
HARD_MAX  = 1400
OVERLAP   = 0.12  # 邻块重叠比例，帮助跨段语义衔接

def paragraph_split(text: str):
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paras) <= 2 and len(text) > HARD_MAX:
        paras = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", text) if s.strip()]
    return paras

def soft_chunk(paras):
    chunks, buf, cur = [], [], 0
    def flush():
        nonlocal buf, cur
        if buf:
            chunks.append(" ".join(buf).strip())
            buf, cur = [], 0
    for para in paras:
        L = len(para)
        if L > HARD_MAX:
            flush()
            start = 0
            while start < L:
                end = min(start + HARD_MAX, L)
                cut = end
                m = re.search(r"[.!?。！？]\s*\S*$", para[start:end])
                if m: cut = start + m.end()
                chunks.append(para[start:cut].strip())
                start = cut
            continue
        if cur + L + (1 if buf else 0) <= MAX_CHARS:
            buf.append(para); cur += L + (1 if buf else 0)
        else:
            flush(); buf.append(para); cur = L
    flush()
    return chunks

def add_overlap(chunks):
    out = []
    for i, ck in enumerate(chunks):
        if i == 0:
            out.append({"text": ck, "overlap_from_prev": ""})
        else:
            take = max(1, int(len(chunks[i-1]) * OVERLAP))
            out.append({"text": ck, "overlap_from_prev": chunks[i-1][-take:]})
    return out

pages = json.loads(Path(IN).read_text(encoding="utf-8"))
out = []
for p in pages:
    text = p["text"]
    paras = paragraph_split(text)
    blocks = soft_chunk(paras)
    blocks = add_overlap(blocks)
    for idx, b in enumerate(blocks, 1):
        out.append({
            "id": hashlib.md5(f'{p["url"]}::{idx}'.encode()).hexdigest(),
            "text": b["text"],
            "metadata": {
                "url": p["url"],
                "title": p.get("title",""),
                "part": idx,
                "overlap_from_prev": b["overlap_from_prev"]
            }
        })

Path(OUT).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Chunks: {len(out)} -> {OUT}")

