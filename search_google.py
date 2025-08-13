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

# ===== Heuristic nhận diện link chi tiết =====
# Trang chi tiết của batdongsan thường có -pr<id> hoặc -<id>.html hoặc /tin-<id>
DETAIL_PATTERNS = re.compile(
    r"(?:-pr\d+|-\d{6,}\.(?:htm|html)$|/tin-\d+)",
    re.IGNORECASE,
)

# (dùng khi phải đào sâu trang danh mục)
LIST_PATTERNS = re.compile(
    r"(?:/ban-|/mua-ban-|/nha-dat|/tim-kiem|/search|/listing|/danh-sach|/bat-dong-san)",
    re.IGNORECASE,
)

# ---------- ENV & utils ----------
def _get_env():
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


def _parse_whitelist() -> list[str]:
    """
    Lấy SITE_WHITELIST từ env thành list có thứ tự, ưu tiên batdongsan đứng trước.
    Ví dụ: "batdongsan.com.vn, alonhadat.com.vn"
    """
    raw = os.getenv("SITE_WHITELIST", "").strip()
    if not raw:
        return []
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
            "num": take,         # luôn <=10 để không bị 400
            "start": start,      # phân trang: 1,11,21...
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


# ---------- Lấy link CHI TIẾT cho 1 domain (ưu tiên batdongsan) ----------
def _detail_links_for_domain(query: str, domain: str, need: int, already: set[str]) -> list[str]:
    """
    Lấy trực tiếp link CHI TIẾT từ Google CSE cho 1 domain:
    - Dùng siteSearch + inurl để bắt pattern trang chi tiết (không fetch HTML danh mục).
    - Tốc độ nhanh, tránh bị chặn từ batdongsan.
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
            if DETAIL_PATTERNS.search((urlparse(u).path or "")):
                cu = _canon_url(u)
                if cu not in already and cu not in found:
                    found.append(cu)
                    if len(found) >= need:
                        break
    return found[:need]


# ---------- Lấy sublink cho alonhadat (quét trang danh mục) ----------
def _sub_links_alonhadat(link: str, soup: BeautifulSoup, max_links: int) -> list[str]:
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
    - Nếu link chi tiết: trả luôn link đó (tránh fetch).
    - Nếu alonhadat: quét trang danh mục (HTML) → lấy link chi tiết.
    - Domain khác: nếu fetch được, gom link chi tiết theo pattern.
    """
    p0 = urlparse(link)
    domain = (p0.netloc or "").lower()
    path0 = p0.path or "/"

    if DETAIL_PATTERNS.search(path0):
        return [_canon_url(link)]

    # alonhadat: cần HTML để gỡ link chi tiết
    if "alonhadat.com.vn" in domain:
        try:
            r = requests.get(link, headers={"User-Agent": UA}, timeout=REQ_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            return _sub_links_alonhadat(link, soup, max_links)
        except Exception:
            return []

    # Domain khác: nếu fetch được, gom link chi tiết theo pattern
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


# ---------- search_google (ưu tiên batdongsan, nhanh & ổn định) ----------
def search_google(query: str, target_total: int = 30) -> list:
    """
    Trả về list dict tin rao: title, price, area, description, image, contact, link.
    Chiến lược nhanh:
      1) Ưu tiên batdongsan.com.vn → kéo link CHI TIẾT trực tiếp (CSE siteSearch + inurl).
      2) Bổ sung từ các domain khác trong SITE_WHITELIST (alonhadat…).
      3) Nếu vẫn thiếu: gọi CSE chung & lọc CHI TIẾT; cuối cùng mới đào sâu danh mục (có thể chậm).
    """
    target_total = int(target_total or 30)
    first_batch = min(10, target_total)  # 10 tin đầu
    results: list[dict] = []
    detail_links: list[str] = []
    seen_links: set[str] = set()

    # --- 1) Ưu tiên batdongsan ---
    need_bds = first_batch
    bds_links = _detail_links_for_domain(query, "batdongsan.com.vn", need_bds, seen_links)
    for u in bds_links:
        if u not in seen_links:
            seen_links.add(u)
            detail_links.append(u)

    # --- 2) Bổ sung alonhadat & các domain whitelist khác ---
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

    # --- 3) Nếu vẫn thiếu cho tổng target_total: mở rộng tìm kiếm ---
    if len(detail_links) < target_total:
        # ưu tiên whitelist thêm 1 lượt nữa
        wl2 = _parse_whitelist() or ["batdongsan.com.vn", "alonhadat.com.vn"]
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

        # nếu vẫn thiếu → gọi CSE chung (không giới hạn domain) và lọc trang chi tiết
        if len(detail_links) < target_total:
            extra_links = _call_google(query, want=target_total * 2)
            for u in extra_links:
                if u in seen_links:
                    continue
                if DETAIL_PATTERNS.search((urlparse(u).path or "")):
                    cu = _canon_url(u)
                    seen_links.add(cu)
                    detail_links.append(cu)
                    if len(detail_links) >= target_total:
                        break

    # --- 4) Cuối cùng, nếu vẫn thiếu → đào sâu trang danh mục (có thể chậm) ---
    if len(detail_links) < target_total:
        max_top = int(os.getenv("MAX_TOP_LINKS", "5") or "5")
        top_links = _call_google(query, want=max_top)
        # gom sublinks theo pattern
        for link in top_links:
            if len(detail_links) >= target_total:
                break
            if DETAIL_PATTERNS.search((urlparse(link).path or "")):
                cu = _canon_url(link)
                if cu not in seen_links:
                    seen_links.add(cu)
                    detail_links.append(cu)
            else:
                subs = get_sub_links(link, max_links=5)
                for s in subs:
                    cs = _canon_url(s)
                    if cs not in seen_links:
                        seen_links.add(cs)
                        detail_links.append(cs)
                        if len(detail_links) >= target_total:
                            break

    # --- 5) Trích xuất nội dung cho các link đã gom ---
    for link in detail_links[:target_total]:
        try:
            info = extract_info_generic(link)
        except Exception as e:
            info = {
                "link": link,
                "title": f"❌ Lỗi khi trích xuất: {e}",
                "price": "",
                "area": "",
                "description": "",
                "image": "",
                "contact": "",
            }
        results.append(info)
        # giảm delay để tăng tốc (0.1s), vẫn "lịch sự"
        time.sleep(0.1)

    return results
