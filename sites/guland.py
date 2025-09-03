# sites/guland.py
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

# ===== Selectors (bản dài theo yêu cầu + rút gọn fallback) =====
_TITLE_LONG = ("body > div.sdb-picker-site > div.sdb-content-picker > div > div:nth-child(1) "
               "> div.dtl-row-wrp > div.dtl-col-lft > div.dtl-col-lft__wrp > div > div.dtl-main > h1")
_TITLE_SHORT = ".dtl-main h1, h1"

_PRICE_LONG = ("body > div.sdb-picker-site > div.sdb-content-picker > div > div:nth-child(1) "
               "> div.dtl-row-wrp > div.dtl-col-lft > div.dtl-col-lft__wrp > div > div.dtl-main "
               "> div.row.row-dtl-sub > div > div > div > div.dtl-prc__sgl.dtl-prc__ttl")
_PRICE_SHORT = ".dtl-prc__ttl, .price, [class*='prc']"

_AREA_LONG = ("body > div.sdb-picker-site > div.sdb-content-picker > div > div:nth-child(1) "
              "> div.dtl-row-wrp > div.dtl-col-lft > div.dtl-col-lft__wrp > div > div.dtl-main "
              "> div.row.row-dtl-sub > div > div > div > div.dtl-prc__sgl.dtl-prc__dtc")
_AREA_SHORT = ".dtl-prc__dtc, .area, [class*='dtc']"

_DESC_LONG = ("body > div.sdb-picker-site > div.sdb-content-picker > div > div:nth-child(1) "
              "> div.dtl-row-wrp > div.dtl-col-lft > div.dtl-inf.dtl-stn > div > div.dtl-inf__dsr")
_DESC_SHORT = ".dtl-inf__dsr, .dtl-inf, [class*='description'], .post-content"

_IMG_LONG = ("#SlickSlider-DetailView > div > div > div.detail-media__full.slick-slide.slick-current.slick-active "
             "> div > div > div > img")
_IMG_SHORT = "#SlickSlider-DetailView img, .detail-media__full img, .detail-media img, img"

_NAME_LONG = ("body > div.sdb-picker-site > div.sdb-content-picker > div > div:nth-child(1) "
              "> div.dtl-row-wrp > div.dtl-col-rgt > div.dtl-aut.dtl-crd > div > a > div.dtl-aut__cxt > h5")
_NAME_SHORT = ".dtl-aut__cxt h5, .dtl-aut h5, [class*='author'] h5, [class*='seller'] h5"

def parse(link: str, html_or_soup) -> dict:
    """Parser guland.vn post detail -> dict"""
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    # Title / Price / Area / Description
    title = _first(_txt(soup.select_one(_TITLE_LONG)), _txt(soup.select_one(_TITLE_SHORT)))
    price = _first(_txt(soup.select_one(_PRICE_LONG)), _txt(soup.select_one(_PRICE_SHORT)))
    area  = _first(_txt(soup.select_one(_AREA_LONG)),  _txt(soup.select_one(_AREA_SHORT)))

    if not area:
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), flags=re.I)
        if m:
            area = m.group(0)

    desc = _first(_txt(soup.select_one(_DESC_LONG)), _txt(soup.select_one(_DESC_SHORT)))

    # Image (prefer og:image, then slider, then any jpg)
    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = urljoin(link, og["content"].strip())
    if not image:
        img = soup.select_one(_IMG_LONG) or soup.select_one(_IMG_SHORT)
        if img:
            image = urljoin(link, (img.get("src") or img.get("data-src") or "").strip())

    # Contact (name only by spec; try phone if present anywhere)
    name  = _first(_txt(soup.select_one(_NAME_LONG)), _txt(soup.select_one(_NAME_SHORT)))
    phone = ""
    tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
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

# Trang SPA/Next-like → ưu tiên dùng Playwright cho chắc
DEFAULT_STRATEGY = "playwright"
