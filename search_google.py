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


def _parse_buckets() -> list[int]:
    raw = os.getenv("BATCH_BUCKETS", "8,8,6,4,4")
    try:
        buckets = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        return buckets or [8, 8, 6, 4, 4]
    except Exception:
        return [8, 8, 6, 4, 4]


def _parse_whitelist() -> set[str]:
    raw = os.getenv("SITE_WHITELIST", "").strip()
    if not raw:
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def get_top_links(query: str, num_links: int = 5) -> list[str]:
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
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Google API HTTP {resp.status_code}: {resp.text[:200]}") from e

    data = resp.json()
    if "error" in data:
        msg = data["error"].get("message", "Unknown Google API error")
        raise RuntimeError(f"Google API error: {msg}")

    items = data.get("items", [])
    if not items:
        raise RuntimeError(
            "Google API trả về 0 kết quả. Kiểm tra CSE đã bật 'Search the entire web', "
            "quota Custom Search JSON API, hoặc thử truy vấn khác."
        )

    whitelist = _parse_whitelist()
    links = []
    for item in items:
        link = item.get("link")
        if not link or not link.startswith("http"):
            continue
        cu = _canon_url(link)
        if whitelist:
            d = urlparse(cu).netloc.lower()
            if not any(w in d for w in whitelist):
                continue
        links.append(cu)

    # Khử trùng lặp, giữ thứ tự
    seen, dedup = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup[:num_links]


def get_sub_links(link: str, max_links: int = 3) -> list[str]:
    """
    Lấy link con cùng domain, sâu hơn, có pattern id tin (prxxxx, *.htm/*.html có số).
    """
    subs: list[str] = []
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


def search_google(query: str, target_total: int = 30) -> list[dict]:
    """
    Trả về list dict tin rao: title, price, area, description, image, contact, link.
    target_total=30 để đủ 3 lần bấm (10 tin/lần).
    """
    max_top = int(os.getenv("MAX_TOP_LINKS", "5") or "5")
    top_links = get_top_links(query, num_links=max_top)

    buckets = _parse_buckets()
    # nếu số top_links ít hơn buckets -> cắt buckets tương ứng
    buckets = buckets[: len(top_links)]

    results: list[dict] = []
    seen_links: set[str] = set()

    for i, link in enumerate(top_links):
        subs = get_sub_links(link, max_links=buckets[i] if i < len(buckets) else 3)
        for sub in subs:
            if sub in seen_links:
                continue
            seen_links.add(sub)
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
        # lịch sự với site: ngủ 300ms giữa các domain
        time.sleep(0.3)

    return results
