# test_bds.py
from crawler import extract_info_generic

URLS = [
    # đặt 3-5 link chi tiết BĐS vào đây (link bạn gửi ở trên + vài link khác)
    "https://batdongsan.com.vn/ban-nha-rieng-duong-cao-thang-phuong-3-13/ban-goc-2-mt-q3-dt-6x14m2-gia-18-ty-tl-xd-ham-6l-pr41322979",
]

for u in URLS:
    data = extract_info_generic(u)
    print("\n===", u, "===")
    for k in ("title", "price", "area", "contact", "image"):
        print(f"{k}: {data.get(k)}")
    print("desc_len:", len(data.get("description", "")))
