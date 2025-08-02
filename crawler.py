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
    # Tiêu đề bài đăng
    title_tag = soup.find("h1", class_="re__pr-title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Mức giá và diện tích là 2 thẻ <span class="value"> liên tiếp
    value_spans = soup.find_all("span", class_="value")
    price = value_spans[0].get_text(strip=True) if len(value_spans) > 0 else ""
    area = value_spans[1].get_text(strip=True) if len(value_spans) > 1 else ""

    # Mô tả nằm trong thẻ <div> có nhiều class
    desc_div = soup.find("div", class_="re__section-body re__detail-content js__section-body js__pr-description js__tracking")
    description = desc_div.get_text(separator="\n", strip=True) if desc_div else ""

    # Hình ảnh đầu tiên (lấy ảnh đại diện đầu nếu có)
    image = ""
    img_tag = soup.find("img")
    if img_tag and img_tag.has_attr("src"):
        image = img_tag["src"]

    # Tên người liên hệ
    contact_tag = soup.find("a", class_="re__contact-name")
    contact = contact_tag.get_text(strip=True) if contact_tag else ""

    return {
        "link": link,
        "title": title,
        "price": price,
        "area": area,
        "description": description,
        "image": image,
        "contact": contact
    }

