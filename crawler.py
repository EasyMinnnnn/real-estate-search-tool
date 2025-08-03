from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    if "batdongsan.com.vn" not in domain and "alonhadat.com.vn" not in domain:
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
        browser = p.chromium.launch(headless=True)  # Đổi thành False nếu muốn quan sát trình duyệt
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            page.goto(link, timeout=30000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(5000)  # Tăng thời gian chờ JS render

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            if "batdongsan.com.vn" in domain:
                return parse_batdongsan(link, soup)
            elif "alonhadat.com.vn" in domain:
                print("📄 DOM alonhadat preview:")
                print(html[:2000])  # In 2000 ký tự đầu HTML để debug nếu cần
                return parse_alonhadat(link, soup)

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
    image = soup.find("img", class_="pr-img")

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

def parse_alonhadat(link, soup):
    # Tiêu đề
    title = soup.find("h1")

    # Giá và diện tích (2 span.value liên tiếp)
    value_tags = soup.find_all("span", class_="value")
    price = value_tags[0].text.strip() if len(value_tags) > 0 else ""
    area = value_tags[1].text.strip() if len(value_tags) > 1 else ""

    # Mô tả
    description = soup.find("div", class_="detail text-content")

    # Hình ảnh đại diện
    image = soup.find("img", id="limage")

    # Người liên hệ + SĐT nếu có
    contact_name = soup.find("div", class_="name")
    contact_phone_tag = soup.find("a", href=lambda href: href and href.startswith("tel:"))
    contact_phone = contact_phone_tag.text.strip() if contact_phone_tag else ""

    contact_full = ""
    if contact_name:
        contact_full += contact_name.text.strip()
    if contact_phone:
        contact_full += f" - {contact_phone}"

    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price,
        "area": area,
        "description": description.get_text(separator="\n").strip() if description else "",
        "image": image["src"] if image and image.has_attr("src") else "",
        "contact": contact_full.strip()
    }
