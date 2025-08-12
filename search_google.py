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
    """Chuẩn hóa URL để khử trùng lặp: bỏ fragment/query, bỏ '/' cuối."""
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
    raw = os.getenv("BATCH_BUCKETS", "10,8,6,4,4")  # hơi nới 1 chút ở domain đầu
    try:
        buckets = [int(x.strip()) for x in raw.split(",") if x.strip()]
        return buckets or [10, 8, 6, 4, 4]
    except Exception:
        return [10, 8, 6, 4, 4]


def _parse_whitelist():
    raw = os.getenv("SITE_WHITELIST", "").strip()
    if not raw:
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _call_google(query: str, num_links: int):
    """Gọi Google CSE API, trả về danh sách link (đã canon + dedup)."""
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
        wl = {"batdongsan.com.vn", "alonhadat.com.vn", "chotot.com", "muaban.net"}
    # cập nhật hàm _bias sau khi wl có giá trị mặc định
    add = " OR ".join(f"site:{d}" for d in wl)
    links = _call_google(f"{query} {add}", num_links)
    if links:
        return links

    # Try 3: nới lỏng truy vấn (bỏ phần sau dấu phẩy)
    loose = query.split(",")[0].strip()
    if loose and loose != query:
        links = _call_google(loose, num_links)
        if links:
            return links

    return []


# ===== Heuristic nhận diện link chi tiết vs link danh sách =====
DETAIL_PATTERNS = re.compile(
    r"(?:/pr\d+|/tin-|\d{6,}\.(?:htm|html)$|/ban-|/nha-|/can-ho-|/chung-cu-|/bds-)",
    re.IGNORECASE,
)

LIST_PATTERNS = re.compile(
    r"(?:/ban-|/mua-ban-|/nha-dat|/tim-kiem|/search|/listing|/danh-sach|/bat-dong-san)",
    re.IGNORECASE,
)


def get_sub_links(link: str, max_links: int = 5) -> list:
    """
    - Nếu link là trang DANH SÁCH: lấy các link CHI TIẾT ở trong.
    - Nếu link đã là CHI TIẾT: trả luôn link đó (để không bỏ lỡ).
    """
    subs: list[str] = []
    try:
        resp = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        p0 = urlparse(link)
        base_domain = p0.netloc

        # Nếu link có vẻ là trang CHI TIẾT → trả luôn
        if DETAIL_PATTERNS.search(p0.path or ""):
            return [_canon_url(link)]

        # Còn lại: coi là trang DANH SÁCH → gom link chi tiết bên trong
        for a in soup.find_all("a", href=True):
            full = urljoin(link, a["href"])
            p = urlparse(full)
            if p.scheme not in ("http", "https") or p.netloc != base_domain:
                continue
            # Ưu tiên link chi tiết theo pattern
            if DETAIL_PATTERNS.search(p.path or ""):
                cu = _canon_url(full)
                if cu not in subs:
                    subs.append(cu)
                    if len(subs) >= max_links:
                        break

        # Nếu vẫn chưa đủ, nới lỏng: lấy thêm các link có từ khóa “bán/nhà/căn hộ…”
        if len(subs) < max_links:
            for a in soup.find_all("a", href=True):
                if len(subs) >= max_links:
                    break
                full = urljoin(link, a["href"])
                p = urlparse(full)
                if p.scheme not in ("http", "https") or p.netloc != base_domain:
                    continue
                if LIST_PATTERNS.search(p.path or "") or "/chi-tiet" in (p.path or ""):
                    cu = _canon_url(full)
                    if cu not in subs:
                        subs.append(cu)

        return subs[:max_links]
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
        subs = get_sub_links(link, max_links=buckets[i] if i < len(buckets) else 5)
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
        time.sleep(0.25)  # lịch sự với site

    return results
