# sites/muaban.py
from __future__ import annotations
from bs4 import BeautifulSoup
import re
from typing import Optional

def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""

def _clean_phone_digits(s: str) -> str:
    """Chỉ giữ ký tự số và + (cho trường hợp đã hiện số)."""
    return re.sub(r"[^\d+]", "", s or "")

def _clean_phone_mask(s: str) -> str:
    """Giữ số, khoảng trắng và ký tự che (* x • ●) khi chưa bấm 'Hiện số'."""
    s = s or ""
    s = re.sub(r"[^0-9+*xX•● ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ====== Selectors (bản dài theo yêu cầu + rút gọn fallback) ======
_TITLE_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div.sc-6orc5o-0.hCKpzV > div.sc-6orc5o-1.eheBnp > div.sc-6orc5o-8.bzqDYr > h1"
_TITLE_SHORT = "div.sc-6orc5o-8 h1, h1"

_PRICE_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div.sc-6orc5o-0.hCKpzV > div.sc-6orc5o-1.eheBnp > div.sc-6orc5o-8.bzqDYr > div.price"
_PRICE_SHORT = "div.sc-6orc5o-8 .price, .price"

_AREA_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div.sc-6orc5o-0.hCKpzV > div.sc-6orc5o-1.eheBnp > div.sc-6orc5o-14.dtPffK > div.sc-6orc5o-15.hRtXrD > ul > li.sc-6orc5o-17.gCgqPV > span:nth-child(2) > a.link"
_AREA_SHORT = "div.sc-6orc5o-14 div.sc-6orc5o-15 ul li span:nth-child(2) a.link, [class*='area']"

_DESC_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div.sc-6orc5o-0.hCKpzV > div.sc-6orc5o-1.eheBnp > div.sc-6orc5o-9.khOhZD > div"
_DESC_SHORT = "div.sc-6orc5o-9 div, div.sc-6orc5o-9, [class*='description']"

_IMG_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div.sc-6orc5o-0.hCKpzV > div.sc-6orc5o-2.ihYfKH > div.slick-slider.slick-initialized > div > div > div > div > div > img"
_IMG_SHORT = "div.slick-slider img, img[data-lazy], img[data-src], img[src$='.jpg'], img[src$='.jpeg']"

_NAME_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div:nth-child(2) > div > div.sc-lohvv8-1.kavwNJ > div.sc-lohvv8-2.ficBQz > p > span.title"
_NAME_SHORT = "div.sc-lohvv8-2 p span.title, [class*='Seller'], [class*='Contact'] [class*='title']"

# Phone:
# - nút 'Hiện số' nằm trong span.phone-hidden > span.show-phone
# - sau khi click, số sẽ xuất hiện ngay trong span.phone-hidden
_PHONE_BOX_LONG = "#__next > div.sc-ed7dq4-0.fPSoZc > div.sc-11qpg5t-0.sc-ed7dq4-1.hblyZv.WWhVi > div.sc-6orc5o-0.hCKpzV > div.sc-6orc5o-1.eheBnp > div.sc-6orc5o-9.khOhZD > div > div > span.phone-hidden"
_PHONE_BOX_SHORT = "span.phone-hidden, .phone-hidden"

def _first(*vals: Optional[str]) -> str:
    for v in vals:
        if v and v.strip():
            return v.strip()
    return ""

def parse(link: str, html_or_soup) -> dict:
    """Parse trang muaban.net → dict(title, price, area, description, image, contact)."""
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    # --- Title / Price / Area / Description ---
    title = _first(_txt(soup.select_one(_TITLE_LONG)), _txt(soup.select_one(_TITLE_SHORT)))

    price = _first(_txt(soup.select_one(_PRICE_LONG)), _txt(soup.select_one(_PRICE_SHORT)))

    area = _first(_txt(soup.select_one(_AREA_LONG)), _txt(soup.select_one(_AREA_SHORT)))
    if not area:
        # Fallback regex tìm "xx m2" / "xx m²"
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), re.I)
        if m:
            area = m.group(0)

    desc = _first(_txt(soup.select_one(_DESC_LONG)), _txt(soup.select_one(_DESC_SHORT)))

    # --- Image ---
    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = og["content"].strip()
    if not image:
        img = soup.select_one(f"{_IMG_LONG}, {_IMG_SHORT}")
        if img:
            image = (img.get("src") or img.get("data-lazy") or img.get("data-src") or "").strip()

    # --- Contact ---
    name = _first(_txt(soup.select_one(_NAME_LONG)), _txt(soup.select_one(_NAME_SHORT)))

    phone = ""
    # Ưu tiên vùng phone-hidden: sau khi click 'Hiện số' thì text ở đây là số; nếu chưa click thì có thể là dạng che
    box = soup.select_one(_PHONE_BOX_LONG) or soup.select_one(_PHONE_BOX_SHORT)
    if box:
        raw = _txt(box)
        # Nếu đã hiện số: lấy số sạch
        digits = _clean_phone_digits(raw)
        if digits and len(digits) >= 9:
            phone = digits
        else:
            # Chưa hiện số: giữ dạng che (096xxx ***) nếu có
            masked = _clean_phone_mask(raw)
            if ("*" in masked or "x" in masked.lower() or "•" in masked or "●" in masked) and any(ch.isdigit() for ch in masked):
                phone = masked

    # Fallback: anchor tel:
    if not phone:
        tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
        if tel:
            phone = _clean_phone_digits(tel.get_text(strip=True) or tel.get("href", "").replace("tel:", ""))

    # Fallback cuối: regex số VN
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

# Trang động → ưu tiên playwright (nếu dùng chế độ auto)
DEFAULT_STRATEGY = "playwright"
