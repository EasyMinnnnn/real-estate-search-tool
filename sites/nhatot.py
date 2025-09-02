# sites/nhatot.py
from bs4 import BeautifulSoup
import re
from .utils_dom import sel, sel1, text_or_empty as _txt

# ===== CSS selectors bạn cung cấp + fallback ngắn gọn =====
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

def parse(link: str, html_or_soup) -> dict:
    # Nhận HTML string hoặc BeautifulSoup
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    # ----- Title / Price / Area -----
    title = _txt(sel1(soup, f"{_TITLE_SEL_LONG}, {_TITLE_SEL_SHORT}"))
    price = _txt(sel1(soup, f"{_PRICE_SEL_LONG}, {_PRICE_SEL_SHORT}"))
    area  = _txt(sel1(soup, f"{_AREA_SEL_LONG}, {_AREA_SEL_SHORT}"))
    if not area:
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), re.I)
        if m: area = m.group(0)

    # ----- Description -----
    desc = _txt(sel1(soup, f"{_DESC_SEL_LONG}, {_DESC_SEL_SHORT}"))

    # ----- Image -----
    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = og["content"].strip()
    if not image:
        img = sel1(soup, f"{_IMAGE_SEL_LONG}, {_IMAGE_SEL_SHORT}")
        if img:
            image = (img.get("src") or img.get("data-src") or "").strip()

    # ----- Contact -----
    name = _txt(sel1(soup, f"{_NAME_SEL_LONG}, {_NAME_SEL_SHORT}"))
    phone = _clean_phone(_txt(sel1(soup, f"{_PHONE_SEL_LONG}, {_PHONE_SEL_SHORT}")))
    if not phone:
        tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
        if tel:
            phone = _clean_phone(tel.get_text(strip=True) or tel.get("href", "").replace("tel:", ""))

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

# Nên dùng Playwright cho trang Next.js động
DEFAULT_STRATEGY = "playwright"
