from crawler import extract_info_generic

# 🔎 Thêm các link bạn muốn test vào đây
test_links = [
    "https://alonhadat.com.vn/-ban-nha-2-mat-tien-hem-xe-hoi-ngay-ha-do-quan-10-gia-chi-7-9-ty--17025352.html"
]

print("🔍 ĐANG TEST CÁC LINK RAO BÁN:\n")

for link in test_links:
    print("🔗 Link:", link)
    try:
        info = extract_info_generic(link)
        for k, v in info.items():
            print(f"{k}: {v}")
    except Exception as e:
        print(f"❌ Lỗi khi xử lý link: {e}")
    print("-" * 80)
