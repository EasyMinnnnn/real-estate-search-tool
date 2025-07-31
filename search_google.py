import os
import requests
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
    try:
        resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        sub_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/ban-nha" in href and href.startswith("https://batdongsan.com.vn") and len(sub_links) < max_links:
                sub_links.append(href)
        return sub_links
    except:
        return []

def search_google(query):
    distribution = [3, 3, 2, 1, 1]  # Tổng 10 link con
    top_links = get_top_links(query)
    result_links = []

    for idx, link in enumerate(top_links):
        sub_links = get_sub_links(link, max_links=distribution[idx])
        for sub in sub_links:
            info = extract_info_batdongsan(sub)
            result_links.append(info)

    return result_links
