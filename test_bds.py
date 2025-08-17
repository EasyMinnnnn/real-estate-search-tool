# test_bds.py
import json
import sys
from typing import List
from crawler import extract_info_generic

# DÁN THÊM LINK CHI TIẾT BDS VÀO ĐÂY
URLS: List[str] = [
    "https://batdongsan.com.vn/ban-nha-rieng-duong-cao-thang-phuong-3-13/ban-goc-2-mt-q3-dt-6x14m2-gia-18-ty-tl-xd-ham-6l-pr41322979",
    # "https://batdongsan.com.vn/.....-prXXXXXXXX",   # thêm các link khác
]

def run_one(url: str):
    print(f"\n=== {url} ===")
    data = extract_info_generic(url)
    # In gọn các trường quan trọng + chiều dài mô tả
    out = {
        "link": data.get("link"),
        "title": data.get("title"),
        "price": data.get("price"),
        "area": data.get("area"),
        "contact": data.get("contact"),
        "image": data.get("image"),
        "desc_len": len((data.get("description") or "").strip()),
        "_source": data.get("_source"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

def main():
    # Cho phép truyền link qua argv để test nhanh: python test_bds.py <url1> <url2> ...
    args = [a for a in sys.argv[1:] if a.strip()]
    urls = args if args else URLS
    if not urls:
        print("Chưa có URL nào. Hãy bổ sung vào URLS hoặc truyền qua argv.")
        sys.exit(1)
    for u in urls:
        try:
            run_one(u)
        except Exception as e:
            print(f"[ERR] {u}: {e}")

if __name__ == "__main__":
    main()
