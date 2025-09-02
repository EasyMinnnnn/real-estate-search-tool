# sites/batdongsan.py
from bs4 import BeautifulSoup
import re
from .utils_dom import sel, sel1, text_or_empty as _txt

def parse(link: str, html_or_soup) -> dict:
    # Chấp nhận cả string HTML hoặc đối tượng BeautifulSoup
    soup = html_or_soup if hasattr(html_or_soup, "select") else BeautifulSoup(html_or_soup, "lxml")

    root = sel1(soup, "#product-detail-web")

    # ===== Title =====
    title = ""
    if root:
        # dùng sel1 để tự bỏ combinator '>' ở đầu nếu có
        title = _txt(sel1(root, "> h1"))
    if not title:
        title = _txt(soup.find("h1", class_="re__pr-title") or sel1(soup, "h1"))
        if not title:
            og = soup.find("meta", property="og:title")
            if og and og.get("content"):
                title = og["content"].strip()

    # ===== Price & Area =====
    price, area = "", ""
    if root:
        short = sel1(root, "div.re__pr-short-info, .re__pr-short-info.entrypoint-v1.js__pr-short-info")
        if short:
            p = sel1(short, "> div:nth-child(1) span.value")
            a = sel1(short, "> div:nth-child(2) span.value")
            price = _txt(p) or price
            area  = _txt(a) or area

    if not price or not area:
        # Fallback theo label/regex để chống đổi layout
        for row in sel(soup, ".re__pr-shortinfo, .re__pr-config, .re__info, .re__pr-specs, .re__list, ul li, .re__box-info"):
            t = _txt(row)
            if not price and re.search(r"\b(Giá|Price)\b", t, re.I):
                m = re.search(r"(Giá|Price)\s*[:\-]?\s*([^\s].{0,50}?)($|\s{2,})", t, re.I)
                if m:
                    price = m.group(2).strip()
            if not area:
                m2 = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", t, re.I)
                if m2:
                    area = m2.group(0)

    # ===== Description =====
    desc = ""
    if root:
        desc = _txt(sel1(root, ".re__section.re__pr-description.js__section.js__li-description > div"))
    if not desc:
        desc = _txt(sel1(soup, ".re__section-body, .re__pr-description, .re__content, .re__section-content, #article, .article, .post-content"))

    # ===== Image =====
    image = ""
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image = og["content"].strip()
    if not image:
        img = sel1(soup, "img.pr-img, img[data-src], img[src*='cloudfront'], img[src$='.jpg'], img[src$='.jpeg']")
        if img:
            image = (img.get("src") or img.get("data-src") or "").strip()

    # ===== Contact =====
    name = _txt(sel1(soup, "div.re__main-sidebar .re__agent-infor.re__agent-name > a"))
    phone = ""
    tel = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    if tel:
        phone = tel.get_text(strip=True) or tel.get("href", "").replace("tel:", "")

    return {
        "link": link,
        "title": title,
        "price": price,
        "area": area,
        "description": desc,
        "image": image,
        "contact": (name + (" - " + phone if phone else "")).strip(" -"),
    }

# Với site này thường gặp 403 → ưu tiên playwright
DEFAULT_STRATEGY = "playwright"
