import re, json, hashlib
from pathlib import Path
from urllib.parse import urlparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

import hashlib

IN  = "data/site_pages.json"
OUT = "data/site_pages_rag.json"

# 去重需要用的辅助函数：
def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())

def dedup_exact(docs, near_thresh=0.92):
    """
    docs: List[{"url","title","text"}]
    返回: 去重后的 docs（保留代表作）
    策略：
      精确去重：规范化后完全相同 -> 只留“更长”的那条
    """
    # ---------- 1) 精确去重 ----------
    by_hash = {}
    order = []  # 记录首次出现顺序
    for d in docs:
        t = _norm_text(d["text"])
        h = hashlib.md5(t.encode("utf-8")).hexdigest() #声称唯一的哈希值
        if h not in by_hash:
            by_hash[h] = d
            order.append(h)
        else:
            # 保留更长文本
            if len(_norm_text(d["text"])) > len(_norm_text(by_hash[h]["text"])): #如果当下这个比字典里更长就保留这个
                by_hash[h] = d
    exact = [by_hash[h] for h in order]

    if len(exact) <= 1:
        return exact

    return exact


def too_small_interval(text:str) -> bool:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if all(len(line.split()) <= 15 for line in lines):
        return True
    
    if not lines:
        return True
    

def delete_all(text: str) -> bool:
    if "Read More" in text or len(text.split()) < 5:
        return True
    if too_small_interval(text):
        return True
    else:
        return False


def remove_title_from_start(text: str, title: str) -> str:
    if not title:
        return text
    # 去掉 title 末尾的分隔符
    title_clean = re.sub(r"[\s\-–—:]+$", "", title.strip())
    # 允许 text 开头有空白，title 后面跟可选的分隔符或换行
    pat = re.compile(rf"^\s*{re.escape(title_clean)}(?:\s*[-–—:])?\s*\n?", re.I)
    return pat.sub("", text, count=1)


def clean_text(text: str, title: str) -> str:

    # normalize newline的写法
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    text = remove_title_from_start(text, title)
    
    # 删掉导航行
    text = re.sub(r"^(?:\s*Home\s*>\s*[^\n]*\n?)+", "", text)

    # 删掉结尾的导航
    text = text.rstrip()
    nav_pattern = (
        r"(Home\s*[\n\r]+Company\s*[\n\r]+Support\s*[\n\r]+News\s*[\n\r]+"
        r"Contact[^\n]*[\n\r]+Back[\n\r]+Whatsapp[\n\r]+Skype[\n\r]+QQ\s*)$"
    )
    text = re.sub(nav_pattern, "", text, flags=re.IGNORECASE)

    # 删掉 Full Name: * E-mail: Telephone: Company: * Message: * Verification Code:以及后面所有的东西
    text = re.sub(
        r"\n\* Full Name: \* E-mail: Telephone: Company: \* Message: \* Verification Code:.*",
        "",
        text,
        flags=re.DOTALL  # 跨行匹配，确保把后面所有行都删掉
    )


    return text.strip() #去掉首位空白

def main():
    pages = json.loads(Path(IN).read_text(encoding="utf-8"))
    cleaned = []
    dropped = 0
    for page in pages:
        title = page["title"]
        text = page["text"]
        text = clean_text(text, title)

        if delete_all(text):
            dropped += 1
            continue
        cleaned.append({
            "url": page.get("url", ""),
            "title": title,
            "text": text
        })
    deduped = dedup_exact(cleaned)
    
    Path(OUT).write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Input: {len(pages)}  -> Kept: {len(deduped)}  Dropped: {dropped}")
    print(f"Saved to: {OUT}")

if __name__ == "__main__":
    main()