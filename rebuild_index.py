# rebuild_index_from_meta.py
import os, json, faiss, numpy as np
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SOONER_DATA_DIR", ROOT / "data"))
IDX  = DATA_DIR / "index.faiss"
META = DATA_DIR / "index_meta.json"
EMBED = "text-embedding-3-small"

# load key
load_dotenv(find_dotenv(usecwd=True), override=True)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def embed_batch(texts, batch=128):
    out = []
    for i in range(0, len(texts), batch):
        resp = client.embeddings.create(model=EMBED, input=texts[i:i+batch])
        X = np.array([r.embedding for r in resp.data], dtype="float32")
        X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)  # L2 归一化
        out.append(X)
    return np.vstack(out) if out else np.zeros((0, 1536), dtype="float32")

def main():
    items = json.loads(META.read_text(encoding="utf-8"))
    # 与检索时完全一致的文本拼接方式
    texts = []
    for it in items:
        md = it.get("metadata", {})
        overlap = md.get("overlap_from_prev", "")
        txt = ((overlap + " ") if overlap else "") + it.get("text", "")
        texts.append(txt)

    X = embed_batch(texts)
    idx = faiss.IndexFlatIP(X.shape[1])
    idx.add(X)

    faiss.write_index(idx, str(IDX))
    print(f"rebuilt index: ntotal={idx.ntotal}, meta={len(items)}")

if __name__ == "__main__":
    main()
