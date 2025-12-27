import requests
import urllib.parse

from bs4 import BeautifulSoup
from flask import redirect, render_template, session
from functools import wraps
import os
import uuid

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    
    return decorated_function


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def get_product_info(url):
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Try Open Graph tags first
        title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"}) or soup.find("title")
        image = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "image"})
        description = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})

        # Extract content
        title_content = title.get("content") if title and title.get("content") else (title.text if title else None)
        image_content = image.get("content") if image else None
        description_content = description.get("content") if description else None

        # Download image if available
        local_image_path = None
        if image_content:
            try:
                # Resolve relative image URLs against the page URL
                image_url = urllib.parse.urljoin(url, image_content)
                image_response = requests.get(image_url, headers=headers, timeout=10)
                image_response.raise_for_status()

                # Protect against very large images (limit ~2MB)
                max_bytes = 2 * 1024 * 1024
                content_length = image_response.headers.get('Content-Length')
                if content_length and int(content_length) > max_bytes:
                    raise requests.exceptions.RequestException("Image too large")

                # Create images folder if not exists
                images_dir = os.path.join(os.getcwd(), 'static', 'images')
                os.makedirs(images_dir, exist_ok=True)
                # Generate unique filename
                ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1] or '.jpg'
                filename = f"{uuid.uuid4()}{ext}"
                filepath = os.path.join(images_dir, filename)

                content = image_response.content
                if len(content) > max_bytes:
                    raise requests.exceptions.RequestException("Image too large")

                with open(filepath, 'wb') as f:
                    f.write(content)

                local_image_path = f"/static/images/{filename}"
            except requests.exceptions.RequestException:
                local_image_path = None

        return {
            "title": title_content,
            "image": local_image_path,
            "description": description_content
        }
    except requests.exceptions.RequestException as e:
        return {
            "title": None,
            "image": None,
            "description": None,
            "error": str(e)
        }