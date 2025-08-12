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
    """Chuẩn hóa URL để khử trùng lặp: bỏ fragment/query theo heuristic đơn giản."""
    try:
        p = urlparse(s)
        # bỏ query/fragment để tránh trùng cùng bài nhưng khác tracking params
        p = p._replace(query="", fragment="")
        # chuẩn hóa path: bỏ dấu "/" cuối
        path = p.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        p = p._replace(path=path)
        return urlunparse(p)
    except Exception:
        return s


def _parse_whitelist():
    """Lấy danh sách domain whitelist từ biến môi trường SITE_WHITELIST."""
    wl_raw = os.getenv("SITE_WHITELIST", "").strip()
    if not wl_raw:
        return set()
    return {d.strip() for d in wl_raw.split(",") if d.strip()}


def _call_google(query: str, num_links: int):
    """Gọi Google CSE API, trả về danh sách link."""
    api_key, cx = _get_env()
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": num_links, "hl": "vi"}
    resp = requests.get(url, params=params, timeout=REQ_TIMEOUT)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Google API HTTP {resp.status_code}: {resp.text[:200]}") from e

    data = resp.json()
    if "error" in data:
        msg = data["error"].get("message", "Unknown Google API error")
        raise RuntimeError(f"Google API error: {msg}")

    links = []
    for item in data.get("items", []):
        link = item.get("link")
        if link and link.startswith("http"):
            links.append(_canon_url(link))

    # khử trùng lặp, giữ thứ tự
    seen, dedup = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup


def get_top_links(query: str, num_links: int = 5) -> list:
    """
    Trả về tối đa num_links link từ Google CSE.
    Nếu FORCE_SITE_BIAS=1 hoặc có SITE_WHITELIST -> thêm 'site:' ngay từ lần gọi đầu.
    Nếu vẫn rỗng, thử lại các fallback.
    """
    wl = _parse_whitelist()
    force_bias = os.getenv("FORCE_SITE_BIAS", "0") == "1"

    def _bias(q: str) -> str:
        if not wl:
            return q
        add = " OR ".join(f"site:{d}" for d in wl)
        return f"{q} {add}"

    # Try 1: nếu ép bias
    if force_bias and wl:
        links = _call_google(_bias(query), num_links)
        if links:
            return links

    # Try 1 (không ép bias)
    links = _call_google(query, num_links)
    if links:
        return links

    # Try 2: bias theo whitelist hoặc mặc định
    if not wl:
        wl = {"batdongsan.com.vn", "alonhadat.com.vn"}
    links = _call_google(_bias(query), num_links)
    if links:
        return links

    # Try 3: nới lỏng truy vấn (bỏ phần sau dấu phẩy)
    loose = query.split(",")[0].strip()
    if loose and loose != query:
        links = _call_google(loose, num_links)
        if links:
            return links

    return []


def get_sub_links(link: str, max_links: int = 3) -> list:
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

        for a in soup.find_all("a", href=True):
            full = urljoin(link, a["href"])
            p = urlparse(full)
            if (
                p.scheme in ("http", "https")
                and p.netloc == base_domain
                and (p.path or "/").startswith(base_path)
                and p.path != base_path
            ):
                # heuristic: có id bài hoặc đường dẫn dạng /ban-...
                if (
                    "pr" in p.path
                    or re.search(r"/\d{6,}\.(?:htm|html)$", p.path)
                    or "/ban-" in p.path
                ):
                    cu = _canon_url(full)
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
    top_links = get_top_links(query, num_links=5)

    # Phân bổ số link con theo từng domain (tổng gần ~30)
    buckets = [8, 8, 6, 4, 4]
    results: list[dict] = []
    for i, link in enumerate(top_links[:5]):
        subs = get_sub_links(link, max_links=buckets[i])
        for sub in subs:
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
