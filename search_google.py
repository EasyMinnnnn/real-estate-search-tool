import os
import re
import time
from urllib.parse import urlparse, urlunparse

import requests
from crawler import extract_info_generic

# --------- HTTP defaults ----------
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
REQ_TIMEOUT = 15

# ====== Patterns ======
# CHỈ nhận link chi tiết (tránh danh mục)
DETAIL_PATTERNS = re.compile(
    r"(?:-pr\d+|-\d{6,}\.(?:htm|html)$|/tin-\d+)",
    re.IGNORECASE,
)


# ---------- Utils ----------
def _get_env():
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        raise RuntimeError("Thiếu GOOGLE_API_KEY hoặc GOOGLE_CX trong biến môi trường")
    return api_key, cx


def _canon_url(s: str) -> str:
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


def _call_google(query: str, want: int, extra: dict | None = None) -> list[str]:
    """
    Gọi Google CSE API (tự phân trang, num<=10/trang).
    extra: dict tham số bổ sung (siteSearch, siteSearchFilter, etc.)
    """
    api_key, cx = _get_env()
    url = "https://www.googleapis.com/customsearch/v1"
    want = max(1, int(want))
    start = 1
    page_size = 10
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

        r = requests.get(url, params=params, timeout=REQ_TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        data = r.json()
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
            if cu in seen:
                continue
            seen.add(cu)
            out.append(cu)

        start += page_size
        if start > 91:  # an toàn
            break

    return out[:want]


# ====== Lấy trực tiếp LINK CHI TIẾT theo domain (NHANH) ======
def _cse_detail_links_for_domain(query: str, domain: str, need: int, already: set[str]) -> list[str]:
    """
    Ưu tiên link chi tiết của 1 domain (không fetch HTML).
    Dùng siteSearch + inurl để bắt pattern chi tiết.
    """
    need = max(0, need)
    if need == 0:
        return []

    # Các biến thể truy vấn để tăng xác suất ra trang chi tiết
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


# ====== Main search (NHANH & ƯU TIÊN BDS) ======
def search_google(query: str, target_total: int = 30) -> list[dict]:
    """
    Trả về list dict tin rao: title, price, area, description, image, contact, link.
    Chiến lược:
    1) Ưu tiên kéo link chi tiết từ batdongsan.com.vn (siteSearch, inurl filters).
    2) Bổ sung từ alonhadat.com.vn theo cách tương tự.
    3) Nếu còn thiếu, lấy từ kết quả chung nhưng CHỈ nhận link chi tiết.
    -> Không fetch HTML của trang danh mục (để tăng tốc & tránh 403).
    """
    target_total = int(target_total or 30)
    want_first_batch = min(10, target_total)  # bạn cần 10 tin đầu
    results: list[dict] = []
    detail_links: list[str] = []
    seen: set[str] = set()

    # 1) Ưu tiên batdongsan
    bds_needed = want_first_batch
    bds_links = _cse_detail_links_for_domain(query, "batdongsan.com.vn", bds_needed, seen)
    for u in bds_links:
        if u not in seen:
            seen.add(u)
            detail_links.append(u)

    # 2) Bổ sung alonhadat (nếu chưa đủ 10)
    if len(detail_links) < want_first_batch:
        need = want_first_batch - len(detail_links)
        alnd_links = _cse_detail_links_for_domain(query, "alonhadat.com.vn", need, seen)
        for u in alnd_links:
            if u not in seen:
                seen.add(u)
                detail_links.append(u)

    # 3) Nếu vẫn thiếu cho tổng target_total thì lấy thêm bất kỳ domain (chỉ link chi tiết)
    if len(detail_links) < target_total:
        # gọi CSE general nhưng chỉ nhận link chi tiết
        extra_links = _call_google(query, want=target_total * 2)  # gọi rộng rồi lọc
        for u in extra_links:
            if u in seen:
                continue
            path = urlparse(u).path or ""
            if DETAIL_PATTERNS.search(path):
                cu = _canon_url(u)
                if cu not in seen:
                    seen.add(cu)
                    detail_links.append(cu)
                    if len(detail_links) >= target_total:
                        break

    # 4) Extract nội dung cho các link đã gom
    for u in detail_links[:target_total]:
        try:
            info = extract_info_generic(u)
        except Exception as e:
            info = {
                "link": u,
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
