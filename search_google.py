import os
import re
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from crawler import extract_info_generic  # sửa import

API_KEY = os.getenv("GOOGLE_API_KEY")
CX = os.getenv("GOOGLE_CX")

def get_top_links(query, num_links=5):
    if not API_KEY or not CX:
        raise RuntimeError("Thiếu GOOGLE_API_KEY hoặc GOOGLE_CX trong biến môi trường")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": API_KEY, "cx": CX, "q": query, "num": num_links}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return [item["link"] for item in data.get("items", [])]

def get_sub_links(link, max_links=3):
    """Lấy link con cùng domain, sâu hơn, có pattern id tin (prxxxx, *.htm/*.html số)."""
    try:
        resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        base = urlparse(link)
        base_domain, base_path = base.netloc, base.path.rstrip("/")
        subs = []
        for a in soup.find_all("a", href=True):
            full = urljoin(link, a["href"])
            p = urlparse(full)
            if (p.netloc == base_domain and p.path.startswith(base_path)
                and p.path != base_path and full not in subs and (
                    "pr" in p.path or re.search(r"\d{6,}\.(htm|html)$", p.path)
                )):
                subs.append(full)
                if len(subs) >= max_links:
                    break
        return subs
    except Exception:
        return []

def search_google(query, target_total=30):
    """
    Trả về danh sách dict tin rao (title, price, area, description, image, contact, link).
    target_total=30 để đủ 3 lần bấm (10 tin/lần).
    """
    top_links = get_top_links(query, num_links=5)
    # Phân bổ 30 link con qua 5 domain: [8,8,6,4,4]
    buckets = [8, 8, 6, 4, 4]
    results = []
    for i, link in enumerate(top_links[:5]):
        for sub in get_sub_links(link, max_links=buckets[i]):
            info = extract_info_generic(sub)
            if info: results.append(info)
            if len(results) >= target_total:
                return results
    return results
