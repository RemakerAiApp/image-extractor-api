from flask import Flask, jsonify, request, Response
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/")
def home():
    return jsonify({
        "message": "Image Extractor API is live and running! 🚀",
        "status": "healthy",
        "version": "1.3",
        "endpoints": {
            "POST /api/extract-images": "Extract image URLs from any website",
            "GET /api/image-proxy?url=...": "Proxy images (bypass hotlink protection)"
        },
        "frontend": "https://www.image-extractor.com/tools/website-image-extractor"
    }), 200


@app.route("/api/image-proxy", methods=["GET"])
def image_proxy():
    img_url = request.args.get("url", "").strip()
    if not img_url or img_url.startswith("data:") or not img_url.startswith(("http://", "https://")):
        return "", 204

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Referer": img_url.split("?")[0],
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }
        r = requests.get(img_url, headers=headers, timeout=20, stream=True, allow_redirects=True)
        if r.status_code != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
            return "", 204

        response = Response(r.iter_content(chunk_size=8192), content_type=r.headers.get("Content-Type", "image/jpeg"))
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    except Exception as e:
        app.logger.error(f"Proxy error: {str(e)}")
        return "", 204


@app.route("/api/extract-images", methods=["POST", "OPTIONS"])
def extract_images():
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp, 200

    try:
        data = request.get_json(force=True)
        if not data or "url" not in data:
            return jsonify({"success": False, "error": "Missing 'url'"}), 400

        url = data["url"].strip()
        if not url or not url.startswith(("http://", "https://")):
            return jsonify({"success": False, "error": "Invalid URL"}), 400

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }

        r = requests.get(url, headers=headers, timeout=35, allow_redirects=True)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        images = set()

        for tag in soup.find_all("img"):
            sources = []

            # All possible src attributes
            for attr in ["src", "data-src", "data-lazy-src", "data-original", "data-image", "data-srcset"]:
                if tag.get(attr):
                    sources.append(tag[attr])

            # srcset and data-srcset
            for attr in ["srcset", "data-srcset"]:
                if tag.get(attr):
                    for part in tag[attr].split(","):
                        candidate = part.strip().split(" ")[0]
                        if candidate:
                            sources.append(candidate)

            for src in sources:
                if not src or src.startswith("data:"):
                    continue

                # Resolve relative URLs
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urljoin(url, src)
                elif not src.startswith(("http://", "https://")):
                    src = urljoin(url, src)

                if src.startswith(("http://", "https://")):
                    images.add(src)

        unique_images = sorted(list(images))

        response = jsonify({
            "success": True,
            "images": unique_images,
            "total_images": len(unique_images),
            "website": url
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except Exception as e:
        app.logger.error(f"Extract error: {str(e)}")
        return jsonify({"success": False, "error": "Failed to extract images. Try a different website."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
