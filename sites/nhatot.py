# sites/nhatot.py
from __future__ import annotations
from bs4 import BeautifulSoup
import json, re
from typing import Any, Dict
from .utils_dom import sel, sel1, text_or_empty as _txt

# ===== CSS selector bạn cung cấp + rút gọn =====
_TITLE_SEL_LONG = "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(2) > div > div > div > div.df0dbrp > div.d49myw8 > h1"
_TITLE_SEL_SHORT = "div.pty-container-detail h1, h1"

_PRICE_SEL_LONG = "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(2) > div > div > div > div.plmkxo3 > div.r9vw5if > div > b"
_PRICE_SEL_SHORT = ".plmkxo3 .r9vw5if > div > b, .plmkxo3 b, .price b, .price"

_AREA_SEL_LONG = "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(2) > div > div > div > div.plmkxo3 > div.r9vw5if > div > span.brnpcl3.t19tc1ar > strong"
_AREA_SEL_SHORT = ".plmkxo3 .r9vw5if span.brnpcl3.t19tc1ar strong, .plmkxo3 .r9vw5if strong"

_DESC_SEL_LONG = "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(4) > div > div.d-lg-block.styles_adBodyCollapse__1Xvk7 > div:nth-child(2) > p"
_DESC_SEL_SHORT = ".styles_adBodyCollapse__1Xvk7 p, .adBody p, .adBody, .ct-detail p"

_IMAGE_SEL_LONG = "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(1) > div > div.sbxypvz > div.i12je7dy > span > img"
_IMAGE_SEL_SHORT = ".i12je7dy img, .sbxypvz img, img[data-src], img[src$='.jpg'], img[src$='.jpeg']"

_NAME_SEL_LONG = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
                  "div.c1uglbk9 > div.col-md-4.no-padding.dtView.r1a38bue > div > div:nth-child(2) "
                  "> div.d-lg-block.d-none.r4vrt5z > div.SellerInfo_profileWrapper__eRBjV."
                  "SellerInfo_profileWrapperPty___7nQ_ > div.SellerInfo_sellerWrapper__r4S9i "
                  "> div.SellerInfo_nameBounder__Nzf1W > a > div > div.SellerInfo_flexDiv___8piT")
_NAME_SEL_SHORT = "[class*='SellerInfo_nameBounder'] a [class*='SellerInfo_flexDiv'], [class*='SellerInfo'] a"

_PHONE_SEL_LONG = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
                   "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(4) > "
                   "div > div:nth-child(2) > div > div > a")
_PHONE_SEL_SHORT = "a[href^='tel:'], [class*='phone'] a, .js__phone a, .phone a"

def _clean_phone(s: str) -> str:
    s = s or ""
    return re.sub(r"[^\d+]", "", s)

def _first_nonempty(*vals: str) -> str:
    for v in vals:
        if v and v.strip():
            return v.strip()
    return ""

