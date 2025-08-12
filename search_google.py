import os
import re
import time
from urllib.parse import urlparse, urljoin, urlunparse

import requests
from bs4 import BeautifulSoup
from crawler import extract_info_generic

# --------- HTTP defaults ----------
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
REQ_TIMEOUT = 20


def _get_env():
    """Lấy API key và CX từ env/secrets mỗi lần gọi (tránh bị cache lúc import)."""
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        raise RuntimeError("Thiếu GOOGLE_API_KEY hoặc GOOGLE_CX trong biến môi trường")
    return api_key, cx


def _canon_url(s: str) -> str:
    """Chuẩn hóa URL để khử trùng lặp: bỏ query/fragment, bỏ '/' cuối."""
    try:
        p = urlparse(s)
        p = p._replace(query="", fragment="")
        path = p.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        p = p._replace(path=path)
        return urlunparse(p)
    except Exception:
        return s


def _parse_buckets():
    raw = os.getenv("BATCH_BUCKETS", "8,8,6,4,4")
    try:
        buckets = [int(x.strip()) for x in raw.split(",") if x.strip()]
        return buckets or [8, 8, 6, 4, 4]
    except Exception:
        return [8, 8, 6, 4, 4]


def _parse_whitelist():
    raw = os.getenv("SITE_WHITELIST", "").strip()
    if not raw:
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _call_google(query: str, num_links: int) -> list:
    """Gọi Google CSE và trả về danh sách link (đã canon + dedup)."""
    api_key, cx = _get_env()
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_links,
        "hl": "vi",
        "gl": "vn",
    }
    resp = requests.get(url, params=params, timeout=REQ_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        msg = data["error"].get("message", "Unknown Google API error")
        raise RuntimeError(f"Google API error: {msg}")

    links = []
    for item in data.get("items", []):
        link = item.get("link")
        if link and link.startswith("http"):
            links.append(_canon_url(link))

    # dedup giữ thứ tự
    seen, dedup = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup[:num_links]


def get_top_links(query: str, num_links: int = 5) -> list:
    """
    Trả về tối đa num_links link từ Google CSE.
    Có fallback nếu truy vấn đầu trả về 0 items.
    """
    # Try 1: query gốc
    links = _call_google(query, num_links)
    if links:
        return links

    # Try 2: bias theo domain whitelist (hoặc mặc định 2 domain lớn)
    wl = _parse_whitelist()
    if not wl:
        wl = {"batdongsan.com.vn", "alonhadat.com.vn"}
    site_q = query + " " + " OR ".join(f"site:{d}" for d in wl)
    links = _call_google(site_q, num_links)
    if links:
        return links

    # Try 3: nới lỏng (bỏ phần sau dấu phẩy nếu có)
    loose = query.split(",")[0].strip()
    if loose and loose != query:
        links = _call_google(loose, num_links)
    return links


def get_sub_links(link: str, max_links: int = 3) -> list:
    """
    Lấy link con cùng domain, sâu hơn, có pattern id tin (prxxxx, *.htm/*.html có số).
    """
    subs = []
    try:
        resp = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        base = urlparse(link)
        base_domain, base_path = base.netloc, (base.path.rstrip("/") or "/")

        whitelist = _parse_whitelist()
        for a in soup.find_all("a", href=True):
            full = urljoin(link, a["href"])
            p = urlparse(full)
            if (
                p.scheme in ("http", "https")
                and p.netloc == base_domain
                and (p.path or "/").startswith(base_path)
                and p.path != base_path
            ):
                # heuristic: có id bài
                if ("pr" in p.path) or re.search(r"/\d{6,}\.(?:htm|html)$", p.path):
                    cu = _canon_url(full)
                    if whitelist:
                        d = urlparse(cu).netloc.lower()
                        if not any(w in d for w in whitelist):
                            continue
                    if cu not in subs:
                        subs.append(cu)
                        if len(subs) >= max_links:
                            break
        return subs
    except Exception:
        return []


def search_google(query: str, target_total: int = 30) -> list:
    """
    Trả về list dict tin rao: title, price, area, description, image, contact, link.
    target_total=30 để đủ 3 lần bấm (10 tin/lần).
    """
    max_top = int(os.getenv("MAX_TOP_LINKS", "5") or "5")
    top_links = get_top_links(query, num_links=max_top)
    if not top_links:
        return []

    buckets = _parse_buckets()[: len(top_links)]
    results = []
    seen = set()

    for i, link in enumerate(top_links):
        subs = get_sub_links(link, max_links=buckets[i] if i < len(buckets) else 3)
        for sub in subs:
            if sub in seen:
                continue
            seen.add(sub)
            try:
                info = extract_info_generic(sub)
            except Exception as e:
                info = {
                    "link": sub,
                    "title": f"❌ Lỗi khi trích xuất: {e}",
                    "price": "",
                    "area": "",
                    "description": "",
                    "image": "",
                    "contact": "",
                }
            results.append(info)
            if len(results) >= target_total:
                return results
        # lịch sự với site
        time.sleep(0.3)

    return results
