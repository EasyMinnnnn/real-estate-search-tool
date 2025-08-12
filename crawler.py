from __future__ import annotations

import os
from urllib.parse import urlparse, quote

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ===== Config =====
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "1") != "0"
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
        html = fetch_with_playwright(link, domain)
        soup = BeautifulSoup(html, "html.parser")

        # CAPTCHA / Verify page?
        title_text = (soup.title.get_text(strip=True) if soup.title else "").lower()
        if "xác minh" in title_text or "verify" in title_text or "captcha" in title_text:
            # cố Google cache
            return extract_from_google_cache(link)

        if "batdongsan.com.vn" in domain:
            return parse_batdongsan(link, soup)
        elif "alonhadat.com.vn" in domain:
            return parse_alonhadat(link, soup)

        # Phòng xa
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
            page.wait_for_timeout(1500)  # thả nhẹ JS
            html = page.content()
            return html
        except PWTimeout:
            # Hết kiên nhẫn -> thử requests fallback
            return fetch_with_requests(link)
        finally:
            context.close()
            browser.close()


def fetch_with_requests(link: str) -> str:
    """Fallback nhẹ nhàng nếu Playwright lỗi/timeout."""
    resp = requests.get(link, timeout=15, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def extract_from_google_cache(link: str) -> dict:
    encoded_url = quote(link, safe="")
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{encoded_url}"

    resp = requests.get(cache_url, timeout=15, headers={"User-Agent": USER_AGENT})
    if resp.status_code != 200:
        raise RuntimeError(f"Google Cache trả về mã lỗi {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

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


def parse_alonhadat(link: str, soup: BeautifulSoup) -> dict:
    """
    Alonhadat thường có:
    - Title: h1
    - Giá/DT: span.value
    - Mô tả: div.detail.text-content
    - Ảnh: img#limage
    - Liên hệ: div.name + thẻ <a href="tel:...">
    """
    title = soup.find("h1")
    value_tags = soup.find_all("span", class_="value")
    price = value_tags[0].get_text(strip=True) if len(value_tags) > 0 else ""
    area = value_tags[1].get_text(strip=True) if len(value_tags) > 1 else ""
    description = soup.find("div", class_="detail text-content")
    image = soup.find("img", id="limage")
    contact_name = soup.find("div", class_="name")
    contact_phone_tag = soup.find("a", href=lambda href: href and str(href).startswith("tel:"))
    contact_phone = contact_phone_tag.get_text(strip=True) if contact_phone_tag else ""

    contact_full = (contact_name.get_text(strip=True) if contact_name else "").strip()
    if contact_phone:
        contact_full = (contact_full + " - " + contact_phone).strip(" -")

    return {
        "link": link,
        "title": title.get_text(strip=True) if title else "",
        "price": price,
        "area": area,
        "description": description.get_text(separator="\n").strip() if description else "",
        "image": image["src"] if image and image.has_attr("src") else "",
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
