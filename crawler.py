from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(link, timeout=30000)
            page.wait_for_load_state("domcontentloaded")  # Chờ DOM tải xong
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            if "batdongsan.com.vn" in domain:
                return parse_batdongsan(link, soup)
            else:
                return {
                    "link": link,
                    "title": "❓ Không hỗ trợ domain này",
                    "price": "",
                    "area": "",
                    "description": "",
                    "image": "",
                    "contact": ""
                }
        except Exception as e:
            return {
                "link": link,
                "title": f"⚠️ Lỗi: {str(e)}",
                "price": "",
                "area": "",
                "description": "",
                "image": "",
                "contact": ""
            }
        finally:
            browser.close()

def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()

def parse_batdongsan(link, soup):
    title = soup.select_one("h1.re__pr-title")
    price = soup.select_one("span.value")
    area = soup.select("span.value")
    description = soup.select_one("div.re__detail-content")
    contact = soup.select_one("a.re__contact-name")
    image = soup.select_one("img.pr-img")

    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area[1].text.strip() if len(area) > 1 else "",
        "description": description.text.strip() if description else "",
        "image": image["src"] if image and image.has_attr("src") else "",
        "contact": contact.text.strip() if contact else ""
    }
