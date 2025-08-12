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

# ===== Heuristic nhận diện link chi tiết vs link danh sách =====
# Nhận trang chi tiết (tránh gom nhầm danh mục)
DETAIL_PATTERNS = re.compile(
    r"(?:-pr\d+|-\d{6,}\.(?:htm|html)$|/tin-\d+)",
    re.IGNORECASE,
)

LIST_PATTERNS = re.compile(
    r"(?:/ban-|/mua-ban-|/nha-dat|/tim-kiem|/search|/listing|/danh-sach|/bat-dong-san)",
    re.IGNORECASE,
)


# ---------- ENV & utils ----------
def _get_env():
    """Lấy API key và CX từ env/secrets mỗi lần gọi (tránh cache)."""
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
        return []
    # list có thứ tự để ưu tiên (batdongsan đứng trước)
    wl = [d.strip().lower() for d in raw.split(",") if d.strip()]
    wl = sorted(wl, key=lambda d: 0 if "batdongsan.com.vn" in d else 1)
    return wl


# ---------- Google CSE ----------
def _call_google(query: str, want: int, extra: dict | None = None) -> list[str]:
    """
    Gọi Google CSE API (tự phân trang, num<=10/trang) và trả danh sách link đã canon + dedup.
    extra: tham số bổ sung (vd: {"siteSearch": "batdongsan.com.vn", "siteSearchFilter": "i"})
    """
    api_key, cx = _get_env()
    url = "https://www.googleapis.com/customsearch/v1"
    want = max(1, int(want))
    start = 1
    page_size = 10  # giới hạn cứng của API
    out, seen = [], set()

    while len(out) < want:
        take = min(page_size, want - len(out))
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": take,
            "start": start,
            "hl": "vi",
            "gl": "vn",
        }
        if extra:
            params.update(extra)

        resp = requests.get(url, params=params, timeout=REQ_TIMEOUT, headers={"User-Agent": UA})
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            msg = data["error"].get("message", "Unknown Google API error")
            raise RuntimeError(f"Google API error: {msg}")

        items = data.get("items") or []
        if not items:
            break

        for it in items:
            link = it.get("link")
            if not link or not link.startswith("http"):
                continue
            cu = _canon_url(link)
            if cu not in seen:
                seen.add(cu)
                out.append(cu)

        start += page_size
        if start > 91:  # an toàn (CSE ~100 kết quả)
            break

    return out[:want]


