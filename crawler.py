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
ALONHADAT_STORAGE = os.getenv("ALONHADAT_STORAGE", "auth_alonhadat.json")

SUPPORTED_DOMAINS = ("batdongsan.com.vn", "alonhadat.com.vn")


def extract_info_generic(link: str) -> dict:
    """
    Trả về dict gồm: link, title, price, area, description, image, contact.
    Hỗ trợ batdongsan.com.vn và alonhadat.com.vn. Domain khác trả về thông báo.
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

        # Ưu tiên parser lxml nếu có, rơi về html.parser khi thiếu
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
        # Fallback: thử Google Cache; nếu vẫn lỗi thì trả thông điệp lỗi.
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
            "viewport": {"width": 1280, "height": 900},
        }

        # Dùng storage_state cho alonhadat nếu có (đã tick CAPTCHA trước đó)
        if "alonhadat.com.vn" in domain and os.path.exists(ALONHADAT_STORAGE):
            context_kwargs["storage_state"] = ALONHADAT_STORAGE

        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        try:
            page.goto(link, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(1200)
            html = page.content()
            return html
        except PWTimeout:
            return fetch_with_requests(link)
        finally:
            context.close()
            browser.close()


def fetch_with_requests(link: str) -> str:
    """Fallback nhẹ nhàng nếu Playwright lỗi/timeout hoặc bị tắt."""
    resp = requests.get(link, timeout=20, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def extract_from_google_cache(link: str) -> dict:
    encoded_url = quote(link, safe="")
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{encoded_url}"

    resp = requests.get(cache_url, timeout=20, headers={"User-Agent": USER_AGENT})
    if resp.status_code != 200:
        raise RuntimeError(f"Google Cache trả về mã lỗi {resp.status_code}")

    soup = BeautifulSoup(resp.text, "lxml") if _has_lxml() else BeautifulSoup(resp.text, "html.parser")

    if "batdongsan.com.vn" in link:
        return parse_batdongsan(link, soup)
    if "alonhadat.com.vn" in link:
        return parse_alonhadat(link, soup)
    return _unsupported(link)


def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def parse_batdongsan(link: str, soup: BeautifulSoup) -> dict:
    """
    BĐS thường có:
    - Title: h1.re__pr-title
    - Giá/Diện tích: span.value (thứ tự 0: giá, 1: DT)
    - Mô tả: div.re__section-body
    - Ảnh: img.pr-img
    - Liên hệ: a.re__contact-name
    """
    title = soup.find("h1", class_="re__pr-title")
    price_tag = soup.find_all("span", class_="value")
    description = soup.find("div", class_="re__section-body")
    contact = soup.find("a", class_="re__contact-name")
    image = soup.find("img", class_="pr-img")

    price = price_tag[0].get_text(strip=True) if len(price_tag) > 0 else ""
    area = price_tag[1].get_text(strip=True) if len(price_tag) > 1 else ""

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": price,
        "area": area,
        "description": description.get_text(separator="\n").strip() if description else "",
        "image": image["src"] if image and image.has_attr("src") else "",
        "contact": contact.get_text(strip=True) if contact else "",
    }


# ------- Alonhadat helpers -------
def _abs_url(base: str, src: str) -> str:
    try:
        if not src:
            return ""
        return urljoin(base, src)
    except Exception:
        return src or ""


def parse_alonhadat(link: str, soup: BeautifulSoup) -> dict:
    """
    Trích xuất chi tiết từ trang alonhadat.com.vn
    - Tiêu đề: <h1>
    - Giá/DT: <span class="value"> (thường 2 phần tử đầu)
    - Mô tả: <div class="detail text-content">
    - Ảnh: <img id="limage"> (URL tương đối -> chuẩn hoá tuyệt đối)
    - Liên hệ: <div class="name"> + <a href="tel:..."> (fallback regex)
    """
    # ----- Tiêu đề -----
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # ----- Giá & Diện tích -----
    value_tags = soup.find_all("span", class_="value")
    price = value_tags[0].get_text(" ", strip=True) if len(value_tags) > 0 else ""
    area = value_tags[1].get_text(" ", strip=True) if len(value_tags) > 1 else ""

    # Fallback nếu không tìm thấy theo span.value
    if not price:
        lbl = soup.find(string=re.compile(r"\bGiá\b", re.I))
        if lbl and getattr(lbl, "parent", None):
            nxt = lbl.parent.find_next(string=True)
            if nxt:
                price = str(nxt).strip()
    if not area:
        m = re.search(r"(\d[\d\.,]*)\s*m(?:2|²)\b", soup.get_text(" ", strip=True), re.I)
        if m:
            area = m.group(0).replace("  ", " ")

    # ----- Mô tả -----
    desc_el = soup.find("div", class_="detail text-content") or soup.select_one("div.detail.text-content")
    if not desc_el:
        desc_el = soup.select_one("div#content, div.description, div.post-content")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""

    # ----- Ảnh -----
    img = soup.find("img", id="limage")
    image = ""
    if img and img.has_attr("src"):
        image = _abs_url(link, img["src"])
    else:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image = _abs_url(link, og["content"])
        else:
            any_img = soup.select_one("div.images img, .image img, img")
            if any_img and any_img.has_attr("src"):
                image = _abs_url(link, any_img["src"])

    # ----- Liên hệ -----
    name_el = soup.find("div", class_="name") or soup.select_one(".info-contact .name, .name a, .name span")
    contact_name = name_el.get_text(strip=True) if name_el else ""
    phone_tag = soup.find("a", href=lambda h: h and str(h).startswith("tel:"))
    phone = ""
    if phone_tag:
        phone = phone_tag.get_text(strip=True) or phone_tag.get("href", "").replace("tel:", "")
    else:
        # Fallback regex số điện thoại trong toàn trang
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
