import os
import math
import time
import streamlit as st
from search_google import search_google

# --- cấu hình ---
BATCH_SIZE = 10
MAX_BATCHES = 3      # tối đa 30 tin
TARGET_TOTAL = BATCH_SIZE * MAX_BATCHES

st.set_page_config(page_title="Tra cứu BĐS (Streamlit)", layout="wide")

# --- sidebar: API keys & tuỳ chọn ---
with st.sidebar:
    st.header("Cấu hình")
    api = st.text_input("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY") or "", type="password")
    cx  = st.text_input("GOOGLE_CX", os.getenv("GOOGLE_CX") or "")
    os.environ["GOOGLE_API_KEY"] = api
    os.environ["GOOGLE_CX"] = cx

    st.caption("Playwright chạy headless (đổi sang 0 để debug giao diện Chromium).")
    headless = st.checkbox("HEADLESS", value=True)
    os.environ["PLAYWRIGHT_HEADLESS"] = "1" if headless else "0"

# --- khởi tạo state ---
if "query" not in st.session_state:
    st.session_state.query = ""
if "results" not in st.session_state:
    st.session_state.results = []
if "batch" not in st.session_state:
    st.session_state.batch = 0

st.title("🔎 Tra cứu bất động sản (Streamlit)")

# --- form tìm kiếm ---
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
                    res = search_google(st.session_state.query)
            st.session_state.results = res or []

# --- hiển thị kết quả ---
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
            if idx >= show_n: break
            item = st.session_state.results[idx]
            with c:
                if item.get("image"):
                    st.image(item["image"], use_container_width=True)
                st.markdown(f"**{item.get('title','')}**")
                st.write(f"**Giá:** {item.get('price','')}")
                st.write(f"**Diện tích:** {item.get('area','')}")
                if item.get("description"):
                    # rút gọn mô tả
                    desc = item["description"]
                    if len(desc) > 240:
                        desc = desc[:240].rstrip() + "…"
                    st.write(desc)
                st.write(f"**Liên hệ:** {item.get('contact','')}")
                if item.get("link"):
                    st.link_button("🔗 Xem chi tiết", item["link"])
            idx += 1

    st.caption(f"Đang hiển thị {show_n}/{total} tin.")

    # nút Crawl thêm
    c1, c2 = st.columns([1, 3])
    with c1:
        if has_more and st.button("Crawl thêm 10 tin"):
            st.session_state.batch += 1
            time.sleep(0.1)  # nhỏ để ổn định UI
            st.rerun()

    # làm mới toàn bộ tìm kiếm
    with c2:
        if st.button("Làm mới"):
            st.session_state.batch = 0
            st.session_state.results = []
            st.session_state.query = ""
            st.rerun()
