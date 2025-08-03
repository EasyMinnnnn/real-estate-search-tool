from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(link, timeout=30000)
            page.wait_for_selector("h1.re__pr-title", timeout=10000)
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
    from urllib.parse import urlparse
    return urlparse(url).netloc.lower()

def parse_batdongsan(link, soup):
    title = soup.find("h1", class_="re__pr-title")
    price = soup.find("span", class_="value")
    area = price.find_next("span", class_="value") if price else None
    description = soup.find("div", class_="re__section-body re__detail-content js__section-body js__pr-description js__tracking")
    contact = soup.find("a", class_="re__contact-name")
    image_tag = soup.find("img", class_="pr-img")
    image = image_tag["src"] if image_tag and image_tag.has_attr("src") else ""

    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area.text.strip() if area else "",
        "description": description.get_text(separator="\n").strip() if description else "",
        "image": image,
        "contact": contact.text.strip() if contact else ""
    }
