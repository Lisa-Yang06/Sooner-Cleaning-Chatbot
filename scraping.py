from dotenv import load_dotenv #来自detenv这个库 读取.evn里的环境变量
import os
import time, re, json, requests
from collections import deque
from bs4 import BeautifulSoup
import urllib.parse as up
from urllib.robotparser import RobotFileParser

load_dotenv(dotenv_path="/Users/yuxuanyang/soonerbot/.env")
api_key = os.getenv("OPENAI_API_KEY")
#print(api_key)

import requests
from bs4 import BeautifulSoup
RESPECT_ROBOTS = True #不爬不让爬的内容
BASE_URL = "https://www.soonercleaning.com/" #避免爬出站
PATH_ALLOW = {
    "",
    "aboutus.html",
    "products.html",
    "news.html",
    "support.html",
    "contactus.html"
}
ALLOW_DOMAINS = {"soonercleaning.com", "www.soonercleaning.com"}
MAX_PAGES  = 50000
MAX_DEPTH  = 50
REQUEST_INTERVAL = 0.25
TIMEOUT    = 12
HEADERS    = {"User-Agent":"SoonerBot/1.0 (+site QA)"}

def same_site(u: str) -> bool:
    """同域判断：scheme http/https 且 netloc 在白名单内"""
    try:
        p = up.urlparse(u)
        return (p.scheme in ("http", "https")) and (p.netloc in ALLOW_DOMAINS)
    except Exception:
        return False

def canonicalize(url: str) -> str:
    # 统一url格式 避免同一页面多次抓取
    """URL 规范化：去 #fragment、去常见追踪参数、标准化路径/域名大小写"""

    u = up.urlparse(url.split("#")[0]) #把锚点去掉 这个只影响页面定位 不影响内容
    qs = up.parse_qs(u.query, keep_blank_values=False)
    keep = {}  # 如果需要保留某些参数，在这里放入（如 keep["lang"] = qs.get("lang", [])）
    new_q = up.urlencode(keep, doseq=True)

    path = u.path or "/"
    # 统一去掉非根路径末尾的斜杠
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    return up.urlunparse((u.scheme, u.netloc.lower(), path, "", new_q, ""))


def extract_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if (soup.title and soup.title.string) else ""

    # 先锁定 #content
    content = soup.select_one("#content")

    # 去噪，但保留 #content 子树
    noise_selectors = ("nav", "header", "footer", ".navbar", ".menu", ".sidebar", ".footer", "script", "style")
    for sel in noise_selectors:
        for t in soup.select(sel):
            if content and content in t.parents:  # 在 #content 里就跳过
                continue
            t.decompose()

    # 重新获取（去噪后结构更干净）
    content = soup.select_one("#content") or content

    blocks = []

    # 1) #content 内 .desc（含 description/desc-*）
    if content:
        for node in content.select(".desc, [class*='desc']"):
            txt = node.get_text(" ", strip=True)
            if txt:
                blocks.append(txt)

        # 2) #content 内常规正文
        for tag in content.select("h1, h2, h3, h4, h5, p, li"):
            txt = tag.get_text(" ", strip=True)
            if txt:
                blocks.append(txt)

    # 3) 全页补充（#content 之外的重要文本）
    for tag in soup.select("h1, h2, h3, h4, h5, p, li"):
        txt = tag.get_text(" ", strip=True)
        if txt:
            blocks.append(txt)

    # 去重保序
    seen, uniq = set(), []
    for b in blocks:
        if b not in seen:
            seen.add(b)
            uniq.append(b)

    text = "\n".join(([title] if title else []) + uniq)
    text = re.sub(r"\n{2,}", "\n", text)
    print(text)
    return title, text


def build_robot(base: str) -> RobotFileParser | None:
    if not RESPECT_ROBOTS: #如果不需要respect robot那可以直接返回none 后面就不查robits了
        return None
    rp = RobotFileParser()
    try:
        rp.set_url(up.urljoin(base, "/robots.txt"))
        rp.read() #用read读取robot规则
        return rp
    except Exception:
        return None

READ_MORE_PAT = re.compile(
    r"(Read\s*More|learn\s*more|more\s*details|full\s*article|查看详情|了解更多|阅读全文|更多详情|查看全文)",
    re.I,
)

def safe_href(href: str) -> bool:
    href = href.strip().lower()
    return not (href.startswith(("mailto:", "tel:", "javascript:", "#")))

