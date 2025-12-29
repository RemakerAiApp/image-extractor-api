from flask import Response, request
import requests
import base64

@app.route("/api/image-proxy")
def image_proxy():
    img_url = request.args.get("url")

    if not img_url:
        return "Missing image URL", 400

    # ❌ data:image/... URLs ko skip karo
    if img_url.startswith("data:"):
        return "Data URLs not supported", 204

    # ❌ sirf http/https allow
    if not img_url.startswith(("http://", "https://")):
        return "Invalid image URL", 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": img_url
        }
        r = requests.get(img_url, headers=headers, timeout=10)

        return Response(
            r.content,
            content_type=r.headers.get(
                "Content-Type", "image/jpeg"
            )
        )

    except Exception as e:
        return str(e), 500
