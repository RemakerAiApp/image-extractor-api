from flask import Response, request
import requests

@app.route("/api/image-proxy", methods=["GET"])
def image_proxy():
    img_url = request.args.get("url", "").strip()

    # ❌ URL missing
    if not img_url:
        return "Missing image URL", 400

    # ❌ data:image / base64 URLs skip
    if img_url.startswith("data:"):
        return "", 204

    # ❌ only http / https allowed
    if not (img_url.startswith("http://") or img_url.startswith("https://")):
        return "Invalid image URL", 400

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            # 🔥 Referer spoof (hotlink protection bypass)
            "Referer": img_url,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }

        r = requests.get(
            img_url,
            headers=headers,
            timeout=15,
            stream=True
        )

        # ❌ non-200 response
        if r.status_code != 200:
            return "", 204

        content_type = r.headers.get("Content-Type", "image/jpeg")

        # ❌ non-image response
        if not content_type.startswith("image/"):
            return "", 204

        response = Response(
            r.content,
            content_type=content_type
        )

        # ✅ browser cache (performance)
        response.headers["Cache-Control"] = "public, max-age=86400"

        return response

    except Exception:
        # ❌ silently fail (no 500 in browser)
        return "", 204
