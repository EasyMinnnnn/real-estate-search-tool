from crawler import extract_info_generic

# 🔎 Thêm các link bạn muốn test vào đây
test_links = [
    "https://batdongsan.com.vn/ban-nha-rieng-duong-cao-thang-phuong-12-5/ban-2-mat-hem-71m2-ngang-khung-5m-ngay-khu-ha-do-sam-uat-p12-q10-nhinh-9-ty-pr42505316",
    "https://alonhadat.com.vn/-ban-nha-2-mat-tien-hem-xe-hoi-ngay-ha-do-quan-10-gia-chi-7-9-ty--17025352.html",
    "https://www.nhatot.com/mua-ban-nha-dat-quan-10-tp-ho-chi-minh/126733039.htm#px=SR-stickyad-[PO-1][PL-top]",
    "https://nhabansg.vn/can-ban-nha-5x10-trung-tam-q10-cach-mt-ngo-gia-tu-tam-40m-nb605518.html",
    "https://i-batdongsan.com/10-ty-cho-50m2-thang-may-pho-tran-duy-hung-trung-tam-quan-cau-giay-6341743.html",
    "https://i-nhadat.com/10-ty-cho-50m2-thang-may-pho-tran-duy-hung-trung-tam-quan-cau-giay-5820008.html",
    "https://guland.vn/post/ban-gap-nr-56m2-gan-le-quang-dao-keo-dai-899-ty-tin-het-han-1320463"
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
