# TODO: 读公司pdf--clean--chunk--导出json
# 依赖：pdfminer.six

import json, re, hashlib
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage

IN_PATH = Path("data/Soonercleaning catalog of nonwoven.pdf")
OUT_JSON = Path("data/pdf_ite_pages_rag_miner.json")

SECTION_DICT = {
    (3,3): "Company Profile",
    (4,4): "Production Line",
    (5,5): "Quality Control System",
    (6,6): "Enterprise Advantage",
    (7, 14): "Spunlace Biodegradable Material",
    (15, 20): "Spunlace Viscose & PET Material",
    (21, 25): "Spunlace Woodpulp & PET Material",
    (26, 31): "Spunlace Woodpulp & PP Material",
    (32, 35): "Meltblown Material"
}

def clean_text(s: str) -> str:
    s = s.replace("\u00a0"," ").replace("\r","\n")
    s = re.sub(r"-\n(?=\w)", "", s)       # 行尾连字符断行修复
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# 注意：为了用 pdfminer，这里把签名改成 (pdf_path, page_no)
def page_text(pdf_path: Path, page_no: int) -> str:
    # pdfminer 用 0-based 页码
    txt = extract_text(str(pdf_path), page_numbers=[page_no - 1]) or ""
    return clean_text(txt)

def get_section(page:int):
    for (x, y), val in SECTION_DICT.items():
        if page in range(x, y+1):
            return val
        continue

def pdfminer_num_pages(pdf_path: Path) -> int:
    with open(pdf_path, "rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        return sum(1 for _ in PDFPage.create_pages(doc))

def pdf_to_items(pdf_path: Path):
    doc_title = pdf_path.stem.strip()
    doc_id = hashlib.md5(str(pdf_path.resolve()).encode()).hexdigest()  # 文档级ID（如需可加入 item）

    items = []
    n_pages = pdfminer_num_pages(pdf_path)
    for i in range(1, n_pages + 1):
        txt = page_text(pdf_path, i)
        if not txt:
            continue

        page_no = i
        pseudo_url = f"file://{pdf_path.resolve()}#page={page_no}"

        section = get_section(page_no)
        txt = (section + "\n" + txt).strip() if section else txt

        items.append({
            "id": hashlib.md5(pseudo_url.encode()).hexdigest(),
            "url": pseudo_url,
            "title": f"{doc_title} - p.{page_no}",
            "text": txt,
            "source": "pdf",
            "page": page_no,
            # "doc_id": doc_id,  # 如果你想在下游按文档聚合，可以把这行放开
        })
    return items

def main():
    all_items = []
    all_items.extend(pdf_to_items(IN_PATH))
    # 确保输出目录存在（唯一的小改动，避免 data/ 不存在时报错）
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(all_items)} items -> {OUT_JSON}")

if __name__ == "__main__":
    main()
