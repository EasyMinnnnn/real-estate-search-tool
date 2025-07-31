import os
from flask import Flask, render_template, request
from search_google import search_google

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query")
        results = search_google(query)
        return render_template("index.html", query=query, results=results)
    return render_template("index.html", results=[])
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
