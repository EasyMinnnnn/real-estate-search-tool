from __future__ import annotations

import os
import re
from urllib.parse import urlparse, quote, urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ===== Config =====
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "1") != "0"
USE_PLAYWRIGHT = os.getenv("USE_PLAYWRIGHT", "1") != "0"
DEBUG_HTML = os.getenv("DEBUG_HTML", "0") == "1"
ALONHADAT_STORAGE = os.getenv("ALONHADAT_STORAGE", "auth_alonhadat.json")

SUPPORTED_DOMAINS = ("batdongsan.com.vn", "alonhadat.com.vn")


# ===== Public entry =====
def extract_info_generic(link: str) -> dict:
    """
    Trả về dict: link, title, price, area, description, image, contact.
    Hỗ trợ batdongsan.com.vn & alonhadat.com.vn. Domain khác -> thông báo.
    """
    domain = get_domain(link)

    if not any(d in domain for d in SUPPORTED_DOMAINS):
        return _unsupported(link)

    try:
        # Cho phép tắt Playwright qua biến môi trường
        if USE_PLAYWRIGHT:
            html = fetch_with_playwright(link, domain)
        else:
            html = fetch_with_requests(link)

        soup = BeautifulSoup(html, "lxml") if _has_lxml() else BeautifulSoup(html, "html.parser")

        # CAPTCHA / Verify page?
        title_text = (soup.title.get_text(strip=True) if soup.title else "").lower()
        if any(x in title_text for x in ("xác minh", "captcha", "verify")):
            return extract_from_google_cache(link)

        if "batdongsan.com.vn" in domain:
            return parse_batdongsan(link, soup)
        elif "alonhadat.com.vn" in domain:
            return parse_alonhadat(link, soup)

        return _unsupported(link)

    except Exception as e:
        # Fallback: Google Cache; nếu vẫn lỗi thì trả thông điệp lỗi.
        try:
            return extract_from_google_cache(link)
        except Exception:
            return {
                "link": link,
                "title": f"❌ Lỗi khi trích xuất: {e}",
                "price": "",
                "area": "",
                "description": "",
                "image": "",
                "contact": "",
            }


# ===== Internals =====
def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except Exception:
        return False


