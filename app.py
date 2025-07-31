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
    app.run(debug=True)
