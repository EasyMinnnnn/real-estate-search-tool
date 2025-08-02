import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

def extract_info_generic(link):
    domain = urlparse(link).netloc

    if "batdongsan.com.vn" in domain:
        return extract_info_batdongsan(link)
    elif "nhatot.com" in domain:
        return extract_info_nhatot(link)
    elif "alonhadat.com.vn" in domain:
        return extract_info_alonhadat(link)
    elif "guland.vn" in domain:
        return extract_info_guland(link)
    elif "muaban.net" in domain:
        return extract_info_muaban(link)
    elif "rever.vn" in domain:
        return extract_info_rever(link)
    elif "i-nhadat.com" in domain or "i-batdongsan.com" in domain:
        return extract_info_ibds(link)
    else:
        return {
            "link": link,
            "title": "❓ Không hỗ trợ domain này",
            "price": "",
            "area": "",
            "description": "",
            "image": "",
            "contact": ""
        }

def fetch_soup(link):
    try:
        resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None

def extract_info_batdongsan(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.find("h1") or soup.title
    price = soup.find(text=re.compile(r"Giá")).find_next() if soup.find(text=re.compile(r"Giá")) else ""
    area = soup.find(text=re.compile(r"Diện tích")).find_next() if soup.find(text=re.compile(r"Diện tích")) else ""
    desc = soup.find("div", {"class": re.compile("section-content|description")})
    img = soup.find("img", src=re.compile(r"https.*\.jpg"))
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": price.get_text(strip=True) if price else "",
        "area": area.get_text(strip=True) if area else "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": img["src"] if img else "",
        "contact": phone.strip() if phone else "",
    }

def extract_info_nhatot(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.find("h1") or soup.title
    price = soup.find(text=re.compile(r"(Giá|₫)")).find_next() if soup.find(text=re.compile(r"(Giá|₫)")) else ""
    area = soup.find(text=re.compile(r"m2|m²"))
    desc = soup.find("div", {"class": re.compile("section-content|description")})
    img = soup.find("img", src=re.compile(r"https.*\.jpg"))
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": price.get_text(strip=True) if price else "",
        "area": area.strip() if area else "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": img["src"] if img else "",
        "contact": phone.strip() if phone else "",
    }

def extract_info_alonhadat(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.find("h1") or soup.title
    price = soup.find("span", class_="price")
    area = soup.find(text=re.compile(r"m2|m²"))
    desc = soup.find("div", {"class": "short-desc"})
    img = soup.find("img", src=re.compile(r"https.*\.jpg"))
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": price.get_text(strip=True) if price else "",
        "area": area.strip() if area else "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": img["src"] if img else "",
        "contact": phone.strip() if phone else "",
    }

def extract_info_guland(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.title
    desc = soup.find("div", class_=re.compile("description"))
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": "",
        "area": "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": "",
        "contact": phone.strip() if phone else "",
    }

def extract_info_muaban(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.find("h1") or soup.title
    price = soup.find(text=re.compile(r"(Giá|₫)"))
    area = soup.find(text=re.compile(r"m2|m²"))
    desc = soup.find("div", {"class": re.compile("description|content")})
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": price.strip() if price else "",
        "area": area.strip() if area else "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": "",
        "contact": phone.strip() if phone else "",
    }

def extract_info_rever(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.title
    desc = soup.find("div", class_=re.compile("description"))
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": "",
        "area": "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": "",
        "contact": phone.strip() if phone else "",
    }

def extract_info_ibds(link):
    soup = fetch_soup(link)
    if not soup:
        return {"link": link, "title": "❌ Không load được trang"}

    title = soup.title
    desc = soup.find("div", class_=re.compile("description|content"))
    phone = soup.find(text=re.compile(r"0\d{9,10}"))

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": "",
        "area": "",
        "description": desc.get_text(strip=True) if desc else "",
        "image": "",
        "contact": phone.strip() if phone else "",
    }
