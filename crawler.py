from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def extract_info_generic(link: str) -> dict:
    domain = get_domain(link)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(link, timeout=20000)
            page.wait_for_timeout(2000)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            if "batdongsan.com.vn" in domain:
                return parse_batdongsan(link, soup)
            elif "nhatot.com" in domain:
                return parse_nhatot(link, soup)
            elif "alonhadat.com.vn" in domain:
                return parse_alonhadat(link, soup)
            elif "guland.vn" in domain:
                return parse_guland(link, soup)
            elif "i-nhadat.com" in domain:
                return parse_inhadat(link, soup)
            elif "i-batdongsan.com" in domain:
                return parse_ibatdongsan(link, soup)
            elif "muaban.net" in domain:
                return parse_muaban(link, soup)
            elif "rever.vn" in domain:
                return parse_rever(link, soup)
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

# --- Template parsers ---

def parse_batdongsan(link, soup):
    title = soup.find("h1")
    price = soup.find("div", class_="re__price")
    area = soup.find("div", class_="re__area")
    description = soup.find("div", class_="re__section-content")
    image = soup.find("img")
    contact = soup.find("div", class_="re__contact-name")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area.text.strip() if area else "",
        "description": description.text.strip() if description else "",
        "image": image["src"] if image else "",
        "contact": contact.text.strip() if contact else ""
    }

def parse_nhatot(link, soup):
    title = soup.find("h1")
    price = soup.find("div", class_="price")
    area = soup.find("div", class_="area")
    description = soup.find("div", class_="section-content")
    image = soup.find("img")
    contact = soup.find("div", class_="seller-info")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area.text.strip() if area else "",
        "description": description.text.strip() if description else "",
        "image": image["src"] if image else "",
        "contact": contact.text.strip() if contact else ""
    }

def parse_alonhadat(link, soup):
    title = soup.find("h1")
    price = soup.find("span", class_="price")
    area = soup.find("span", class_="square")
    description = soup.find("div", class_="content")
    image = soup.find("img")
    contact = soup.find("div", class_="contact")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area.text.strip() if area else "",
        "description": description.text.strip() if description else "",
        "image": image["src"] if image else "",
        "contact": contact.text.strip() if contact else ""
    }

# Các domain còn lại làm tương tự:
def parse_guland(link, soup):
    title = soup.find("h1")
    description = soup.find("div", class_="content-post")
    contact = soup.find("div", class_="contact-content")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": "",
        "area": "",
        "description": description.text.strip() if description else "",
        "image": "",
        "contact": contact.text.strip() if contact else ""
    }

def parse_inhadat(link, soup):
    title = soup.find("h1")
    description = soup.find("div", class_="col-lg-9")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": "",
        "area": "",
        "description": description.text.strip() if description else "",
        "image": "",
        "contact": ""
    }

def parse_ibatdongsan(link, soup):
    return parse_inhadat(link, soup)

def parse_muaban(link, soup):
    title = soup.find("h1")
    price = soup.find("div", class_="price")
    area = soup.find("div", class_="attributes")
    description = soup.find("div", class_="description")
    image = soup.find("img")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": price.text.strip() if price else "",
        "area": area.text.strip() if area else "",
        "description": description.text.strip() if description else "",
        "image": image["src"] if image else "",
        "contact": ""
    }

def parse_rever(link, soup):
    title = soup.find("h1")
    description = soup.find("div", class_="description")
    return {
        "link": link,
        "title": title.text.strip() if title else "",
        "price": "",
        "area": "",
        "description": description.text.strip() if description else "",
        "image": "",
        "contact": ""
    }
