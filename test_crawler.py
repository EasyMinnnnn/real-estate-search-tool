from crawler import extract_info_generic

# 🔎 Thêm các link bạn muốn test vào đây
test_links = [
    "https://batdongsan.com.vn/ban-nha-rieng-duong-cao-thang-phuong-12-5/ban-2-mat-hem-71m2-ngang-khung-5m-ngay-khu-ha-do-sam-uat-p12-q10-nhinh-9-ty-pr42505316"
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
