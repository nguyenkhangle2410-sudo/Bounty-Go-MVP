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

    session = requests.Session()

    adapter = SafeHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        response = session.get(url, timeout=5, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Try Open Graph tags first
        title_tag = (
            soup.find("meta", property="og:title") or 
            soup.find("meta", attrs={"name": "title"}) or 
            soup.find("title")
        )

        desc_tag = (
            soup.find("meta", property="og:description") or 
            soup.find("meta", attrs={"name": "description"})
        )

        image_tag = (
            soup.find("meta", property="og:image") or 
            soup.find("meta", attrs={"name": "image"}) or
            soup.find("link", rel="image_src") or
            soup.find("img", {"id": "icImg"}) or
            soup.find("img", {"class": "ux-image-magnifier-view__image"})
        )

        # Extract content
        title_content = None
        if title_tag:
            raw_title = title_tag.get("content") or title_tag.get_text()
            title_content = raw_title.strip() if raw_title else None

        if desc_tag:
            raw_desc = desc_tag.get("content")
            description_content = raw_desc.strip() if raw_desc else None

        image_url = None
        if image_tag:
            raw_url = image_tag.get("content") or image_tag.get("href") or image_tag.get("src")
            if raw_url:
                raw_url = raw_url.strip()
                if raw_url.startswith("//"):
                    raw_url = "https:" + raw_url
                image_url = urllib.parse.urljoin(response.url, raw_url)

        return {
            "title": title_content,
            "image": image_url,
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

            city = (
                address.get('city') or 
                address.get('town') or 
                address.get('village') or 
                address.get('city_district') or 
                address.get('suburb') or 
                address.get('province') or 
                address.get('state')
            )

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

