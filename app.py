import os
from flask import Flask, render_template, request
from search_google import search_google

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query")
    results = search_google(query)
    return render_template("results.html", query=query, results=results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sẽ gán biến môi trường PORT
    app.run(debug=False, host="0.0.0.0", port=port)  # ← PHẢI có host="0.0.0.0" và port đúng
