# sites/i_batdongsan.py
from __future__ import annotations
from bs4 import BeautifulSoup
import re
from typing import Optional
from urllib.parse import urljoin

def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""

def _first(*vals: Optional[str]) -> str:
    for v in vals:
        if v and v.strip():
            return v.strip()
    return ""

def _clean_phone(s: str) -> str:
    return re.sub(r"[^\d+]", "", s or "").strip()

# ===== Selectors (theo yêu cầu + rút gọn) =====
_TITLE_LONG = "#left > div.property > div.title > h1"
_TITLE_SHORT = "div.property .title h1, h1"

_PRICE_LONG = "#left > div.property > div.moreinfor1 > div.infor > table > tbody > tr:nth-child(7) > td.price"
_AREA_LONG  = "#left > div.property > div.moreinfor1 > div.infor > table > tbody > tr:nth-child(7) > td:nth-child(2)"
# Fallback: tìm theo label trong bảng thông tin
_INFO_TABLE  = "#left > div.property > div.moreinfor1 > div.infor table, .moreinfor1 .infor table"

_DESC_LONG = "#left > div.property > div.detail.text-content"
_DESC_SHORT = "div.property .detail.text-content, .property .detail, .text-content"

# i-batdongsan đôi khi có 2 thẻ cùng id #limage; có thể là <img> hoặc wrapper
_IMG_PREFS  = "#limage, img#limage, #limage img"
_IMG_SHORT  = "img[src$='.jpg'], img[src$='.jpeg'], img[data-src$='.jpg'], img[data-src$='.jpeg'], .property img"

_NAME_LONG  = "#left > div.property > div.contact > div.contact-info > div.content > div.name"
_NAME_SHORT = ".property .contact .contact-info .content .name, .contact .name"

_PHONE_LONG  = "#left > div.property > div.contact > div.contact-info > div.content > div.fone > a"
_PHONE_SHORT = ".property .contact .contact-info .content .fone a, a[href^='tel:']"

def parse(link: str, html_or_soup) -> dict:
    """Parser i-batdongsan.com"""
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    # ---- Title
    title = _first(_txt(soup.select_one(_TITLE_LONG)), _txt(soup.select_one(_TITLE_SHORT)))

    # ---- Price & Area
    price = _txt(soup.select_one(_PRICE_LONG))
    area  = _txt(soup.select_one(_AREA_LONG))

    if not (price and area):
        # Fallback quét theo label trong bảng
        tbl = soup.select_one(_INFO_TABLE)
        if tbl:
            for tr in tbl.select("tr"):
                t = _txt(tr)
                if not price and re.search(r"\b(Giá|Price)\b", t, re.I):
                    m = re.search(r"(Giá|Price)\s*[:\-]?\s*([^\s].{0,60}?)($|\s{2,})", t, re.I)
                    if m:
                        price = m.group(2).strip()
                if not area and re.search(r"(Diện tích|Area)", t, re.I):
                    m2 = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", t, re.I)
                    if m2:
                        area = m2.group(0)

    if not area:
        # bắt theo regex toàn trang
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), re.I)
        if m:
            area = m.group(0)

    # ---- Description
    desc = _first(_txt(soup.select_one(_DESC_LONG)), _txt(soup.select_one(_DESC_SHORT)))

    # ---- Image (robust + absolute URL)
    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = urljoin(link, og["content"].strip())

    if not image:
        # Duyệt tất cả biến thể #limage (trang có thể lặp id)
        for el in soup.select(_IMG_PREFS):
            img_el = el
            if el.name != "img":
                img_el = el.select_one("img") or el
            src = (img_el.get("src") or img_el.get("data-src") or img_el.get("data-original") or "").strip()
            if src:
                image = urljoin(link, src)
                break

    if not image:
        img2 = soup.select_one(_IMG_SHORT)
        if img2:
            image = urljoin(link, (img2.get("src") or img2.get("data-src") or img2.get("data-original") or "").strip())

    # ---- Contact
    name  = _first(_txt(soup.select_one(_NAME_LONG)), _txt(soup.select_one(_NAME_SHORT)))
    phone = ""
    tel = soup.select_one(_PHONE_LONG) or soup.select_one(_PHONE_SHORT)
    if tel:
        phone = _clean_phone(tel.get_text(strip=True) or tel.get("href", "").replace("tel:", ""))
    if not phone:
        m = re.search(r"(?:\+?84|0)\d{8,11}", soup.get_text(" ", strip=True))
        if m:
            phone = m.group(0)

    contact = (name + (" - " + phone if phone else "")).strip(" -")

    return {
        "link": link,
        "title": title,
        "price": price,
        "area": area,
        "description": desc,
        "image": image,
        "contact": contact,
    }

# Site này thường render tĩnh, ưu tiên requests
DEFAULT_STRATEGY = "requests"