def fetch_with_playwright(link: str, domain: str) -> str:
    """
    Tải HTML bằng Playwright. Nếu có file lưu session cho alonhadat thì dùng.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context_kwargs = {
            "user_agent": USER_AGENT,
            "viewport": {"width": 1366, "height": 900},
        }
        # Dùng storage_state cho alonhadat nếu có (đã pass CAPTCHA)
        if "alonhadat.com.vn" in domain and os.path.exists(ALONHADAT_STORAGE):
            context_kwargs["storage_state"] = ALONHADAT_STORAGE

        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            page.goto(link, timeout=50000, wait_until="domcontentloaded")
            # chờ mạng rảnh + một chút để JS render
            page.wait_for_load_state("networkidle", timeout=25000)
            page.wait_for_timeout(5000)
            html = page.content()
            return html
        except PWTimeout:
            return fetch_with_requests(link)
        finally:
            context.close()
            browser.close()


def fetch_with_requests(link: str) -> str:
    """Fallback nếu Playwright lỗi/timeout hoặc bị tắt."""
    resp = requests.get(link, timeout=25, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def extract_from_google_cache(link: str) -> dict:
    encoded_url = quote(link, safe="")
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{encoded_url}"
    resp = requests.get(cache_url, timeout=25, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml") if _has_lxml() else BeautifulSoup(resp.text, "html.parser")

    if "batdongsan.com.vn" in link:
        return parse_batdongsan(link, soup)
    if "alonhadat.com.vn" in link:
        return parse_alonhadat(link, soup)
    return _unsupported(link)


def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


# ===== Parsers =====
def parse_batdongsan(link: str, soup: BeautifulSoup) -> dict:
    """
    BĐS thường có:
    - Title: h1.re__pr-title
    - Giá/Diện tích: span.value (thứ tự 0: giá, 1: DT)
    - Mô tả: div.re__section-body
    - Ảnh: img.pr-img
    - Liên hệ: a.re__contact-name
    + Fallback selector/regex nếu thay đổi cấu trúc.
    """
    if DEBUG_HTML:
        _dump_html(soup, prefix="bds")

    # --- Title ---
    title = soup.find("h1", class_="re__pr-title") or soup.select_one("h1")
    title_text = title.get_text(strip=True) if title else ""

    # --- Giá & Diện tích ---
    price, area = "", ""
    value_tags = soup.find_all("span", class_="value")
    if value_tags:
        price = value_tags[0].get_text(" ", strip=True) if len(value_tags) > 0 else ""
        area = value_tags[1].get_text(" ", strip=True) if len(value_tags) > 1 else ""
    if not price or not area:
        # fallback quét theo label
        text_all = soup.get_text(" ", strip=True)
        if not price:
            m = re.search(r"(Giá|Price)\s*[:\-]?\s*([^\s].{0,40}?)\s{2,}", text_all, re.I)
            if m:
                price = m.group(2).strip()
        if not area:
            m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", text_all, re.I)
            if m:
                area = m.group(0)

    # --- Mô tả ---
    desc = (soup.find("div", class_="re__section-body")
            or soup.select_one("section .re__section-body, .re__pr-description, .re__content"))
    description = desc.get_text("\n", strip=True) if desc else ""

    # --- Ảnh ---
    img = (soup.find("img", class_="pr-img")
           or soup.select_one("img[src*='cloudfront'], img[src*='.jpg'], img[src*='.jpeg']"))
    image = img["src"].strip() if img and img.has_attr("src") else ""

    # --- Liên hệ ---
    contact = (soup.find("a", class_="re__contact-name")
               or soup.select_one(".re__contact .re__contact-name, .contact .name, a[href^='tel:']"))
    contact_name = contact.get_text(strip=True) if contact else ""
    phone_tag = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    phone = phone_tag.get_text(strip=True) if phone_tag else ""

    contact_full = contact_name
    if phone:
        contact_full = (contact_full + " - " + phone).strip(" -")

    return {
        "link": link,
        "title": title_text,
        "price": price,
        "area": area,
        "description": description,
        "image": image,
        "contact": contact_full,
    }


def parse_alonhadat(link: str, soup: BeautifulSoup) -> dict:
    """
    alonhadat.com.vn:
    - Title: <h1>
    - Giá & Diện tích: <span class="value"> (2 cái đầu), có fallback label/regex
    - Mô tả: <div class="detail text-content"> (fallback id=content / .description / .post-content)
    - Ảnh: <img id="limage"> hoặc og:image; chuẩn hoá URL bằng urljoin
    - Liên hệ: <div class="name"> và <a href="tel:..."> (regex fallback số ĐT)
    """
    if DEBUG_HTML:
        _dump_html(soup, prefix="alnd")

    # ----- Tiêu đề -----
    title_el = soup.find("h1") or soup.select_one("h1.title, h1.h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # ----- Giá & Diện tích -----
    price, area = "", ""
    value_tags = soup.find_all("span", class_="value")
    if value_tags:
        price = value_tags[0].get_text(" ", strip=True) if len(value_tags) > 0 else ""
        area = value_tags[1].get_text(" ", strip=True) if len(value_tags) > 1 else ""

    if not price or not area:
        text_all = soup.get_text(" ", strip=True)
        if not price:
            # bắt cụm sau "Giá" ngắn gọn
            m = re.search(r"Giá\s*[:\-]?\s*([^\s].{0,40}?)\s{2,}", text_all, re.I)
            if m:
                price = m.group(1).strip()
        if not area:
            # diện tích kiểu "180 m2", "180 m²"
            m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", text_all, re.I)
            if m:
                area = m.group(0)

    # ----- Mô tả -----
    desc_el = (soup.find("div", class_="detail text-content")
               or soup.select_one("div.detail.text-content")
               or soup.select_one("div#content, div.description, div.post-content, .news-content, .content"))
    description = desc_el.get_text("\n", strip=True) if desc_el else ""

    # ----- Ảnh (chuẩn hoá URL) -----
    image = ""
    img = soup.find("img", id="limage") or soup.select_one("#limage, .gallery img, .images img, img")
    if img and img.has_attr("src"):
        image = _abs_url(link, img["src"])
    else:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image = _abs_url(link, og["content"])

    # ----- Liên hệ -----
    name_el = (soup.find("div", class_="name")
               or soup.select_one(".info-contact .name, .contact .name, .name a, .name span"))
    contact_name = name_el.get_text(strip=True) if name_el else ""
    phone_tag = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    phone = ""
    if phone_tag:
        phone = phone_tag.get_text(strip=True) or phone_tag.get("href", "").replace("tel:", "")
    else:
        # Fallback regex số điện thoại Việt Nam
        m = re.search(r"(0\d{9,10})", soup.get_text(" ", strip=True))
        if m:
            phone = m.group(1)

    contact_full = contact_name
    if phone:
        contact_full = (contact_full + " - " + phone).strip(" -")

    return {
        "link": link,
        "title": title,
        "price": price,
        "area": area,
        "description": description,
        "image": image,
        "contact": contact_full,
    }


# ===== Helpers =====
def _abs_url(base: str, src: str) -> str:
    try:
        if not src:
            return ""
        return urljoin(base, src)
    except Exception:
        return src or ""


def _dump_html(soup: BeautifulSoup, prefix: str) -> None:
    """Ghi HTML ra file để debug (bật với DEBUG_HTML=1)."""
    try:
        path = f"/tmp/{prefix}_debug.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print(f"[DEBUG] Saved HTML -> {path}")
    except Exception as e:
        print(f"[DEBUG] Save HTML failed: {e}")


def _unsupported(link: str) -> dict:
    return {
        "link": link,
        "title": "❓ Không hỗ trợ domain này",
        "price": "",
        "area": "",
        "description": "",
        "image": "",
        "contact": "",
    }


# Giữ tương thích với code cũ (nếu nơi khác import theo tên này)
extract_info_batdongsan = extract_info_generic
