# search_aggregator.py
import os, time, re, requests
from urllib.parse import urlparse
from sites import pick_site
from fetchers import get_html

# ... (hàm gọi Google CSE giống file cũ của bạn) ...

DETAIL_PATTERNS = re.compile(r"(?:-pr\d+|-\d{6,}\.(?:htm|html)$|/tin-\d+)", re.I)

def extract_one(link: str) -> dict:
    picked = pick_site(link)
    if not picked:
        return {"link": link, "title": "❓Không hỗ trợ domain", "price": "", "area": "",
                "description": "", "image": "", "contact": ""}

    parser, default_strategy = picked
    strategy = os.getenv("FORCE_STRATEGY", "") or default_strategy
    try:
        html = get_html(link, strategy)
        data = parser(link, html)
        data["_source"] = strategy
        return data
    except Exception as e:
        return {"link": link, "title": f"❌ Lỗi khi trích xuất: {e}",
                "price": "", "area": "", "description": "", "image": "", "contact": ""}

def crawl_detail_links(query: str, target_total: int = 30) -> list[str]:
    # giữ nguyên thuật toán ưu tiên batdongsan -> alonhadat từ code cũ của bạn
    # (dựa vào Custom Search API + siteSearch + pattern DETAIL_PATTERNS)
    ...
