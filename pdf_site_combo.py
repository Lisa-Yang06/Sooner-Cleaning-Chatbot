
# incremental_dedupe_add.py
import os, json, faiss, numpy as np
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from dotenv import find_dotenv

# === 路径与模型（与建库保持一致） ===
ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SOONER_DATA_DIR", ROOT / "data"))
IDX  = DATA_DIR / "index.faiss"
META = DATA_DIR / "index_meta.json"
NEW  = DATA_DIR / "pdf_pages_chunks.json"   #

EMBED_MODEL = "text-embedding-3-small"
SIM_THRESHOLD = 0.90     # 相似度阈值（归一化后用内积≈cosine）

DRY_RUN = False          # 只检测不写入：True；默认 False 表示去重后追加

# === OpenAI client ===
dotenv_path = find_dotenv(usecwd=True)  # 会从当前工作目录向上找
load_dotenv(dotenv_path=dotenv_path, override=True)
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key = api_key)

def embed_one(text: str) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=[text])
    v = np.array(resp.data[0].embedding, dtype="float32")
    v /= (np.linalg.norm(v) + 1e-12)   # L2 归一化：与建库一致
    return v

def load_index_and_meta():
    index = faiss.read_index(str(IDX)) if IDX.exists() else None
    meta  = json.loads(META.read_text(encoding="utf-8")) if META.exists() else []
    return index, meta

def ensure_index(index, dim: int):
    if index is None:
        index = faiss.IndexFlatIP(dim)  # 归一化+内积 ≈ 余弦
    elif index.d != dim:
        raise ValueError(f"维度不匹配：index.d={index.d}, embed_dim={dim}")
    return index

def main():
    if not NEW.exists():
        raise FileNotFoundError(f"未找到新 chunks 文件：{NEW}")

    items = json.loads(NEW.read_text(encoding="utf-8"))
    index, meta = load_index_and_meta()

    added, skipped = 0, 0
    embed_dim = None

    for n, it in enumerate(items, 1):
        text = it.get("text", "")
        if not text.strip():
            print(f"[{n:02d}] 空文本，跳过。")
            skipped += 1
            continue

        v = embed_one(text)
        if embed_dim is None:
            embed_dim = v.shape[0]
            index = ensure_index(index, embed_dim)

        v = v.reshape(1, -1)

        # 在现有索引中查重
        dup = False
        if index.ntotal > 0:
            D, I = index.search(v, k=1)
            sim = float(D[0, 0])
            nn  = int(I[0, 0])
            if nn >= 0 and sim >= SIM_THRESHOLD:
                dup = True
                ref = meta[nn] if nn < len(meta) else {}
                ref_url = ref.get("metadata", {}).get("url", "")
                print(f"[{n:02d}] SKIP  sim={sim:.3f}  ->  {ref_url}")
                skipped += 1

        if not dup:
            print(f"[{n:02d}] ADD   (idx_total -> {index.ntotal+1}) "
                  f"title={it.get('metadata',{}).get('title','')!r} "
                  f"part={it.get('metadata',{}).get('part')}")
            if not DRY_RUN:
                index.add(v)
                meta.append(it)
                # 也可以每次都保存一次以防中断：但会慢
                # faiss.write_index(index, str(IDX))
                # META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
                added += 1

    if not DRY_RUN:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(IDX))
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完成：added={added}, skipped={skipped}, total_index={index.ntotal if index else 0}")

if __name__ == "__main__":
    main()