# ---------- Lấy sublink ----------
def _sub_links_alonhadat(link: str, soup: BeautifulSoup, max_links: int) -> list:
    """Tối ưu riêng alonhadat: gom link chi tiết trong trang danh mục."""
    subs: list[str] = []
    p0 = urlparse(link)
    domain = p0.netloc.lower()
    path0 = p0.path or "/"

    # Trang chi tiết -> trả luôn
    if re.search(r"-\d{6,}\.(?:htm|html)$", path0):
        return [_canon_url(link)]

    # Trang danh mục -> gom link chi tiết
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
    - Nếu link đã là CHI TIẾT: trả luôn (KHÔNG fetch) → tránh 403 của batdongsan.
    - Nếu là DANH MỤC: tuỳ domain, cố gắng gom link chi tiết bên trong.
    """
    p0 = urlparse(link)
    domain = (p0.netloc or "").lower()
    path0 = p0.path or "/"

    # 1) Link chi tiết -> trả luôn
    if DETAIL_PATTERNS.search(path0):
        return [_canon_url(link)]

    # 2) alonhadat: cần HTML để gỡ link chi tiết
    if "alonhadat.com.vn" in domain:
        try:
            r = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            return _sub_links_alonhadat(link, soup, max_links)
        except Exception:
            return []

    # 3) Domain khác: nếu fetch được thì gom theo pattern
    subs: list[str] = []
    try:
        r = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

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


# ---------- Ưu tiên kéo link chi tiết theo domain (NHANH) ----------
def _detail_links_for_domain(query: str, domain: str, need: int, already: set[str]) -> list[str]:
    """
    Lấy trực tiếp link CHI TIẾT từ Google CSE cho 1 domain:
    - Dùng siteSearch + inurl để bắt pattern trang chi tiết (không fetch HTML danh mục).
    """
    need = max(0, int(need))
    if need == 0:
        return []

    variants = [
        {"q": query, "extra": {"siteSearch": domain, "siteSearchFilter": "i"}},
        {"q": f"{query} inurl:-pr", "extra": {"siteSearch": domain, "siteSearchFilter": "i"}},
        {"q": f"{query} inurl:/tin-", "extra": {"siteSearch": domain, "siteSearchFilter": "i"}},
        {"q": "inurl:-pr", "extra": {"siteSearch": domain, "siteSearchFilter": "i"}},
        {"q": "inurl:/tin-", "extra": {"siteSearch": domain, "siteSearchFilter": "i"}},
    ]

    found: list[str] = []
    for v in variants:
        if len(found) >= need:
            break
        try:
            links = _call_google(v["q"], want=min(20, need * 2), extra=v["extra"])
        except Exception:
            continue
        for u in links:
            if u in already:
                continue
            path = urlparse(u).path or ""
            if DETAIL_PATTERNS.search(path):
                cu = _canon_url(u)
                if cu not in already and cu not in found:
                    found.append(cu)
                    if len(found) >= need:
                        break
    return found[:need]


# ---------- search_google (ưu tiên batdongsan, hết lỗi 400) ----------
def search_google(query: str, target_total: int = 30) -> list:
    """
    Trả về list dict tin rao: title, price, area, description, image, contact, link.
    Chiến lược:
      1) Ưu tiên batdongsan.com.vn → kéo link CHI TIẾT trực tiếp (CSE siteSearch + inurl).
      2) Bổ sung từ các domain khác (SITE_WHITELIST, ưu tiên alonhadat) theo cách tương tự.
      3) Nếu vẫn thiếu: lấy kết quả chung rồi lọc CHI TIẾT; cuối cùng mới đào sâu danh mục 1 cấp.
    """
    target_total = int(target_total or 30)
    first_batch = min(10, target_total)  # bạn muốn 10 tin đầu
    results: list[dict] = []
    detail_links: list[str] = []
    seen_links: set[str] = set()

    # --- 1) Ưu tiên batdongsan trước
    need_bds = first_batch
    bds_more = _detail_links_for_domain(query, "batdongsan.com.vn", need_bds, seen_links)
    for u in bds_more:
        if u not in seen_links:
            seen_links.add(u)
            detail_links.append(u)

    # --- 2) Bổ sung domain whitelist (alonhadat…) để đủ 10 tin đầu
    if len(detail_links) < first_batch:
        wl = _parse_whitelist() or ["alonhadat.com.vn"]
        for dom in wl:
            if dom == "batdongsan.com.vn":
                continue
            need = first_batch - len(detail_links)
            if need <= 0:
                break
            more = _detail_links_for_domain(query, dom, need, seen_links)
            for u in more:
                if u not in seen_links:
                    seen_links.add(u)
                    detail_links.append(u)

    # --- 3) Nếu vẫn thiếu cho tổng target_total → mở rộng
    if len(detail_links) < target_total:
        # 3a) Thử tiếp với whitelist (mỗi domain 1 lượt nữa)
        wl2 = _parse_whitelist() or ["batdongsan.com.vn", "alonhadat.com.vn"]
        wl2 = [d for d in wl2 if d]  # bảo vệ
        for dom in wl2:
            need = target_total - len(detail_links)
            if need <= 0:
                break
            more = _detail_links_for_domain(query, dom, need, seen_links)
            for u in more:
                if u not in seen_links:
                    seen_links.add(u)
                    detail_links.append(u)
                    if len(detail_links) >= target_total:
                        break

    # --- 4) Nếu vẫn thiếu → gọi CSE chung & lọc link chi tiết
    if len(detail_links) < target_total:
        extra = _call_google(query, want=target_total * 2)
        for u in extra:
            if u in seen_links:
                continue
            if DETAIL_PATTERNS.search((urlparse(u).path or "")):
                cu = _canon_url(u)
                seen_links.add(cu)
                detail_links.append(cu)
                if len(detail_links) >= target_total:
                    break

    # --- 5) Cuối cùng, nếu vẫn thiếu → đào sâu 1 cấp từ các top links (có thể chậm)
    if len(detail_links) < target_total:
        # Lấy top links (5–8 link) rồi đào sâu
        max_top = int(os.getenv("MAX_TOP_LINKS", "8") or "8")
        # FORCE_SITE_BIAS: chèn whitelist ngay từ đầu
        wl_env = _parse_whitelist()
        force_bias = os.getenv("FORCE_SITE_BIAS", "0") == "1"
        base_q = query
        if force_bias and wl_env:
            sites = " OR ".join(f"site:{d}" for d in wl_env)
            base_q = f"{query} {sites}"

        top_links = _call_google(base_q, want=max_top)
        buckets = _parse_buckets()[: len(top_links)]

        for i, link in enumerate(top_links):
            if len(detail_links) >= target_total:
                break
            # lấy chi tiết trực tiếp nếu có, nếu không thì đào sâu 1 cấp
            p = urlparse(link)
            if DETAIL_PATTERNS.search(p.path or ""):
                cu = _canon_url(link)
                if cu not in seen_links:
                    seen_links.add(cu)
                    detail_links.append(cu)
            else:
                subs = get_sub_links(link, max_links=buckets[i] if i < len(buckets) else 5)
                for s in subs:
                    cs = _canon_url(s)
                    if cs not in seen_links:
                        seen_links.add(cs)
                        detail_links.append(cs)
                        if len(detail_links) >= target_total:
                            break

    # --- 6) Extract nội dung cho các link đã gom
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
        time.sleep(0.1)  # lịch sự với site

    return results
