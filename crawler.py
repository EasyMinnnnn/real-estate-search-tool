from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    if "batdongsan.com.vn" not in domain:
        return {
            "link": link,
            "title": "❓ Không hỗ trợ domain này",
            "price": "",
            "area": "",
            "description": "",
            "image": "",
            "contact": ""
        }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ))
        page = context.new_page()

        try:
            page.goto(link, timeout=30000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)  # đợi JS render

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            return parse_batdongsan(link, soup)

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
    title = soup.find("h1", class_="re__pr-title")
    price_tag = soup.find_all("span", class_="value")
    description = soup.find("div", class_="re__section-body")
    contact = soup.find("a", class_="re__contact-name")
    image = soup.find("img")

    # Gán theo thứ tự nếu có nhiều thẻ <span class="value">
    price = price_tag[0].text.strip() if len(price_tag) > 0 else ""
    area = price_tag[1].text.strip() if len(price_tag) > 1 else ""

    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price,
        "area": area,
        "description": description.get_text(separator="\n").strip() if description else "",
        "image": image["src"] if image and image.has_attr("src") else "",
        "contact": contact.text.strip() if contact else ""
    }
