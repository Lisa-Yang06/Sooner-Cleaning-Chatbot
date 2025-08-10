import json, faiss, numpy as np #faiss是用来建立相似度向量索引
from pathlib import Path
from openai import OpenAI
import os
from dotenv import load_dotenv

IN  = "data/site_pages_chunks.json"
IDX = "data/index.faiss"
META= "data/index_meta.json"

EMBED_MODEL = "text-embedding-3-small"  # 便宜速度快；追求效果可用 -large

load_dotenv(dotenv_path="/Users/yuxuanyang/soonerbot/.env")
my_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key = my_api_key)

def embed_texts(texts):
    B = 256
    vecs = []
    for i in range(0, len(texts), B):
        batch = texts[i:i+B]
        resp = client.embeddings.create(model=EMBED_MODEL, input=batch) #调API拿到向量
        vecs.extend(e.embedding for e in resp.data)
    return np.array(vecs, dtype="float32")

chunks = json.loads(Path(IN).read_text(encoding="utf-8"))
texts = [c["text"] for c in chunks]
vecs = embed_texts(texts)

index = faiss.IndexFlatIP(vecs.shape[1]) #用dot product当作similarity
# 这里的 IndexFlatIP 表示以后检索的时候用 Inner Product（内积） 作为相似度度量。
faiss.normalize_L2(vecs) #L2归一化：把每个vector除自己的长度 这样刚刚的dot product就是cos值了
index.add(vecs) #把这批向量顺序地塞进索引

faiss.write_index(index, IDX) #把FAISS索引序列化成二进制文件写到硬盘上 路径是IDX
Path(META).write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8") #专门和index.faiss一一对应保存
print(f"Indexed {len(chunks)} chunks -> {IDX}")