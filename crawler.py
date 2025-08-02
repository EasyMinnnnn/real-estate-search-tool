from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(link, timeout=20000)
            page.wait_for_timeout(3000)
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
    title = soup.find("h1")

    # Tìm thông tin giá và diện tích
    info_items = soup.find_all("div", class_="re__pr-short-info-item")
    price = ""
    area = ""
    for item in info_items:
        label = item.find("span", class_="title")
        value = item.find("span", class_="value")
        if label and value:
            label_text = label.get_text(strip=True)
            if "Mức giá" in label_text:
                price = value.get_text(strip=True)
            elif "Diện tích" in label_text:
                area = value.get_text(strip=True)

    # Mô tả
    description = soup.find("div", class_="re__section-content")

    # Ảnh đại diện (nên dùng og:image thay vì <img>)
    image_tag = soup.find("meta", property="og:image")
    image = image_tag["content"] if image_tag else ""

    # Tên người liên hệ
    contact = soup.find("div", class_="re__contact-name")

    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price,
        "area": area,
        "description": description.text.strip() if description else "",
        "image": image,
        "contact": contact.text.strip() if contact else ""
    }
