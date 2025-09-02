# sites/alonhadat.py
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

def _txt(el): return el.get_text(" ", strip=True) if el else ""

def parse(link: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = _txt(soup.find("h1") or soup.select_one("h1.title, h1.h1"))

    price, area = "", ""
    vals = soup.find_all("span", class_="value")
    if vals:
        price = _txt(vals[0]) if len(vals) > 0 else ""
        area  = _txt(vals[1]) if len(vals) > 1 else ""
    if not price or not area:
        text = soup.get_text(" ", strip=True)
        if not price:
            m = re.search(r"Giá\s*[:\-]?\s*([^\s].{0,40}?)\s{2,}", text, re.I)
            if m: price = m.group(1).strip()
        if not area:
            m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", text, re.I)
            if m: area = m.group(0)

    image = ""
    img = soup.find("img", id="limage") or soup.select_one("#limage, .gallery img, .images img, img")
    if img:
        src = img.get("src") or img.get("data-src")
        if src: image = urljoin(link, src)
    if not image:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"): image = urljoin(link, og["content"])

    contact_name = _txt(soup.select_one(".info-contact .name, .contact .name, .name a, .name span"))
    phone = ""
    tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    if tel: phone = tel.get_text(strip=True) or tel.get("href","").replace("tel:","")

    return {
        "link": link, "title": title, "price": price, "area": area,
        "description": _txt(soup.select_one("div.detail.text-content, #content, .description, .post-content")),
        "image": image,
        "contact": (contact_name + (" - " + phone if phone else "")).strip(" -"),
    }

# gợi ý strategy mặc định cho site này
DEFAULT_STRATEGY = "requests"
