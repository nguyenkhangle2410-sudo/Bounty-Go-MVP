import requests
import urllib.parse
import logging
import socket
import ipaddress

from bs4 import BeautifulSoup
from flask import redirect, render_template, session
from functools import wraps
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import os
import uuid

from security import SafeHTTPAdapter

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

    session = requests.session()

    adapter = SafeHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = session.get(url, timeout=5, allow_redirects=True)
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

        # Download image if available, with validation
        local_image_path = None
        if image_content:
            try:
                image_url = urllib.parse.urljoin(response.url, image_content)

                # Stream the image and enforce size limit
                max_bytes = 2 * 1024 * 1024
                with session.get(image_url, headers=headers, timeout=10, stream=True) as img_resp:
                    img_resp.raise_for_status()

                    content_length = img_resp.headers.get('Content-Length')
                    if content_length and int(content_length) > max_bytes:
                        raise requests.exceptions.RequestException("Image too large")

                    images_dir = os.path.join(os.getcwd(), 'static', 'images')
                    os.makedirs(images_dir, exist_ok=True)

                    ext = os.path.splitext(urllib.parse.urlparse(image_url).path)[1] or '.jpg'
                    allowed_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                    if ext.lower() not in allowed_exts:
                        ext = '.jpg'
                    filename = f"{uuid.uuid4()}{ext}"
                    filepath = os.path.join(images_dir, filename)

                    total = 0
                    with open(filepath, 'wb') as f:
                        for chunk in img_resp.iter_content(8192):
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > max_bytes:
                                f.close()
                                os.remove(filepath)
                                raise requests.exceptions.RequestException("Image too large")
                            f.write(chunk)

                    local_image_path = f"/static/images/{filename}"

            except requests.exceptions.RequestException:
                local_image_path = None
                logging.exception("Failed to fetch or save remote image")

        return {
            "title": title_content,
            "image": local_image_path,
            "description": description_content
        }
    except requests.exceptions.RequestException:
        # Do not expose internal error details to callers; return empty data
        return {
            "title": None,
            "image": None,
            "description": None
        }
    

def validate_city(location_input):
    q = urllib.parse.quote_plus(location_input or "")
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&addressdetails=1&limit=1"
    headers = {'User-Agent': 'BountyGo_Global_Validator'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data:
            address = data[0].get('address', {})

            city = address.get('city') or address.get('town') or address.get('village') or address.get('state')
            country = address.get('country')
            if city and country:
                return True, f"{city}, {country}"
            return False, None
        return False, None
    except requests.exceptions.RequestException:
        return False, None
    

def calculate_success_rate(completed, total):
    if not total or total <= 0:
        return 100.0
    return round((completed / total * 100), 1)


def to_cents(amount_str: str) -> int:
    try:
        amount = Decimal(amount_str)
        return int((amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (ValueError, TypeError, decimal.InvalidOperation):
        raise ValueError("Invalid currency format.")
    

def format_currency(cents: int) -> str:
    return f"{cents / 100:.2f}"