def is_read_more_anchor(a_tag) -> bool:
    """判断一个 <a> 是否是 'Read More/查看详情' 类型的按钮/链接。"""
    # 1) 文本匹配
    text = (a_tag.get_text(" ", strip=True) or "").lower()
    if READ_MORE_PAT.search(text):
        return True
    # 2) class/aria-label/rel 等属性辅助判断
    cls = " ".join(a_tag.get("class") or []).lower()
    aria = (a_tag.get("aria-label") or "").lower()
    rel  = " ".join(a_tag.get("rel") or []).lower()
    if any(k in cls for k in ["readmore", "more", "btn-more", "btn_read", "see-more", "detail"]):
        return True
    if READ_MORE_PAT.search(aria) or READ_MORE_PAT.search(rel):
        return True
    # 3) href 本身包含关键词（有些站直接把 more 放路径）
    href = (a_tag.get("href") or "").lower()
    if any(k in href for k in ["read", "more", "detail", "details"]):
        return True
    return False

def looks_like_html(url: str) -> bool:
    bad_ext = (".pdf",".jpg",".jpeg",".png",".gif",".svg",".webp",".zip",".rar",".7z",
               ".doc",".docx",".xls",".xlsx",".ppt",".pptx",".mp4",".mp3",".avi",".mov",
               ".css",".js",".ico")
    p = up.urlparse(url)
    return not any(p.path.lower().endswith(ext) for ext in bad_ext)

def crawl():
    # 1) 起始队列
    seeds = [canonicalize(up.urljoin(BASE_URL, p)) for p in PATH_ALLOW]
    seeds = list(dict.fromkeys(seeds)) #去重复并保持顺序

    rp = build_robot(BASE_URL)
    seen: set[str] = set()      # 已抓取或确认处理过
    queued: set[str] = set()    # 已经入队，避免重复入队
    q: deque[tuple[str, int]] = deque() #deque支持头尾入队

    for u in seeds:
        if same_site(u) and looks_like_html(u):
            q.append((u, 0))
            queued.add(u)

    out: list[dict] = []
    pages_done = 0

    while q and len(out) < MAX_PAGES:
        url, depth = q.popleft()
        print(f"[crawl] depth={depth} queue={len(q)} url={url}")

        if depth > MAX_DEPTH:
            continue

        url = canonicalize(url)

        # robots 检查
        if rp and RESPECT_ROBOTS:
            try:
                if not rp.can_fetch(HEADERS["User-Agent"], url):
                    continue
            except Exception:
                pass

        # 抓页面
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        except requests.RequestException:
            continue
        # 下面这两行是在过滤掉不正常的html响应
        ctype = (r.headers.get("Content-Type") or "").lower()
        if r.status_code != 200 or ("text/html" not in ctype and "application/xhtml+xml" not in ctype):
            continue

        # 抽正文
        title, text = extract_text(r.text)
        if len(text) >= 120:
            out.append({"url": url, "title": title, "text": text})
            pages_done += 1
            if pages_done % 50 == 0:
                print(f"[progress] saved={pages_done}, total_out={len(out)}")

        # 标记已处理（避免重复抓）
        seen.add(url)

        # 解析链接：先分类，绝不在这之前入队
        # 下面这个应该都是在处理href
        soup = BeautifulSoup(r.text, "html.parser")
        read_more_links = []
        normal_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not safe_href(href):
                continue

            nxt = up.urljoin(url, href)
            nxt = canonicalize(nxt)

            if not same_site(nxt):
                continue
            if not looks_like_html(nxt):
                continue
            if nxt in seen or nxt in queued:
                continue

            if is_read_more_anchor(a):
                read_more_links.append(nxt)
            else:
                normal_links.append(nxt)

        # **策略：Read More 优先入队**（不直接抓，避免当前页触发大量请求）
        for detail_url in read_more_links:
            q.appendleft((detail_url, depth + 1)) #append left优先处理
            queued.add(detail_url)

        # 其次再入队普通链接
        for nxt in normal_links:
            q.append((nxt, depth + 1))
            queued.add(nxt)

        time.sleep(REQUEST_INTERVAL)

    return out

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    pages = crawl()
    with open("data/site_pages.json", "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    print(f"✅ Crawled pages: {len(pages)}")
    print("👉 Saved to data/site_pages.json")


    '''
    整体思路：
    queue：先放入base url+那几个大类
    if queue + 不超过page number：
    检查depth是否在范围内
        （保证是正确的html后）抓去正文+标记为seen
        找href readmore的插队 其他的正常放入队列（BFS）这些depth都要+1

    '''