# chunk_for_rag_pdf.py
import json, re, hashlib
from pathlib import Path

# 1) 指向你的 PDF 页级 JSON（每条=一页）
IN  = "data/pdf_ite_pages_rag.json"
OUT = "data/pdf_pages_chunks.json"

MAX_CHARS = 1100
OVERLAP   = 0.12  # 取上一个块尾部的百分比做重叠

def paragraph_split(text: str):
    # 先按换行切成“段落”，段落仍超长再按句号切
    text = (text or "").replace("\r", "\n")
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    out = []
    for p in paras:
        if len(p) > MAX_CHARS:
            # 英文 .!? + 中文 。！？
            sents = [s.strip() for s in re.split(r'(?<=[。！？.!?])\s+', p) if s.strip()]
            out.extend(sents if sents else [p])
        else:
            out.append(p)
    return out

def soft_chunk(paras):
    chunks, buf = [], ""

    def flush():
        nonlocal buf
        if buf:
            chunks.append(buf.strip())
            buf = ""

    for para in paras:
        sents = re.split(r'(?<=[。！？.!?])\s+', para) if len(para) > MAX_CHARS else [para]
        for s in sents:
            s = s.strip()
            if not s:
                continue
            while len(s) > MAX_CHARS:
                window = s[:MAX_CHARS]
                pos = max(window.rfind('。'), window.rfind('！'), window.rfind('？'),
                          window.rfind('.'), window.rfind('!'), window.rfind('?'), window.rfind(' '))
                cut = pos + 1 if pos != -1 else MAX_CHARS
                flush()
                chunks.append(s[:cut].strip())
                s = s[cut:].lstrip()
            if not buf:
                buf = s
            elif len(buf) + 1 + len(s) <= MAX_CHARS:
                buf += " " + s
            else:
                flush()
                buf = s
    flush()
    return chunks

def add_overlap(chunks):
    out = []
    for i, ck in enumerate(chunks):
        if i == 0:
            out.append({"text": ck, "overlap_from_prev": ""})
        else:
            take = min(200, max(1, int(len(chunks[i-1]) * OVERLAP)))
            out.append({"text": ck, "overlap_from_prev": chunks[i-1][-take:]})
    return out

pages = json.loads(Path(IN).read_text(encoding="utf-8"))
out = []
for p in pages:
    text = p.get("text", "")
    paras = paragraph_split(text)
    blocks = soft_chunk(paras)
    blocks = add_overlap(blocks)
    for idx, b in enumerate(blocks, 1):
        # 注意：你的 pdf JSON 里 url 通常已含 #page=xx；再加 page 也可
        uid_str = f'{p.get("url","")}::p{p.get("page")}::{idx}'
        out.append({
            "id": hashlib.md5(uid_str.encode()).hexdigest(),
            "text": b["text"],
            "metadata": {
                "url": p.get("url",""),
                "title": p.get("title",""),
                "page": p.get("page"),
                "source": p.get("source","pdf"),
                "doc_id": p.get("doc_id", ""),     # 你的页级 JSON 若没有可留空
                "part": idx,
                "overlap_from_prev": b["overlap_from_prev"]
            }
        })

Path(OUT).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Chunks: {len(out)} -> {OUT}")

