# query_openai.py
import json, faiss, numpy as np
from pathlib import Path
from openai import OpenAI
import os
from dotenv import load_dotenv
from dotenv import find_dotenv
# query_openai.py
import os, json, faiss, numpy as np
from pathlib import Path

# 以当前文件为基准，定位到 repo 内的 data 目录
ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SOONER_DATA_DIR", ROOT / "data"))  # 允许用环境变量覆盖

IDX  = str(DATA_DIR / "index.faiss") #用path的/重载来拼接路径
META = str(DATA_DIR / "index_meta.json")

_index = None
_meta  = None

def _load_index_and_meta():
    global _index, _meta
    if _index is None:
        p = Path(IDX)
        if not p.exists():
            raise FileNotFoundError(f"FAISS index not found at:\n{p}\n"
                                    f"Set SOONER_DATA_DIR or run build_index_openai.py")
        _index = faiss.read_index(str(p))
    if _meta is None:
        m = Path(META)
        if not m.exists():
            raise FileNotFoundError(f"Meta file not found at:\n{m}")
        _meta = json.loads(m.read_text(encoding="utf-8"))
    return _index, _meta



EMBED = "text-embedding-3-small"   # 和建库时一致
CHAT  = "gpt-4o"              # 任选可用聊天模型名

dotenv_path = find_dotenv(usecwd=True)  # 会从当前工作目录向上找
load_dotenv(dotenv_path=dotenv_path, override=True)
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key = api_key)


# 先要把query转成embedding 并且L2归一化得到的vector 和库里保持一致
def embed_query(q:str) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED, input = [q])
    v = np.array(resp.data[0].embedding, dtype="float32") #取出第一个embedding 再转换为numpy数组
    v /= np.linalg.norm(v) + 1e-12 #对v进行L2归一化 把向量单位变为0
    return v #返回归一化后的query的vector embedding！

def retrieve(query:str, k: int=5):
    index, meta = _load_index_and_meta()
    vq = embed_query(query).reshape(1, -1)
    D, I = index.search(vq, k) #用点乘做相似度搜索 D是相似度分数 i是行号 这里出来的还是个2D array
    hits = []
    for rank, (i, score) in enumerate(zip(I[0], D[0]), 1):
        if i < 0:  # 没命中
            continue
        item = meta[i]

        overlap = item["metadata"].get("overlap_from_prev", "")
        text = ((overlap + " ") if overlap else "") + item["text"]

        hits.append({
            "rank":  rank,
            "score": float(score),           # 归一化后 IP ≈ 余弦相似度，越大越相关
            "text":  text,
            "url":   item["metadata"]["url"],
            "title": item["metadata"].get("title",""),
            "part":  item["metadata"].get("part", 0),
        })
    return hits

def answer(query: str, hits: list):
    context = "\n\n".join(
        f"[{h['rank']}] {h['title']} ({h['url']})\n{h['text']}" for h in hits
    )
    prompt = f"""You are a helpful assistant for SoonerCleaning.
    Use ONLY the context below to answer the question. If the context is insufficient, say you don't know.
    Cite sources by index like [1], [2] and list their URLs at the end. 
    That said, your goal is also to promote SoonerCleaning to potential customers

    Question: {query}

    Context:
    {context}
    """

    resp = client.chat.completions.create(
        model=CHAT,
        messages=[{"role":"user","content": prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content

if __name__ == "__main__":
    q = "Spunlace Woodpulp & PP Material Dual Textured Woodpulp & PP CLeaning Material, is it man-made"
    hits = retrieve(q, k=50)
    print("Top hits:")
    for h in hits:
        print(f"{h['rank']:>2}  {h['score']:.3f}  {h['title']}  {h['url']}")
    print("\nAnswer:\n")
    print(answer(q, hits))
