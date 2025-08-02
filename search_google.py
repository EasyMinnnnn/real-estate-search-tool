import os
import re
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from crawler import extract_info_batdongsan

API_KEY = os.getenv("GOOGLE_API_KEY")
CX = os.getenv("GOOGLE_CX")

def get_top_links(query, num_links=5):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CX,
        "q": query,
        "num": num_links
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    return [item["link"] for item in data.get("items", [])]

def get_sub_links(link, max_links=3):
    """Lấy link con từ cùng domain, có path sâu hơn, chứa ID tin (prxxxxx, .htm, .html)"""
    try:
        resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        base_domain = urlparse(link).netloc
        base_path = urlparse(link).path.rstrip("/")

        sub_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(link, href)
            parsed = urlparse(full_url)

            if (
                parsed.netloc == base_domain
                and parsed.path.startswith(base_path)
                and parsed.path != base_path
                and full_url not in sub_links
                and (
                    "pr" in parsed.path or
                    re.search(r"\d{6,}\.htm", parsed.path) or
                    re.search(r"\d{6,}\.html", parsed.path)
                )
            ):
                sub_links.append(full_url)

            if len(sub_links) >= max_links:
                break

        return sub_links

    except Exception as e:
        print(f"⚠️ Error get_sub_links({link}): {e}")
        return []

def search_google(query):
    distribution = [3, 3, 2, 1, 1]  # Tổng 10 link con
    top_links = get_top_links(query)
    result_links = []

    for idx, link in enumerate(top_links):
        if idx >= len(distribution):
            break
        sub_links = get_sub_links(link, max_links=distribution[idx])
        for sub in sub_links:
            info = extract_info_batdongsan(sub)
            if info:
                result_links.append(info)

    return result_links
