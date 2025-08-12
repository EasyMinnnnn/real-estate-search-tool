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
    raw = os.getenv("BATCH_BUCKETS", "10,8,6,4,4")
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


# ========== GOOGLE CSE CALLERS ==========
def _call_google(query: str, num_links: int, extra_params: dict | None = None):
    """Gọi Google CSE API, trả về danh sách link (đã canon + dedup)."""
    api_key, cx = _get_env()
    # Giới hạn theo tài liệu: num 1..10
    num_links = max(1, min(int(num_links or 10), 10))

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_links,
        "hl": "vi",
        "gl": "vn",
    }
    if extra_params:
        params.update(extra_params)

    resp = requests.get(url, params=params, timeout=REQ_TIMEOUT)
    # Nếu 4xx, cố gắng lấy thông điệp JSON để debug
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        try:
            msg = resp.json().get("error", {}).get("message")
            raise RuntimeError(f"Google API error: {msg}") from e
        except Exception:
            raise

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


def _call_google_site(query: str, site: str, num_links: int):
    """Gọi CSE giới hạn 1 site bằng tham số siteSearch (ổn định hơn dùng 'site:' trong q)."""
    return _call_google(
        query,
        num_links,
        extra_params={
            "siteSearch": site,
            "siteSearchFilter": "i",  # include
        },
    )


# ========== TOP LINKS PICKER ==========
def get_top_links(query: str, num_links: int = 5) -> list:
    """
    Trả về tối đa num_links link từ Google CSE.
    Ưu tiên gọi riêng từng site bằng siteSearch để tránh lỗi 400 khi dùng 'OR'.
    Thứ tự ưu tiên: batdongsan.com.vn -> phần còn lại (alonhadat, chotot, muaban) -> truy vấn tự do.
    """
    wl = list(_parse_whitelist())
    if not wl:
        wl = ["batdongsan.com.vn", "alonhadat.com.vn", "chotot.com", "muaban.net"]

    # Ưu tiên batdongsan trước
    wl = sorted(wl, key=lambda d: 0 if "batdongsan.com.vn" in d else 1)

    # 1) Thử riêng batdongsan (nếu có trong wl)
    links: list[str] = []
    tried_sites: set[str] = set()
    if "batdongsan.com.vn" in wl:
        tried_sites.add("batdongsan.com.vn")
        try:
            links = _call_google_site(query, "batdongsan.com.vn", num_links)
            if links:
                return links
        except Exception:
            pass

    # 2) Thử từng site còn lại bằng siteSearch
    for site in wl:
        if site in tried_sites:
            continue
        try:
            links = _call_google_site(query, site, num_links)
            if links:
                return links
        except Exception:
            continue

    # 3) Không hạn chế site (truy vấn tự do)
    try:
        links = _call_google(query, num_links, extra_params=None)
        if links:
            return links
    except Exception:
        pass

    # 4) Thử nới lỏng truy vấn (bỏ phần sau dấu phẩy)
    loose = query.split(",")[0].strip()
    if loose and loose != query:
        try:
            links = _call_google(loose, num_links, extra_params=None)
            if links:
                return links
        except Exception:
            pass

    return []


# ===== Heuristic nhận diện link chi tiết vs link danh sách =====
DETAIL_PATTERNS = re.compile(
    r"(?:-pr\d+|-\d{6,}\.(?:htm|html)$|/tin-\d+)",
    re.IGNORECASE,
)

LIST_PATTERNS = re.compile(
    r"(?:/ban-|/mua-ban-|/nha-dat|/tim-kiem|/search|/listing|/danh-sach|/bat-dong-san)",
    re.IGNORECASE,
)


