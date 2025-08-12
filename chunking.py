# chunk_for_rag.py
import json, re, hashlib
from pathlib import Path

IN  = "data/site_pages_rag.json"       # 你清洗后的文件
OUT = "data/site_pages_chunks.json"    # 分块输出

MAX_CHARS = 1100
OVERLAP   = 0.12  # 邻块重叠比例，帮助跨段语义衔接

def paragraph_split(text: str):
    paras = [p.strip() for p in text.split("\n") if p.strip()] #先用段落切 如果段落内还是大于hardmax 那就按标点符号切
    out = []
    for p in paras:
        if len(p) > MAX_CHARS:
            sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', p) if s.strip()]
            out.extend(sents if sents else [p])
        else:
            out.append(p)
    return out


def soft_chunk(paras): #input是上层按照段落分完的
    # 用于把按照段落分好的文本 再打包成若干个不超过指定长度的chunks
    chunks = []
    buf = ""

    def flush():
        nonlocal buf
        if buf:
            chunks.append(buf.strip())
            buf = ""
        
    for para in paras:
        #够长才切 否则把整段当一句
        sents = re.split(r'(?<=[.!?])\s+', para) if len(para) > MAX_CHARS else [para]

        for s in sents:
            s = s.strip()
            if not s:
                continue
            
            #单句仍然超长 窗口内找到最后一个标点/空格 否则硬切
            while len(s) > MAX_CHARS:
                window = s[:MAX_CHARS]
                pos = max(window.rfind('.'), window.rfind('!'), window.rfind('?'), window.rfind(' '))
                cut = pos + 1 if pos != -1 else MAX_CHARS
                flush()  # 让这段独立成块
                chunks.append(s[:cut].strip())
                s = s[cut:].lstrip()

            if not buf:
                buf = s
            elif len(buf) + 1 + len(s) <= MAX_CHARS:
                buf += " "+s
            else:
                flush()
                buf = s
    flush()
    return chunks


def add_overlap(chunks):
    out = []
    for i, ck in enumerate(chunks):
        if i == 0:
            out.append({"text": ck, "overlap_from_prev": ""}) #第一个块没有前文
        else:
            take = min(200, max(1, int(len(chunks[i-1]) * OVERLAP)))
            out.append({"text": ck, "overlap_from_prev": chunks[i-1][-take:]}) #取上个块最后的take个字符
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

