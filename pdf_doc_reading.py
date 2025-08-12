# TODO: 读公司pdf--clean--chunk--导出json
import fitz # PyMuPDF
import json, re, hashlib
from pathlib import Path

IN_PATH = Path("data/Soonercleaning catalog of nonwoven.pdf")
OUT_JSON = Path("data/pdf_ite_pages_rag.json")

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

def page_text(page)->str:
    blocks = page.get_text("blocks") # 用PyMuPDF把这页拆成文本块
    blocks = sorted(blocks, key=lambda b: (round(b[1],1), round(b[0],1))) # 保证接下来是按照从上到下从左到右拼
    texts = [b[4] for b in blocks if b[4] and b[4].strip()] # block里第四个元素是text
    return clean_text("\n\n".join(texts)) #把每个block用两个回车练起来

def get_section(page:int):
    for (x, y), val in SECTION_DICT.items():
        if page in range(x, y+1):
            return val
        continue

def pdf_to_items(pdf_path: Path):
    doc = fitz.open(pdf_path) # 用这个东西可以打开pdf 之后doc[i]就能访问第i页
    doc_title = pdf_path.stem.strip()
    doc_id = hashlib.md5(str(pdf_path.resolve()).encode()).hexdigest() #给整份pdf生成一个文档级ID

    items = []
    for i in range(len(doc)):
        txt = page_text(doc[i])
        if not txt:
             continue
        page_no = i+1
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
        })
    doc.close()
    return items

def main():
    all_items = []
    all_items.extend(pdf_to_items(IN_PATH))
    OUT_JSON.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(all_items)} items -> {OUT_JSON}")


if __name__ == "__main__":
    main()