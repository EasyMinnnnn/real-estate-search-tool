import os
from flask import Flask, render_template, request, session, redirect, url_for
from search_google import search_google

app = Flask(__name__)
# Cần secret key để dùng session (đặt biến môi trường khi deploy)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# Cấu hình batch
BATCH_SIZE = 10
MAX_BATCHES = 3  # 10 x 3 = 30 tin tối đa

def _slice_results(batch_index: int):
    """Trả về (list kết quả đã cắt theo batch, còn_more: bool)."""
    results = session.get("results_store", [])
    n = min(batch_index * BATCH_SIZE, len(results))
    has_more = batch_index < MAX_BATCHES and n < len(results)
    return results[:n], has_more

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Tìm kiếm mới
        query = (request.form.get("query") or "").strip()
        if not query:
            # không nhập gì -> hiển thị rỗng
            return render_template("index.html", query="", results=[], has_more=False)

        # Lấy tối đa 30 tin trước (để bấm thêm 2 lần nữa)
        try:
            all_results = search_google(query, target_total=BATCH_SIZE * MAX_BATCHES)
        except TypeError:
            # nếu search_google(query) cũ không nhận target_total thì fallback
            all_results = search_google(query)

        # Lưu trạng thái vào session
        session["current_query"] = query
        session["results_store"] = all_results or []
        session["batch_index"] = 1  # hiển thị 10 tin đầu

        sliced, has_more = _slice_results(session["batch_index"])
        return render_template("index.html", query=query, results=sliced, has_more=has_more)

    # GET: nếu đã có session thì giữ nguyên kết quả hiện tại
    query = session.get("current_query", "")
    batch_index = session.get("batch_index", 0)
    results, has_more = _slice_results(batch_index) if batch_index else ([], False)
    return render_template("index.html", query=query, results=results, has_more=has_more)

@app.route("/crawl_more", methods=["POST"])
def crawl_more():
    # Không có state thì quay về trang chính
    if "results_store" not in session:
        return redirect(url_for("index"))

    # Tăng batch, giới hạn tối đa
    session["batch_index"] = min(session.get("batch_index", 1) + 1, MAX_BATCHES)

    query = session.get("current_query", "")
    results, has_more = _slice_results(session["batch_index"])
    return render_template("index.html", query=query, results=results, has_more=has_more)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
