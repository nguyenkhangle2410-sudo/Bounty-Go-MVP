import requests

from bs4 import BeautifulSoup
from flask import redirect, render_template, session
from functools import wraps

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
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=7)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.find("meta", property="og:title")
        image = soup.find("meta", property="og:image")
        description = soup.find("meta", property="og:description")

        return {
            "title": title["content"] if title else None,
            "image": image["content"] if image else None,
            "description": description["content"] if description else None
        }
    except requests.exceptions.RequestException as e:
        return {
            "title": None,
            "image": None,
            "description": None,
            "error": str(e)
        }