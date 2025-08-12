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

REQ_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# ===== Public entry =====
def extract_info_generic(link: str) -> dict:
    """
    Trả về dict: link, title, price, area, description, image, contact, _source.
    Hỗ trợ batdongsan.com.vn & alonhadat.com.vn. Domain khác -> thông báo.
    """
    domain = get_domain(link)
    if not any(d in domain for d in SUPPORTED_DOMAINS):
        return _unsupported(link)

    try:
        # Cho phép tắt Playwright qua biến môi trường
        source = "requests"
        html = ""

        if USE_PLAYWRIGHT:
            try:
                html = fetch_with_playwright(link, domain)
                source = "playwright"
            except Exception:
                # Không cài được Chromium hoặc launch lỗi -> dùng requests
                html = fetch_with_requests(link)
                source = "requests"
        else:
            html = fetch_with_requests(link)
            source = "requests"

        soup = BeautifulSoup(html, "lxml") if _has_lxml() else BeautifulSoup(html, "html.parser")

        # CAPTCHA / Verify page?
        title_text = (soup.title.get_text(strip=True) if soup.title else "").lower()
        if any(x in title_text for x in ("xác minh", "captcha", "verify", "access denied")):
            return extract_from_google_cache(link) | {"_source": "google_cache"}

        if "batdongsan.com.vn" in domain:
            data = parse_batdongsan(link, soup)
        elif "alonhadat.com.vn" in domain:
            data = parse_alonhadat(link, soup)
        else:
            return _unsupported(link)

        # Nếu quá rỗng thì thử Google Cache một lần
        if not data.get("title") and not data.get("price") and not data.get("area"):
            try:
                return extract_from_google_cache(link) | {"_source": "google_cache_fallback"}
            except Exception:
                pass

        data["_source"] = source
        return data

    except Exception as e:
        # Fallback: Google Cache; nếu vẫn lỗi thì trả thông điệp lỗi.
        try:
            return extract_from_google_cache(link) | {"_source": "google_cache_fallback"}
        except Exception:
            return {
                "link": link,
                "title": f"❌ Lỗi khi trích xuất: {e}",
                "price": "",
                "area": "",
                "description": "",
                "image": "",
                "contact": "",
                "_source": "error",
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
    Chờ một số selector để đảm bảo đã render.
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
            page.goto(link, timeout=60000, wait_until="domcontentloaded")

            # Tuỳ domain, chờ thêm các selector phổ biến
            try:
                if "batdongsan.com.vn" in domain:
                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_selector("h1, h1.re__pr-title, meta[property='og:title']", timeout=15000)
                elif "alonhadat.com.vn" in domain:
                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_selector("h1, #limage, meta[property='og:title']", timeout=15000)
            except PWTimeout:
                pass  # vẫn lấy content

            html = page.content()
            return html
        except PWTimeout:
            return fetch_with_requests(link)
        finally:
            context.close()
            browser.close()


def fetch_with_requests(link: str) -> str:
    """Fallback nếu Playwright lỗi/timeout hoặc bị tắt."""
    resp = requests.get(link, timeout=25, headers=REQ_HEADERS)
    # Nếu bị chặn -> dùng cache luôn
    if resp.status_code in (403, 410, 451):
        raise requests.HTTPError(f"Blocked with status {resp.status_code}")
    resp.raise_for_status()
    return resp.text


def extract_from_google_cache(link: str) -> dict:
    # strip=1 + vwsrc=0 cho HTML gọn hơn, ít script
    encoded_url = quote(link, safe="")
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{encoded_url}&strip=1&vwsrc=0"
    resp = requests.get(cache_url, timeout=25, headers=REQ_HEADERS)
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
    - Title: h1.re__pr-title (fallback: h1, og:title)
    - Giá/Diện tích: span.value; hoặc theo label; hoặc regex
    - Mô tả: div.re__section-body (fallback: .re__pr-description / .re__content)
    - Ảnh: ưu tiên og:image, sau đó ảnh chính trong trang (kể cả data-src)
    - Liên hệ: a.re__contact-name (fallback: .re__contact .name, tel:, regex phone)
    """
    if DEBUG_HTML:
        _dump_html(soup, prefix="bds")

    def _txt(el) -> str:
        return el.get_text(" ", strip=True) if el else ""

    # --- Title ---
    title = soup.find("h1", class_="re__pr-title") or soup.select_one("h1")
    title_text = _txt(title)
    if not title_text:
        ogt = soup.find("meta", property="og:title")
        if ogt and ogt.get("content"):
            title_text = ogt["content"].strip()

    # --- Giá & Diện tích ---
    price, area = "", ""

    # 1) cấu trúc cũ
    value_tags = soup.find_all("span", class_="value")
    if value_tags:
        if not price and len(value_tags) > 0:
            price = _txt(value_tags[0])
        if not area and len(value_tags) > 1:
            area = _txt(value_tags[1])

    # 2) cấu trúc mới theo label (VD: “Giá”, “Diện tích”)
    if not price or not area:
        # tìm cặp label-value phổ biến
        for row in soup.select(
            ".re__pr-shortinfo, .re__pr-config, .re__info, .re__pr-specs, .re__list, ul li, .re__box-info"
        ):
            t = _txt(row)
            if not price and re.search(r"\b(Giá|Price)\b", t, re.I):
                # lấy cụm sau 'Giá'
                m = re.search(r"(Giá|Price)\s*[:\-]?\s*([^\s].{0,50}?)($|\s{2,})", t, re.I)
                if m:
                    price = m.group(2).strip()
            if not area:
                m2 = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", t, re.I)
                if m2:
                    area = m2.group(0)

    # 3) regex quét toàn trang
    if not price or not area:
        text_all = soup.get_text(" ", strip=True)
        if not price:
            m = re.search(r"(Giá|Price)\s*[:\-]?\s*([^\s].{0,50}?)\s{2,}", text_all, re.I)
            if m:
                price = m.group(2).strip()
        if not area:
            m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", text_all, re.I)
            if m:
                area = m.group(0)

    # --- Mô tả ---
    desc = (
        soup.find("div", class_="re__section-body")
        or soup.select_one("section .re__section-body, .re__pr-description, .re__content, .re__section-content")
        or soup.select_one("#article, .article, .post-content")
    )
    description = _txt(desc)

    # --- Ảnh ---
    image = ""
    ogimg = soup.find("meta", property="og:image")
    if ogimg and ogimg.get("content"):
        image = ogimg["content"].strip()
    if not image:
        img = (
            soup.select_one("img.pr-img")
            or soup.select_one("img[data-src], img[src*='cloudfront'], img[src$='.jpg'], img[src$='.jpeg']")
        )
        if img:
            src = img.get("src") or img.get("data-src") or ""
            if src:
                image = src.strip()

    # --- Liên hệ ---
    contact_name = ""
    phone = ""

    contact = (
        soup.find("a", class_="re__contact-name")
        or soup.select_one(".re__contact .re__contact-name, .contact .name, .re__contact .name")
        or soup.select_one(".contact .name, .contact-name, .re__contact-name")
    )
    contact_name = _txt(contact)

    phone_tag = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    if phone_tag:
        phone = phone_tag.get_text(strip=True) or phone_tag.get("href", "").replace("tel:", "")
    else:
        # Fallback regex số điện thoại Việt Nam (chấp nhận chấm/cách)
        m = re.search(r"(?:\+?84|0)[\s\.]*(\d[\d\s\.]{8,12}\d)", soup.get_text(" ", strip=True))
        if m:
            phone = re.sub(r"[^\d]+", "", m.group(0))  # lọc chỉ còn số

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

    def _txt(el) -> str:
        return el.get_text(" ", strip=True) if el else ""

    # ----- Tiêu đề -----
    title_el = soup.find("h1") or soup.select_one("h1.title, h1.h1")
    title = _txt(title_el)

    # ----- Giá & Diện tích -----
    price, area = "", ""
    value_tags = soup.find_all("span", class_="value")
    if value_tags:
        price = _txt(value_tags[0]) if len(value_tags) > 0 else ""
        area = _txt(value_tags[1]) if len(value_tags) > 1 else ""

    if not price or not area:
        text_all = soup.get_text(" ", strip=True)
        if not price:
            m = re.search(r"Giá\s*[:\-]?\s*([^\s].{0,40}?)\s{2,}", text_all, re.I)
            if m:
                price = m.group(1).strip()
        if not area:
            m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", text_all, re.I)
            if m:
                area = m.group(0)

    # ----- Mô tả -----
    desc_el = (
        soup.find("div", class_="detail text-content")
        or soup.select_one("div.detail.text-content")
        or soup.select_one("div#content, div.description, div.post-content, .news-content, .content")
    )
    description = _txt(desc_el)

    # ----- Ảnh (chuẩn hoá URL) -----
    image = ""
    img = soup.find("img", id="limage") or soup.select_one("#limage, .gallery img, .images img, img")
    if img and (img.get("src") or img.get("data-src")):
        image = _abs_url(link, img.get("src") or img.get("data-src"))
    else:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image = _abs_url(link, og["content"])

    # ----- Liên hệ -----
    name_el = (soup.find("div", class_="name")
               or soup.select_one(".info-contact .name, .contact .name, .name a, .name span"))
    contact_name = _txt(name_el)
    phone_tag = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    phone = ""
    if phone_tag:
        phone = phone_tag.get_text(strip=True) or phone_tag.get("href", "").replace("tel:", "")
    else:
        m = re.search(r"(?:\+?84|0)[\s\.]*(\d[\d\s\.]{8,12}\d)", soup.get_text(" ", strip=True))
        if m:
            phone = re.sub(r"[^\d]+", "", m.group(0))

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
