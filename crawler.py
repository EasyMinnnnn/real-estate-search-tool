from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(link, timeout=20000)
            page.wait_for_selector("h1.re__pr-title", timeout=10000)
            html = page.inner_html("body")
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
    from urllib.parse import urlparse
    return urlparse(url).netloc.lower()

def parse_batdongsan(link, soup):
    title = soup.find("h1", class_="re__pr-title")
    values = soup.find_all("span", class_="value")
    price = values[0] if len(values) > 0 else None
    area = values[1] if len(values) > 1 else None
    description = soup.find("div", class_="re__detail-content")
    image = soup.find("img")
    contact = soup.find("a", class_="re__contact-name")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area.text.strip() if area else "",
        "description": description.text.strip() if description else "",
        "image": image["src"] if image and image.has_attr("src") else "",
        "contact": contact.text.strip() if contact else ""
    }
