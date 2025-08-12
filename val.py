import os, json, faiss, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SOONER_DATA_DIR", ROOT / "data")).resolve()
IDX, META = DATA_DIR/"index.faiss", DATA_DIR/"index_meta.json"
print("DATA_DIR:", DATA_DIR)

index = faiss.read_index(str(IDX))
meta  = json.loads(META.read_text(encoding="utf-8"))

print("index.ntotal =", index.ntotal, "| meta =", len(meta))
pdf_count = sum((it.get("metadata",{}).get("source")=="pdf") or ("#page=" in it.get("metadata",{}).get("url","")) for it in meta)
print("PDF 条目数 =", pdf_count)

needle = "spunlace woodpulp & pp"
contains = [i for i,it in enumerate(meta)
            if needle in ((it.get("metadata",{}).get("overlap_from_prev","")+" "+it.get("text","")).lower())]
print("纯文本 contains 命中 =", len(contains), "样例 idx =", contains[:5])
