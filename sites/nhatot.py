# sites/nhatot.py
from __future__ import annotations
from bs4 import BeautifulSoup
import json, re
from typing import Any, Dict, Optional
import requests

# Tái dùng UA mặc định của project (nếu có)
try:
    from fetchers import REQ_HEADERS as _REQ_HEADERS
except Exception:
    _REQ_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
        "Referer": "https://www.google.com/",
    }

# ===== CSS selector (đã cung cấp) + rút gọn =====
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

# Phone trong nút “Hiện số” (khi có)
_PHONE_BTN_LONG = (
    "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
    "div.c1uglbk9 > div.col-md-4.no-padding.dtView.r1a38bue > div > div:nth-child(2) > "
    "div.d-lg-block.d-none.r4vrt5z > div.LeadButton_wrapperLeadButtonDesktop__7S80M > "
    "div.LeadButton_showPhoneButton__t3T08 > div > div > button > div > span"
)
_PHONE_BTN_SHORT = (
    "div.LeadButton_showPhoneButton__t3T08 button span, "
    "div[class*='LeadButton_showPhoneButton'] button span, "
    "button[class*='showPhone'] span, "
    "a[href^='tel:']"
)

# ✅ Phone dạng che trong phần nội dung (không cần click)
_PHONE_MASK_SEL_LONG = (
    "#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
    "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(4) > "
    "div > div:nth-child(2) > div > div > div"
)
_PHONE_MASK_SEL_SHORT = (
    "div.ct-detail div.col-md-8 div:nth-child(4) div > div:nth-child(2) div div div, "
    "div[class*='adBody'] div div div"
)

# ---------- Helpers ----------
def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""

def _clean_phone(s: str) -> str:
    return re.sub(r"[^\d+]", "", s or "")