def _json_parse_safe(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None

def _search_dict(obj: Any, keys: set[str]) -> Any:
    """Tìm đệ quy key trong dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in keys:
                return v
            found = _search_dict(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for it in obj:
            found = _search_dict(it, keys)
            if found is not None:
                return found
    return None

def _from_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        obj = _json_parse_safe(sc.string or sc.text or "")
        if not obj:
            continue
        # obj có thể là list hoặc dict
        candidates = obj if isinstance(obj, list) else [obj]
        for c in candidates:
            if not isinstance(c, dict):
                continue
            typ = str(c.get("@type", "")).lower()
            if typ in ("product", "offer", "apartment", "house", "place", "realestateagent", "newsarticle", "article", "webpage"):
                data.setdefault("title", _first_nonempty(c.get("name", ""), c.get("headline", "")))
                data.setdefault("description", _first_nonempty(c.get("description", "")))
                # price
                offers = c.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("price") or c.get("price")
                currency = offers.get("priceCurrency") or c.get("currency")
                if price:
                    data.setdefault("price", f"{price} {currency}".strip())
                # image
                img = c.get("image")
                if isinstance(img, list):
                    img = img[0] if img else ""
                if img:
                    data.setdefault("image", img)
    return data

def _from_next_data(soup: BeautifulSoup) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    sc = soup.find("script", id="__NEXT_DATA__")
    if not sc:
        return data
    obj = _json_parse_safe(sc.string or sc.text or "")
    if not obj:
        return data

    # Tìm các field phổ biến
    title = _search_dict(obj, {"subject", "title", "name", "headline"})
    desc  = _search_dict(obj, {"body", "description", "content"})
    price = _search_dict(obj, {"price_string", "price"})
    area  = _search_dict(obj, {"area", "size", "square"})
    # ảnh
    images = _search_dict(obj, {"images", "image"})
    img = ""
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            img = first.get("full_path") or first.get("url") or ""
        elif isinstance(first, str):
            img = first
    elif isinstance(images, dict):
        img = images.get("full_path") or images.get("url") or ""

    # người bán
    seller = _search_dict(obj, {"sellername", "seller_name", "accountname", "name"})
    phone  = _search_dict(obj, {"phone", "phonenum", "phone_number"})

    if title: data["title"] = str(title)
    if desc:  data["description"] = str(desc)
    if price: data["price"] = str(price)
    if area:  data["area"] = str(area)
    if img:   data["image"] = str(img)
    if seller: data["name"] = str(seller)
    if phone:  data["phone"] = _clean_phone(str(phone))
    return data

def parse(link: str, html_or_soup) -> dict:
    # Nhận HTML string hoặc BeautifulSoup
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    # ----- 1) CSS trực tiếp -----
    title = _txt(sel1(soup, f"{_TITLE_SEL_LONG}, {_TITLE_SEL_SHORT}"))
    price = _txt(sel1(soup, f"{_PRICE_SEL_LONG}, {_PRICE_SEL_SHORT}"))
    area  = _txt(sel1(soup, f"{_AREA_SEL_LONG}, {_AREA_SEL_SHORT}"))
    desc  = _txt(sel1(soup, f"{_DESC_SEL_LONG}, {_DESC_SEL_SHORT}"))

    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = og["content"].strip()
    if not image:
        img = sel1(soup, f"{_IMAGE_SEL_LONG}, {_IMAGE_SEL_SHORT}")
        if img:
            image = (img.get("src") or img.get("data-src") or "").strip()

    # Contact qua CSS
    name  = _txt(sel1(soup, f"{_NAME_SEL_LONG}, {_NAME_SEL_SHORT}"))
    phone = _clean_phone(_txt(sel1(soup, f"{_PHONE_SEL_LONG}, {_PHONE_SEL_SHORT}")))
    if not phone:
        tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
        if tel:
            phone = _clean_phone(tel.get_text(strip=True) or tel.get("href","").replace("tel:",""))

    # ----- 2) JSON-LD -----
    jd = _from_json_ld(soup)
    title = _first_nonempty(title, jd.get("title",""))
    price = _first_nonempty(price, jd.get("price",""))
    desc  = _first_nonempty(desc,  jd.get("description",""))
    image = _first_nonempty(image, jd.get("image",""))

    # ----- 3) __NEXT_DATA__ -----
    nd = _from_next_data(soup)
    title = _first_nonempty(title, nd.get("title",""))
    price = _first_nonempty(price, nd.get("price",""))
    area  = _first_nonempty(area,  nd.get("area",""))
    desc  = _first_nonempty(desc,  nd.get("description",""))
    image = _first_nonempty(image, nd.get("image",""))
    name  = _first_nonempty(name,  nd.get("name",""))
    phone = _first_nonempty(phone, nd.get("phone",""))

    # Fallback dò area từ toàn trang
    if not area:
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), re.I)
        if m: area = m.group(0)

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

# Trang này là Next.js, nên ưu tiên Playwright
DEFAULT_STRATEGY = "playwright"
