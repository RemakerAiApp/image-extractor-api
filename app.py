from flask import Flask, jsonify, request, Response
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = Flask(__name__)

# No need for flask_cors package - we manually add CORS headers (works on Render.com without extra dependency)

@app.route("/api/image-proxy", methods=["GET"])
def image_proxy():
    img_url = request.args.get("url", "").strip()
    
    if not img_url:
        return "Missing image URL", 400
    
    if img_url.startswith("data:"):
        return "", 204
    
    if not (img_url.startswith("http://") or img_url.startswith("https://")):
        return "Invalid image URL", 400
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": img_url.split("?")[0],  # Cleaner referer to bypass some protections
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }
        
        r = requests.get(img_url, headers=headers, timeout=20, stream=True)
        
        if r.status_code != 200:
            return "", 204
        
        content_type = r.headers.get("Content-Type") or "image/jpeg"
        if not content_type.startswith("image/"):
            return "", 204
        
        # Stream response for large images (memory efficient)
        response = Response(r.iter_content(chunk_size=8192), content_type=content_type)
        response.headers["Cache-Control"] = "public, max-age=86400"
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        return response
    
    except Exception as e:
        print(f"Proxy error for {img_url}: {e}")
        return "", 204


@app.route("/api/extract-images", methods=["POST", "OPTIONS"])
def extract_images():
    # Handle CORS preflight
    if request.method == "OPTIONS":
        resp = jsonify({})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp, 200
    
    # Actual POST request
    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"success": False, "error": "Missing or invalid JSON"}), 400
        
        url = data["url"].strip()
        
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return jsonify({"success": False, "error": "Invalid URL"}), 400
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        }
        
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Clean up script/style tags
        for tag in soup(["script", "style"]):
            tag.decompose()
        
        img_tags = soup.find_all("img")
        
        images = set()  # Avoid duplicates
        
        for tag in img_tags:
            src = (
                tag.get("src") or
                tag.get("data-src") or
                tag.get("data-lazy-src") or
                tag.get("data-original")
            )
            
            # Handle srcset (take first URL)
            if tag.get("srcset"):
                srcset_first = tag["srcset"].split(",")[0].strip().split(" ")[0]
                if srcset_first:
                    src = srcset_first
            
            if not src:
                continue
            
            # Convert to absolute URL
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(url, src)
            elif not src.startswith("http"):
                src = urljoin(url, src)
            
            # Skip invalid ones
            if src.startswith("data:") or not src.startswith(("http://", "https://")):
                continue
            
            # Optional: Filter common image extensions for better accuracy
            if src.lower().split("?")[0].endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp')):
                images.add(src)
        
        unique_images = list(images)
        
        response = jsonify({
            "success": True,
            "images": unique_images,
            "total_images": len(unique_images)
        })
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
        
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Could not fetch website: {str(e)}"}), 502
    except Exception as e:
        print(f"Extract error: {e}")
        return jsonify({"success": False, "error": "Something went wrong"}), 500


if __name__ == "__main__":
    app.run()