def _clean_phone_mask(s: str) -> str:
    """Giữ số, +, khoảng trắng và các ký tự che (* x • ●)."""
    s = s or ""
    s = re.sub(r"[^0-9+*xX•● ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _first(*vals: Optional[str]) -> str:
    for v in vals:
        if v and v.strip():
            return v.strip()
    return ""

def _json_safe(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None

def _search(obj: Any, keys: set[str]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in keys:
                return v
            found = _search(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for it in obj:
            found = _search(it, keys)
            if found is not None:
                return found
    return None

def _extract_list_id(link: str, soup: BeautifulSoup) -> Optional[str]:
    m = re.search(r"/(\d{6,})\.htm", link)
    if m:
        return m.group(1)
    t = soup.get_text(" ", strip=True)
    m2 = re.search(r"(list_id|ad_id|adId)\D+(\d{6,})", t, flags=re.I)
    if m2:
        return m2.group(2)
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd and (obj := _json_safe(nd.string or nd.text or "")):
        v = _search(obj, {"list_id", "ad_id", "adid", "id"})
        if v:
            return str(v)
    return None

def _from_ld_json(soup: BeautifulSoup) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        obj = _json_safe(sc.string or sc.text or "")
        if not obj:
            continue
        for c in (obj if isinstance(obj, list) else [obj]):
            if not isinstance(c, dict):
                continue
            out.setdefault("title", _first(c.get("name"), c.get("headline")))
            out.setdefault("description", _first(c.get("description")))
            offers = c.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price") or c.get("price")
            cur = offers.get("priceCurrency") or c.get("currency")
            if price:
                out.setdefault("price", f"{price} {cur}".strip())
            img = c.get("image")
            if isinstance(img, list):
                img = img[0] if img else ""
            if img:
                out.setdefault("image", img)
    return out

def _from_next_data(soup: BeautifulSoup) -> Dict[str, str]:
    out: Dict[str, str] = {}
    sc = soup.find("script", id="__NEXT_DATA__")
    if not sc:
        return out
    obj = _json_safe(sc.string or sc.text or "")
    if not obj:
        return out
    out["title"] = _first(out.get("title"), str(_search(obj, {"subject", "title", "name", "headline"}) or ""))
    out["description"] = _first(out.get("description"), str(_search(obj, {"body", "description", "content"}) or ""))
    out["price"] = _first(out.get("price"), str(_search(obj, {"price_string", "price"}) or ""))
    out["area"] = _first(out.get("area"), str(_search(obj, {"area", "size", "square"}) or ""))
    images = _search(obj, {"images", "image"})
    img = ""
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            img = first.get("full_path") or first.get("url") or ""
        elif isinstance(first, str):
            img = first
    elif isinstance(images, dict):
        img = images.get("full_path") or images.get("url") or ""
    if img:
        out["image"] = img
    name = _search(obj, {"sellername", "seller_name", "accountname", "name"})
    phone = _search(obj, {"phone", "phonenum", "phone_number"})
    if name:
        out["name"] = str(name)
    if phone:
        out["phone"] = _clean_phone(str(phone))
    return out

def _from_gateway(list_id: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for ver in ("v2", "v1"):
        url = f"https://gateway.chotot.com/{ver}/public/ad-listing/{list_id}"
        try:
            r = requests.get(url, headers=_REQ_HEADERS, timeout=15)
            if r.status_code >= 400:
                continue
            js = r.json()
        except Exception:
            continue
        ad = js.get("ad") or js
        if not isinstance(ad, dict):
            continue
        out["title"] = _first(out.get("title"), ad.get("subject"))
        out["description"] = _first(out.get("description"), ad.get("body"))
        out["price"] = _first(out.get("price"), ad.get("price_string"), str(ad.get("price") or ""))
        area = ad.get("size") or ad.get("square")
        if not area:
            params = ad.get("parameters") or []
            if isinstance(params, list):
                for p in params:
                    if isinstance(p, dict) and str(p.get("key", "")).lower() in {"size", "square", "area"}:
                        area = p.get("value")
                        break
        if area:
            out["area"] = str(area)
        imgs = ad.get("images") or []
        img = ""
        if isinstance(imgs, list) and imgs:
            first = imgs[0]
            if isinstance(first, dict):
                img = first.get("full_path") or first.get("url") or ""
            elif isinstance(first, str):
                img = first
        if img:
            out["image"] = img
        out["name"] = _first(out.get("name"), ad.get("account_name"))
        out["phone"] = _first(out.get("phone"), _clean_phone(ad.get("account_phone", "")))
        break
    return out

# ---- tìm số che: cho phép khoảng trắng giữa chữ số & nhiều ký tự che ----
_MASK_PATTERNS = [
    r"((?:\+?84|0)\s*(?:\d\s*){5,})\s*([*xX•●]{2,})",                # 096367 *** / +84 96 3 ***
    r"(?:SĐT|Điện thoại|Phone)\s*[:\-]?\s*((?:\+?84|0)\s*(?:\d\s*){5,})\s*([*xX•●]{2,})"
]

def _find_masked_phone_text(soup: BeautifulSoup) -> Optional[str]:
    # Ưu tiên vùng selector chỉ định
    for sel in (_PHONE_MASK_SEL_LONG, _PHONE_MASK_SEL_SHORT):
        el = soup.select_one(sel)
        if el:
            t = _clean_phone_mask(_txt(el))
            for pat in _MASK_PATTERNS:
                m = re.search(pat, t)
                if m:
                    digits = re.sub(r"\s+", "", m.group(1))
                    mask = re.sub(r"\s+", "", m.group(2))
                    return f"{digits} {mask}"
    # Nếu không thấy, quét toàn trang
    t_all = _clean_phone_mask(soup.get_text(" ", strip=True))
    for pat in _MASK_PATTERNS:
        m = re.search(pat, t_all)
        if m:
            digits = re.sub(r"\s+", "", m.group(1))
            mask = re.sub(r"\s+", "", m.group(2))
            return f"{digits} {mask}"
    return None

# ================== MAIN PARSER ==================
def parse(link: str, html_or_soup) -> dict:
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    # 1) DOM trực tiếp
    title = _first(_txt(soup.select_one(_TITLE_SEL_LONG)), _txt(soup.select_one(_TITLE_SEL_SHORT)))
    price = _first(_txt(soup.select_one(_PRICE_SEL_LONG)), _txt(soup.select_one(_PRICE_SEL_SHORT)))
    area  = _first(_txt(soup.select_one(_AREA_SEL_LONG)),  _txt(soup.select_one(_AREA_SEL_SHORT)))
    desc  = _first(_txt(soup.select_one(_DESC_SEL_LONG)),  _txt(soup.select_one(_DESC_SEL_SHORT)))

    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = og["content"].strip()
    if not image:
        img = soup.select_one(f"{_IMAGE_SEL_LONG}, {_IMAGE_SEL_SHORT}")
        if img:
            image = (img.get("src") or img.get("data-src") or "").strip()

    # ===== Contact =====
    name = _first(_txt(soup.select_one(_NAME_SEL_LONG)), _txt(soup.select_one(_NAME_SEL_SHORT)))

    # (A) ưu tiên số che ở phần nội dung (không cần click)
    phone = _find_masked_phone_text(soup) or ""

    # (B) nếu chưa có, thử span trong nút/anchor tel:
    if not phone:
        phone = _clean_phone(_first(
            _txt(soup.select_one(_PHONE_BTN_LONG)),
            _txt(soup.select_one(_PHONE_BTN_SHORT))
        ))
    if not phone:
        tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
        if tel:
            phone = _clean_phone(tel.get_text(strip=True) or tel.get("href", "").replace("tel:", ""))

    # (C) fallback regex toàn trang cho số đầy đủ
    if not phone:
        m = re.search(r"(?:\+?84|0)\d{8,11}", soup.get_text(" ", strip=True))
        if m:
            phone = m.group(0)

    # 2) JSON-LD
    jd = _from_ld_json(soup)
    title = _first(title, jd.get("title"))
    price = _first(price, jd.get("price"))
    desc  = _first(desc,  jd.get("description"))
    image = _first(image, jd.get("image"))

    # 3) __NEXT_DATA__
    nd = _from_next_data(soup)
    title = _first(title, nd.get("title"))
    price = _first(price, nd.get("price"))
    area  = _first(area,  nd.get("area"))
    desc  = _first(desc,  nd.get("description"))
    image = _first(image, nd.get("image"))
    name  = _first(name,  nd.get("name"))
    if not phone:
        phone = _first(phone, nd.get("phone"))

    # 4) Gateway nếu thiếu các trường chính
    if not title or not price or not desc or not image:
        list_id = _extract_list_id(link, soup)
        if list_id:
            gd = _from_gateway(list_id)
            title = _first(title, gd.get("title"))
            price = _first(price, gd.get("price"))
            area  = _first(area,  gd.get("area"))
            desc  = _first(desc,  gd.get("description"))
            image = _first(image, gd.get("image"))
            name  = _first(name,  gd.get("name"))
            if not phone:
                phone = _first(phone, gd.get("phone"))

    if not area:
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), re.I)
        if m:
            area = m.group(0)

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

# Next.js → ưu tiên Playwright
DEFAULT_STRATEGY = "playwright"
