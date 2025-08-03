from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Bật trình duyệt để tick CAPTCHA
    context = browser.new_context()
    page = context.new_page()

    # Mở link bất kỳ của alonhadat để xác thực robot
    page.goto("https://alonhadat.com.vn/-ban-nha-2-mat-tien-hem-xe-hoi-ngay-ha-do-quan-10-gia-chi-7-9-ty--17025352.html")
    print("👉 Tick CAPTCHA nếu có. Sau đó đóng trình duyệt khi hoàn tất.")

    # Chờ bạn tick CAPTCHA xong
    input("⏳ Nhấn Enter sau khi đã xác minh robot...")

    # Lưu storage (cookie + localStorage)
    context.storage_state(path="auth_alonhadat.json")
    print("✅ Đã lưu session vào auth_alonhadat.json")

    browser.close()
