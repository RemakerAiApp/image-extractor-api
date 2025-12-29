from flask import Flask, request, jsonify
from flask_cors import CORS   # 👈 ADD
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)   # 👈 VERY IMPORTANT

@app.route("/")
def home():
    return jsonify({"status": "API running"})

@app.route("/api/extract-images", methods=["POST"])
def extract_images():
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"error": "URL required"}), 400

    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    images = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            images.append(urljoin(url, src))

    return jsonify({
        "success": True,
        "total_images": len(images),
        "images": images
    })
