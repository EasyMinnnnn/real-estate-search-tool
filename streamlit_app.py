import os
import math
import time
import requests
import streamlit as st
from search_google import search_google

# ========= Đảm bảo Playwright Chromium có sẵn (cài 1 lần) =========
try:
    if "_pw_ready" not in st.session_state:
        import subprocess, sys
        # chỉ cài nếu không bị tắt Playwright
        if os.getenv("USE_PLAYWRIGHT", "1") != "0":
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        st.session_state._pw_ready = True
except Exception as e:
    st.warning(f"Không cài được Playwright Chromium (sẽ dùng requests/cache nếu cần): {e}")

# ========= Load secrets -> env (nếu có) =========
for k in ("GOOGLE_API_KEY", "GOOGLE_CX", "PLAYWRIGHT_HEADLESS", "USE_PLAYWRIGHT"):
    try:
        if k in st.secrets and st.secrets[k]:
            os.environ[k] = str(st.secrets[k])
    except Exception:
        pass

# --- cấu hình ---
BATCH_SIZE = 10
MAX_BATCHES = 3          # tối đa 30 tin
TARGET_TOTAL = BATCH_SIZE * MAX_BATCHES

st.set_page_config(page_title="Tra cứu BĐS (Streamlit)", layout="wide")
st.title("🔎 Tra cứu bất động sản (Streamlit)")

# --- Sidebar: cấu hình & chẩn đoán ---
with st.sidebar:
    st.header("Cấu hình")

    api = st.text_input(
        "GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY") or "", type="password"
    )
    cx = st.text_input("GOOGLE_CX", os.getenv("GOOGLE_CX") or "")

    # Ghi lại vào env để search_google đọc mỗi lần
    if api:
        os.environ["GOOGLE_API_KEY"] = api
    if cx:
        os.environ["GOOGLE_CX"] = cx

    st.caption("Playwright chạy headless (đổi sang 0 để debug giao diện Chromium).")
    headless = st.checkbox("HEADLESS", value=(os.getenv("PLAYWRIGHT_HEADLESS", "1") == "1"))
    os.environ["PLAYWRIGHT_HEADLESS"] = "1" if headless else "0"

    disable_pw = st.checkbox(
        "Disable Playwright (chỉ dùng requests)",
        value=(os.getenv("USE_PLAYWRIGHT", "1") == "0"),
        help="Bật nếu Playwright lỗi trên cloud; crawler sẽ dùng requests + Google Cache fallback."
    )
    os.environ["USE_PLAYWRIGHT"] = "0" if disable_pw else "1"

    st.divider()
    # Chẩn đoán Google API nhanh
    if st.button("Test Google API"):
        params = {
            "key": os.getenv("GOOGLE_API_KEY", ""),
            "cx": os.getenv("GOOGLE_CX", ""),
            "q": "test",
            "num": 3,
            "hl": "vi",
        }
        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=15)
            st.write("HTTP:", r.status_code)
            st.json(r.json())
        except Exception as e:
            st.error(f"Lỗi gọi Google API: {e}")

    st.caption(f"API key loaded: {'GOOGLE_API_KEY' in os.environ}")
    st.caption(f"CX loaded: {'GOOGLE_CX' in os.environ}")

# --- Khởi tạo state ---
if "query" not in st.session_state:
    st.session_state.query = ""
if "results" not in st.session_state:
    st.session_state.results = []
if "batch" not in st.session_state:
    st.session_state.batch = 0

# --- Form tìm kiếm ---
with st.form("search_form", clear_on_submit=False):
    q = st.text_input("Nhập từ khoá", st.session_state.query or "Bán nhà Quận 3, Hồ Chí Minh")
    submitted = st.form_submit_button("Tìm kiếm")
    if submitted:
        if not api or not cx:
            st.error("Thiếu GOOGLE_API_KEY hoặc GOOGLE_CX.")
        else:
            st.session_state.query = q.strip()
            st.session_state.batch = 1
            with st.spinner("Đang tìm kiếm và gom link…"):
                try:
                    # lấy sẵn tối đa 30 tin (để bấm tăng dần mỗi lần 10)
                    res = search_google(st.session_state.query, target_total=TARGET_TOTAL)
                except TypeError:
                    # fallback nếu hàm cũ không có tham số target_total
                    res = search_google(st.session_state.query)
                except Exception as e:
                    st.error(f"Lỗi khi gọi search_google: {e}")
                    res = []
            st.session_state.results = res or []

# --- Hiển thị kết quả ---
if st.session_state.query:
    st.subheader(f"Kết quả cho: {st.session_state.query}")
    total = len(st.session_state.results)
    show_n = min(st.session_state.batch * BATCH_SIZE, total)
    has_more = (st.session_state.batch < MAX_BATCHES) and (show_n < total)

    # dạng lưới 3 cột
    cols_per_row = 3
    rows = math.ceil(show_n / cols_per_row)
    idx = 0
    for _ in range(rows):
        cols = st.columns(cols_per_row)
        for c in cols:
            if idx >= show_n:
                break
            item = st.session_state.results[idx]
            with c:
                if item.get("image"):
                    st.image(item["image"], use_container_width=True)
                st.markdown(f"**{item.get('title','')}**")
                st.write(f"**Giá:** {item.get('price','')}")
                st.write(f"**Diện tích:** {item.get('area','')}")
                if item.get("description"):
                    desc = item["description"]
                    if len(desc) > 240:
                        desc = desc[:240].rstrip() + "…"
                    st.write(desc)
                st.write(f"**Liên hệ:** {item.get('contact','')}")
                # Nhãn debug nguồn dữ liệu
                if item.get("_source"):
                    st.caption(f"source: {item['_source']}")
                if item.get("link"):
                    st.link_button("🔗 Xem chi tiết", item["link"])
            idx += 1

    st.caption(f"Đang hiển thị {show_n}/{total} tin.")

    # Nút Crawl thêm
    c1, c2 = st.columns([1, 3])
    with c1:
        if has_more and st.button("Crawl thêm 10 tin"):
            st.session_state.batch += 1
            time.sleep(0.1)
            st.rerun()

    # Làm mới
    with c2:
        if st.button("Làm mới"):
            st.session_state.batch = 0
            st.session_state.results = []
            st.session_state.query = ""
            st.rerun()

    # Gợi ý nếu không có kết quả
    if total == 0:
        st.info(
            "Không có kết quả. Kiểm tra lại CSE (Search the entire web), quota Custom Search JSON API, "
            "hoặc thử truy vấn hẹp hơn: `site:batdongsan.com.vn \"Bán nhà Quận 3\"`."
        )
