import os
import math
import time
import html
import requests
import streamlit as st
from search_google import search_google

# NEW: dùng fetchers + registry site để test 1 URL
from fetchers import get_html
from sites import pick_site

# ========= Đảm bảo Playwright Chromium có sẵn (cài 1 lần) =========
try:
    if "_pw_ready" not in st.session_state:
        import subprocess, sys

        if os.getenv("USE_PLAYWRIGHT", "1") != "0":
            try:
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install-deps", "chromium"],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            except Exception as e:
                st.warning(f"Install-deps Chromium thất bại (bỏ qua): {e}")

            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
MAX_BATCHES = 3
TARGET_TOTAL = BATCH_SIZE * MAX_BATCHES

st.set_page_config(page_title="Tra cứu BĐS (Streamlit)", layout="wide")
st.title("🔎 Tra cứu bất động sản (Streamlit)")

# ===== CSS cho card =====
st.markdown("""
<style>
.card { padding: 0.75rem; border: 1px solid #eaeaea; border-radius: 12px; }
.card-img { width:100%; height:180px; object-fit:cover; border-radius:10px; background:#f3f5f7; }
.card-title { font-weight:700; font-size:1rem; line-height:1.2; min-height:3.0em; margin:0 0 .25rem 0; }
.card-meta { font-size:.95rem; margin:.1rem 0; }
.card-desc { color:#444; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; min-height:4.4em; }
.card-contact { font-weight:500; margin-top:.25rem; }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.header("Cấu hình")

    api = st.text_input(
        "GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY") or "", type="password"
    )
    cx = st.text_input("GOOGLE_CX", os.getenv("GOOGLE_CX") or "")

    if api:
        os.environ["GOOGLE_API_KEY"] = api
    if cx:
        os.environ["GOOGLE_CX"] = cx

    st.caption("Playwright chạy headless (đổi sang 0 để debug giao diện Chromium).")
    headless = st.checkbox(
        "HEADLESS", value=(os.getenv("PLAYWRIGHT_HEADLESS", "1") == "1")
    )
    os.environ["PLAYWRIGHT_HEADLESS"] = "1" if headless else "0"

    disable_pw = st.checkbox(
        "Disable Playwright (chỉ dùng requests)",
        value=(os.getenv("USE_PLAYWRIGHT", "1") == "0"),
        help="Bật nếu Playwright lỗi trên cloud; crawler sẽ dùng requests + Google Cache fallback."
    )
    os.environ["USE_PLAYWRIGHT"] = "0" if disable_pw else "1"

    st.divider()
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

# --- State ---
if "query" not in st.session_state:
    st.session_state.query = ""
if "results" not in st.session_state:
    st.session_state.results = []
if "batch" not in st.session_state:
    st.session_state.batch = 0

# --- Render card ---
def render_card(item: dict):
    title = html.escape(item.get("title", "") or "")
    price = html.escape(item.get("price", "") or "")
    area  = html.escape(item.get("area", "") or "")
    desc  = item.get("description", "") or ""
    if len(desc) > 300:
        desc = desc[:300].rstrip() + "…"
    desc = html.escape(desc)
    contact = html.escape(item.get("contact", "") or "")
    link = item.get("link")
    image = item.get("image")

    with st.container(border=True):
        left, right = st.columns([1, 1.6], vertical_alignment="top")
        with left:
            if image:
                # Ưu tiên server-side fetch để tránh bị chặn hotlink/referer
                try:
                    st.image(image, use_column_width=True)
                except Exception:
                    st.markdown(f'<img class="card-img" src="{html.escape(image)}">', unsafe_allow_html=True)
            else:
                st.markdown('<div class="card-img"></div>', unsafe_allow_html=True)
        with right:
            st.markdown(f'<div class="card-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-meta"><strong>Giá:</strong> {price}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-meta"><strong>Diện tích:</strong> {area}</div>', unsafe_allow_html=True)
            if desc:
                st.markdown(f'<div class="card-desc">{desc}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-contact"><strong>Liên hệ:</strong> {contact}</div>', unsafe_allow_html=True)
            if item.get("_source"):
                st.caption(f"source: {item['_source']}")
            if link:
                st.link_button("🔗 Xem chi tiết", link)

# --- Form search ---
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
                    res = search_google(st.session_state.query, target_total=TARGET_TOTAL)
                except TypeError:
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

    cols_per_row = int(os.getenv("CARDS_PER_ROW", "2"))
    rows = math.ceil(show_n / cols_per_row)
    idx = 0
    for _ in range(rows):
        cols = st.columns(cols_per_row, vertical_alignment="top")
        for c in cols:
            if idx >= show_n:
                break
            with c:
                render_card(st.session_state.results[idx])
            idx += 1

    st.caption(f"Đang hiển thị {show_n}/{total} tin.")

    c1, c2 = st.columns([1, 3])
    with c1:
        if has_more and st.button("Crawl thêm 10 tin"):
            st.session_state.batch += 1
            time.sleep(0.1)
            st.rerun()

    with c2:
        if st.button("Làm mới"):
            st.session_state.batch = 0
            st.session_state.results = []
            st.session_state.query = ""
            st.rerun()

    if total == 0:
        st.info("Không có kết quả. Thử lại với `site:batdongsan.com.vn \"Bán nhà Quận 3\"`.")

# ================== 🔬 Test 1 URL ==================
st.divider()
st.subheader("🔬 Test 1 URL (theo từng site)")

with st.form("test_one_url_form", clear_on_submit=False):
    test_url = st.text_input(
        "Dán URL bài đăng (chi tiết) để test",
        "https://batdongsan.com.vn/ban-nha-rieng-duong-cao-thang-phuong-3-13/ban-goc-2-mt-q3-dt-6x14m2-gia-18-ty-tl-xd-ham-6l-pr41322979",
    )
    host = ""
    try:
        from urllib.parse import urlparse
        host = (urlparse(test_url).netloc or "").lower()
    except Exception:
        pass

    strategy = st.selectbox(
        "Chọn strategy tải HTML",
        ["auto", "requests", "cloudscraper", "playwright"],
        index=0,
        help="Nếu 403: thử cloudscraper, nếu vẫn lỗi: thử playwright."
    )
    show_raw = st.checkbox("Hiện HTML rút gọn (để debug)", value=False)
    submit = st.form_submit_button("Chạy test")

if submit:
    if not test_url.strip():
        st.warning("Nhập URL trước đã.")
    else:
        picked = pick_site(test_url)
        if not picked:
            st.error("❌ Domain này chưa được hỗ trợ trong 'sites/'.")
        else:
            parser, default_strategy = picked
            # Dùng default_strategy từ SITE_REGISTRY nếu user để 'auto'
            use_strategy = default_strategy if strategy == "auto" else strategy
            st.info(f"Site: **{host or 'n/a'}**, Strategy: **{use_strategy}**")
            try:
                with st.spinner("Đang tải HTML…"):
                    html_text = get_html(test_url, use_strategy)

                from bs4 import BeautifulSoup
                with st.spinner("Đang trích xuất…"):
                    try:
                        data = parser(test_url, html_text)
                    except TypeError:
                        data = parser(test_url, BeautifulSoup(html_text, "lxml"))
                    data["_source"] = use_strategy

                render_card(data)

                if show_raw:
                    short = html_text[:5000] + ("… (truncated)" if len(html_text) > 5000 else "")
                    st.code(short, language="html")
            except Exception as e:
                st.error(f"Lỗi test: {e}. Hãy thử strategy khác (cloudscraper/playwright).")
