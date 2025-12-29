from flask import Flask, jsonify, request, Response
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

app = Flask(__name__)

# Basic logging for Render.com logs
logging.basicConfig(level=logging.INFO)

# Health check + Welcome page (root URL pe 404 nahi aayega)
@app.route("/")
def home():
    return jsonify({
        "message": "Image Extractor API is live and running! 🚀",
        "status": "healthy",
        "version": "1.1",
        "endpoints": {
            "POST /api/extract-images": "Extract image URLs from any website",
            "GET /api/image-proxy?url=...": "Proxy images (bypass hotlink protection)"
        },
        "frontend": "https://www.image-extractor.com/tools/website-image-extractor",
        "docs": "Send POST request with JSON: {\"url\": \"https://example.com\"}"
    }), 200


@app.route("/api/image-proxy", methods=["GET"])
def image_proxy():
    img_url = request.args.get("url", "").strip()

    if not img_url:
        return "Missing image URL parameter", 400

    if img_url.startswith("data:"):
        return "", 204

    if not (img_url.startswith("http://") or img_url.startswith("https://")):
        return "Invalid image URL (must start with http/https)", 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Referer": img_url.split("?")[0],
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Connection": "keep-alive"
        }

        r = requests.get(img_url, headers=headers, timeout=20, stream=True, allow_redirects=True)

        if r.status_code != 200:
            return "", 204

        content_type = r.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            return "", 204

        # Stream large images efficiently
        response = Response(r.iter_content(chunk_size=8192), content_type=content_type)
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response

    except Exception as e:
        app.logger.error(f"Image proxy failed for {img_url}: {str(e)}")
        return "", 204


@app.route("/api/extract-images", methods=["POST", "OPTIONS"])
def extract_images():
    # Handle CORS preflight request
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp, 200

    try:
        data = request.get_json(force=True)  # force=True for better handling
        if not data or "url" not in data:
            return jsonify({"success": False, "error": "Missing 'url' in JSON body"}), 400

        url = data["url"].strip()

        if not url:
            return jsonify({"success": False, "error": "URL cannot be empty"}), 400

        if not (url.startswith("http://") or url.startswith("https://")):
            return jsonify({"success": False, "error": "URL must start with http:// or https://"}), 400

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }

        r = requests.get(url, headers=headers, timeout=35, allow_redirects=True)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        # Remove unnecessary tags to speed up parsing
        for tag in soup(["script", "style", "noscript", "meta", "link"]):
            tag.decompose()

        img_tags = soup.find_all("img")
        images = set()

        for tag in img_tags:
            src = (
                tag.get("src") or
                tag.get("data-src") or
                tag.get("data-lazy-src") or
                tag.get("data-original") or
                tag.get("data-image")
            )

            # Handle srcset - pick the first valid URL
            if not src and tag.get("srcset"):
                candidates = [item.strip().split(" ")[0] for item in tag["srcset"].split(",")]
                src = next((c for c in candidates if c), None)

            if not src:
                continue

            # Convert relative to absolute
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(url, src)
            elif not src.startswith(("http://", "https://")):
                src = urljoin(url, src)

            # Final validation
            if not src.startswith(("http://", "https://")) or src.startswith("data:"):
                continue

            # Strong filter: only known image extensions (more accurate, less junk)
            lower_src = src.lower().split("?")[0].split("#")[0]
            if lower_src.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.avif', '.ico')):
                images.add(src)

        unique_images = sorted(list(images))  # Sort for consistent order

        response = jsonify({
            "success": True,
            "images": unique_images,
            "total_images": len(unique_images),
            "website": url
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except requests.exceptions.Timeout:
        return jsonify({"success": False, "error": "Request timed out. Website is slow or blocked."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"success": False, "error": "Could not connect to website. Check URL or try again later."}), 502
    except requests.exceptions.HTTPError as e:
        return jsonify({"success": False, "error": f"HTTP Error {e.response.status_code}: {e.response.reason}"}), 502
    except Exception as e:
        app.logger.error(f"Extract images failed for {url}: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error. Please try again."}), 500


if __name__ == "__main__":
    # Render.com pe gunicorn use hota hai, local test ke liye
    app.run(host="0.0.0.0", port=5000, debug=False)