def _sub_links_alonhadat(link: str, soup: BeautifulSoup, max_links: int) -> list:
    subs: list[str] = []
    p0 = urlparse(link)
    domain = p0.netloc.lower()
    path0 = p0.path or "/"

    if re.search(r"-\d{6,}\.(?:htm|html)$", path0):
        return [_canon_url(link)]

    detail_pat = re.compile(r"/[a-z0-9-]+-\d{6,}\.(?:htm|html)$", re.IGNORECASE)

    candidates = []
    candidates.extend(soup.select("h3 a[href]"))
    candidates.extend(soup.select("div.content-item a[href]"))
    candidates.extend(soup.select("a[href].vip, a[href].title"))

    def _try_add(a_tag):
        href = a_tag.get("href", "")
        full = urljoin(link, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https") or p.netloc.lower() != domain:
            return
        if detail_pat.search(p.path or ""):
            cu = _canon_url(full)
            if cu not in subs:
                subs.append(cu)

    for a in candidates:
        _try_add(a)
        if len(subs) >= max_links:
            return subs[:max_links]

    if len(subs) < max_links:
        for a in soup.find_all("a", href=True):
            _try_add(a)
            if len(subs) >= max_links:
                break

    return subs[:max_links]


def get_sub_links(link: str, max_links: int = 5) -> list:
    """
    - Nếu link là trang DANH SÁCH: lấy các link CHI TIẾT ở trong.
    - Nếu link đã là CHI TIẾT: trả luôn link đó (KHÔNG fetch).
    - Có tối ưu riêng cho alonhadat.com.vn.
    """
    p0 = urlparse(link)
    domain = (p0.netloc or "").lower()
    path0 = p0.path or "/"

    # 1) ĐÃ là link chi tiết -> trả luôn (tránh bị 403 khi fetch)
    if DETAIL_PATTERNS.search(path0):
        return [_canon_url(link)]

    # 2) alonhadat: cần HTML để gỡ link chi tiết
    if "alonhadat.com.vn" in domain:
        try:
            resp = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            return _sub_links_alonhadat(link, soup, max_links)
        except Exception:
            return []

    # 3) Domain khác: cố gắng quét link chi tiết trong cùng danh mục (nếu fetch được)
    subs: list[str] = []
    try:
        resp = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        base_domain = p0.netloc
        base_path = (p0.path.rstrip("/") or "/")

        for a in soup.find_all("a", href=True):
            full = urljoin(link, a["href"])
            p = urlparse(full)
            if (
                p.scheme in ("http", "https")
                and p.netloc == base_domain
                and (p.path or "/").startswith(base_path)
                and DETAIL_PATTERNS.search(p.path or "")
            ):
                cu = _canon_url(full)
                if cu not in subs:
                    subs.append(cu)
                    if len(subs) >= max_links:
                        break

        return subs[:max_links]

    except Exception:
        return []


# ===== Tăng cường: tìm trực tiếp link chi tiết theo domain =====
def _enrich_detail_links(query: str, domain: str, need: int, already: set[str]) -> list[str]:
    """
    Gọi Google CSE với các truy vấn chuyên biệt để lấy trực tiếp link CHI TIẾT của 1 domain.
    Dùng cho batdongsan.com.vn đặc biệt.
    """
    patterns = [
        f'{query} site:{domain} inurl:-pr',
        f'{query} site:{domain} inurl:/tin-',
        f'{query} site:{domain} \"pr\"',
        f'{query} site:{domain} inurl:.html',
        f'site:{domain} inurl:-pr',          # thêm 1 lượt tổng quát
    ]
    found: list[str] = []
    for q in patterns:
        if len(found) >= need:
            break
        try:
            links = _call_google(q, num_links=10)
        except Exception:
            continue
        for u in links:
            if u in already:
                continue
            p = urlparse(u)
            if DETAIL_PATTERNS.search(p.path or ""):
                cu = _canon_url(u)
                if cu not in already and cu not in found:
                    found.append(cu)
                    if len(found) >= need:
                        break
    return found[:need]


# ===== Helpers nhận diện để “đào sâu 1 cấp” khi cần =====
def _is_detail(url: str) -> bool:
    p = urlparse(url)
    return bool(DETAIL_PATTERNS.search(p.path or ""))


def _drill_detail_links_if_needed(url: str, max_links: int = 5) -> list[str]:
    if _is_detail(url):
        return [_canon_url(url)]
    return get_sub_links(url, max_links=max_links)


def search_google(query: str, target_total: int = 30) -> list:
    """
    Trả về list dict tin rao: title, price, area, description, image, contact, link.
    target_total=30 để đủ 3 lần bấm (10 tin/lần).
    """
    # Đặt 10 cho chắc (API chỉ trả tối đa 10 kết quả/lần)
    max_top = int(os.getenv("MAX_TOP_LINKS", "10") or "10")
    top_links = get_top_links(query, num_links=max_top)
    if not top_links:
        return []

    buckets = _parse_buckets()[: len(top_links)]
    detail_links: list[str] = []
    seen_links: set[str] = set()

    # 1) gom link chi tiết từ top_links
    for i, link in enumerate(top_links):
        first_level = _drill_detail_links_if_needed(link, max_links=buckets[i] if i < len(buckets) else 5)
        subs: list[str] = []
        for u in first_level:
            subs.extend(_drill_detail_links_if_needed(u, max_links=5))
        for s in subs:
            cs = _canon_url(s)
            if cs not in seen_links:
                seen_links.add(cs)
                detail_links.append(cs)
            if len(detail_links) >= target_total:
                break
        if len(detail_links) >= target_total:
            break

    # 2) nếu chưa đủ, enrich riêng cho batdongsan (và các domain whitelist nếu có)
    if len(detail_links) < target_total:
        wl = list(_parse_whitelist()) or ["batdongsan.com.vn", "alonhadat.com.vn"]
        # Ưu tiên batdongsan trước
        wl = sorted(wl, key=lambda d: 0 if "batdongsan.com.vn" in d else 1)
        need = target_total - len(detail_links)
        for dom in wl:
            more = _enrich_detail_links(query, dom, need, seen_links)
            for u in more:
                if u not in seen_links:
                    seen_links.add(u)
                    detail_links.append(u)
            need = target_total - len(detail_links)
            if need <= 0:
                break

    # 3) extract
    results = []
    for sub in detail_links[:target_total]:
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

    time.sleep(0.25)
    return results
