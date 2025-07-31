import requests
from bs4 import BeautifulSoup

def extract_info_batdongsan(link):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.get(link, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        title = soup.find("h1").get_text(strip=True)
        price = soup.select_one(".re__price").get_text(strip=True) if soup.select_one(".re__price") else "Không rõ"
        area = soup.select_one(".re__area").get_text(strip=True) if soup.select_one(".re__area") else "Không rõ"
        description = soup.find("div", class_="re__section-body").get_text(strip=True) if soup.find("div", class_="re__section-body") else ""
        image = soup.select_one(".swiper-wrapper img")
        img_url = image["src"] if image else ""

        phone = soup.select_one("a.re__contact-phone")
        phone_number = phone.get("href").replace("tel:", "") if phone else "Ẩn hoặc yêu cầu đăng nhập"

        return {
            "title": title,
            "price": price,
            "area": area,
            "description": description,
            "image": img_url,
            "phone": phone_number,
            "link": link
        }
    except Exception as e:
        return {"error": str(e), "link": link}
