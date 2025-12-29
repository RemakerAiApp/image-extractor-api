from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from io import BytesIO

app = Flask(__name__)
CORS(app)  # CORS allow (important)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

@app.route("/extract-images", methods=["POST"])
def extract_images():
    data = request.get_json()
    url = data.get("url")

    if not url or not url.startswith("http"):
        return jsonify({"error": "Valid URL required"}), 400

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue

            img_url = urljoin(url, src)

            try:
                img_res = requests.get(img_url, headers=HEADERS, timeout=10)
                img_obj = Image.open(BytesIO(img_res.content))

                images.append({
                    "url": img_url,
                    "width": img_obj.width,
                    "height": img_obj.height,
                    "format": img_obj.format
                })
            except:
                continue

        return jsonify({
            "success": True,
            "count": len(images),
            "images": images
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def health():
    return "Image Extractor API Running"


if __name__ == "__main__":
    app.run()
