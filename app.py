import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
try:
    from cachelib.file import FileSystemCache
    from flask_session.cachelib.cachelib import CacheLibSessionInterface
except Exception:
    FileSystemCache = None
    CacheLibSessionInterface = None
from werkzeug.security import check_password_hash, generate_password_hash
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import urllib.parse
import socket
import ipaddress
from datetime import datetime, timedelta, timezone

from helpers import apology, login_required, get_product_info, validate_city, calculate_success_rate, to_cents, format_currency

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)

db_url = os.getenv("DATABASE_URL", "sqlite:///bounty.db")

# Ensure a secret key is set for securely signing the session cookie
secret = os.environ.get("SECRET_KEY")
if not secret:
    # Allow a development fallback only when explicitly in dev mode
    if os.getenv("FLASK_ENV") == "development" or os.getenv("FLASK_DEBUG") == "1":
        secret = "dev-secret-key-please-change"
        app.logger.warning("Using development SECRET_KEY fallback; set SECRET_KEY in production")
    else:
        raise RuntimeError("SECRET_KEY environment variable is required")
app.secret_key = secret
# Additional cookie/session hardening defaults (override in production as needed)
app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
# Ensure secure cookie flag when running under HTTPS (set via env in production)
app.config.setdefault("SESSION_COOKIE_SECURE", os.getenv("SESSION_COOKIE_SECURE", "False") == "True")

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)


# Make `csrf_token()` available in templates
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

app.config["SESSION_PERMANENT"] = False

# Prefer CacheLib backend (FileSystemCache) to avoid deprecated FileSystemSessionInterface
if FileSystemCache is not None and CacheLibSessionInterface is not None:
    cache_dir = os.path.join(os.getcwd(), 'flask_session_cache')
    os.makedirs(cache_dir, exist_ok=True)
    cache = FileSystemCache(cache_dir)
    # Use CacheLibSessionInterface directly to avoid setting an unsupported SESSION_TYPE
    app.session_interface = CacheLibSessionInterface(client=cache)
else:
    # Fallback to filesystem (may be deprecated depending on flask-session version)
    app.config["SESSION_TYPE"] = "filesystem"
    Session(app)


db = None

@app.before_request
def init_db():
    """Lazy initialize the DB to avoid side effects at import time."""
    global db
    if db is None:
        db = SQL(db_url)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


@app.template_filter('currency')
def currency_filter(cents):
    if cents is None:
        return "0.00"
    return format_currency(cents)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@limiter.limit("10 per second")
def index():
    # Home page route
    try:
        featured_bounties = db.execute(
            "SELECT * FROM bounties WHERE status = 'pending' ORDER BY reward_fee DESC LIMIT 4"
        )

    except Exception:
        featured_bounties = []  
    return render_template("index.html", featured_bounties=featured_bounties)


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():

    session.clear()

    if request.method == "POST":
        username = request.form.get("username").lower().strip()
        email_val = request.form.get("email").lower().strip()
        password = request.form.get("password")

        if not username or not password or not email_val:
            return apology("Please provide both username, password and email.", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ? AND email = ?", username, email_val)
        if len(rows) != 1 or not check_password_hash(rows[0]["password_hash"], password):
            return apology("Invalid username, password and email")

        session["user_id"] = rows[0]["id"]
        return redirect("/")

    else:
        return render_template("login.html")


@app.route("/logout")
@login_required
def logout():

    session.clear()

    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    
    session.clear() # Clear any existing session data

    if request.method == "POST":
        name = request.form.get("username").lower().strip()
        if not name:
            return apology("Missing Name.", 400)

        password = request.form.get("password")
        if not password:
            return apology("Missing Password.", 400)
        
        email_val = request.form.get("email").lower().strip()
        if not email_val:
            return apology("Please enter your email address.", 400)

        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("Missing Confirmation.", 400)

        if password != confirmation:
            return apology("Passwords do not match.", 400)

        # Check if username or email already exists
        existing_user = db.execute("SELECT id FROM users WHERE username = ? OR email = ?", name, email_val)
        if existing_user:
            return apology("Username or email already exists.", 400)

        hash_password = generate_password_hash(password)

        db.execute("INSERT INTO users (username, password_hash, email) VALUES(?, ?, ?)", 
                name, hash_password, email_val)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/order", methods=["GET", "POST"])
@limiter.limit("10 per hour")
@login_required
def order():
    if request.method == "POST":
        if session.get('is_processing_order'):
            return apology("Your request is being processed. Please wait.", 429)
        
        user_id = session.get("user_id")

        item_name = request.form.get("item_name")
        category = request.form.get("category")
        price = request.form.get("price")
        reward = request.form.get("reward")
        description = request.form.get("description")
        img_url = request.form.get("img_url")
        dispatch_box = request.form.get("dispatch_box") or request.form.get("location")
        if not all([item_name, price, reward, description, dispatch_box]):
            return apology("All fields are required", 400)
        
        is_real, full_name = validate_city(dispatch_box)
        if not is_real:
            return apology("The city does not exist. Please check again!", 400)
        
        try:
            price_cents = to_cents(price)
            reward_cents = to_cents(reward)
            if price_cents < 0 or reward_cents < 0:
                return apology("Price and reward must be positive", 400)
        except ValueError:
            return apology("Price and reward must be numbers", 400)
        
        last_order = db.execute("SELECT created_at FROM bounties WHERE poster_id = ? ORDER BY created_at DESC LIMIT 1", user_id)
        if last_order:
            try:
                last_time = datetime.strptime(last_order[0]['created_at'], '%Y-%m-%d %H:%M:%S')

                now = datetime.now()
                diff = (now - last_time).total_seconds()

                if 0 <= diff < 15:
                    return apology(f"Please wait {int(15 - diff)}s...", 400)
            except (ValueError, TypeError):
                pass
        
        session['is_processing_order'] = True
        try:
            db.execute("INSERT INTO bounties (poster_id, item_name, category, price, reward_fee, description, img_url, dispatch_box) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    session["user_id"], item_name, category, price_cents, reward_cents, description, img_url, full_name)
            flash("Bounty successfully posted!")
            return redirect("/")
        except Exception as e:
            return apology("An error occurred during save.", 500)
        finally:
            session.pop('is_processing_order', None)

    else:
        return render_template("order.html")
    

@app.route("/fetch_url")
@limiter.limit("10 per minute")
def fetch_url():
    url = request.args.get("url")
    # Basic validation: require scheme and prevent SSRF to private IPs
    placeholder = "/static/Bountygo.png"
    if not url:
        return jsonify({"title": "Unknown Product", "image": placeholder, "description": ""})

    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Invalid URL scheme or host")
        
        data = get_product_info(url)
        if not data:
            data = {"title": "Unknown Product", "image": placeholder, "description": ""}
        elif not data.get("image"):
            data["image"] = placeholder

        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Fetch URL error: {e}")
        return jsonify({"title": "Invalid URL", "image": placeholder, "description": ""})


@app.route("/bounties", methods=["GET", "POST"])
@limiter.limit("10 per second")
def bounties():
    base_query = "SELECT * FROM bounties WHERE status = 'pending'"
    params = []
    categories = db.execute("SELECT DISTINCT category FROM bounties")
    dispatch_boxes = db.execute("SELECT DISTINCT dispatch_box FROM bounties")

    try:
        if request.method == "POST":
            
            search_query = request.form.get("search_query")
            category = request.form.get("category")
            dispatch_box = request.form.get("dispatch_box")
            
            query = base_query
            if search_query:
                query += " AND item_name ILIKE ?"
                params.append(f"%{search_query}%")

            if category:
                query += " AND category = ?"
                params.append(category)

            if dispatch_box:
                query += " AND dispatch_box = ?"
                params.append(dispatch_box)

            query += " ORDER BY price DESC"
            bounties = db.execute(query, *params)

            if not bounties:
                flash("No bounties found.")
                return redirect("/bounties")
            
            return render_template("bounties.html", bounties=bounties, categories=categories, dispatch_boxes=dispatch_boxes)
        
        else:
            bounties = db.execute(base_query + "ORDER BY price DESC")
            return render_template("bounties.html", bounties=bounties, categories=categories, dispatch_boxes=dispatch_boxes)
    except Exception as e:
        return apology("Database busy, please refresh.", 500)
    

@app.route("/bounties/<int:bounty_id>")
@limiter.limit("5 per second")
@login_required
def bounty_details(bounty_id):
    rows = db.execute("""
        SELECT b.*, u.username AS poster_name, u.id AS poster_id
        FROM bounties b
        JOIN users u ON b.poster_id = u.id
        WHERE b.id = ?
    """, bounty_id)
    
    if not rows:
        return apology("Bounty not found", 404)
    
    current_bounty = rows[0]
    
    bounty_requests = db.execute("""
        SELECT r.id AS req_id, r.traveler_id, u.username, u.completed_orders, u.total_claimed
        FROM bounty_requests r 
        JOIN users u ON r.traveler_id = u.id 
        WHERE r.bounty_id = ? AND r.status = 'pending'
    """, bounty_id)

    for req in bounty_requests:
        claimed = req["total_claimed"] or 0
        completed = req["completed_orders"] or 0
        req["rate"] = calculate_success_rate(completed, claimed)


    check = db.execute("SELECT id FROM bounty_requests WHERE bounty_id = ? AND traveler_id = ?", 
                       bounty_id, session["user_id"])
    
    has_requested = len(check) > 0
    
    return render_template("details.html", 
                           bounty=current_bounty, 
                           requests=bounty_requests, 
                           has_requested=has_requested)


@app.route("/request_bounty", methods=["POST"])
@limiter.limit("10 per hour")
@login_required
def request_bounty():
    bounty_id = request.form.get("bounty_id")
    traveler_id = session["user_id"]
    if not bounty_id:
        return apology("Invalid bounty ID", 400)

    exists = db.execute("SELECT id FROM bounty_requests WHERE bounty_id = ? AND traveler_id = ?", 
                        bounty_id, traveler_id)
    if exists:
        return apology("You have already requested this bounty", 400)
    
    db.execute("INSERT INTO bounty_requests (bounty_id, traveler_id) VALUES(?, ?)", bounty_id, traveler_id)
    flash("Bounty request submitted successfully!")
    return redirect(f"/bounties/{bounty_id}")


@app.route("/accept_traveler", methods=["POST"])
@limiter.limit("10 per hour")
@login_required
def accept_traveler():
    request_id = request.form.get("request_id")

    query = """
            SELECT r.id, r.bounty_id, r.traveler_id 
            FROM bounty_requests r
            JOIN bounties b ON r.bounty_id = b.id
            WHERE r.id = ? AND b.poster_id = ? AND b.status = 'pending'
        """
    req = db.execute(query, request_id, session["user_id"])
    if not req:
        return apology("No permission or request not found.", 403)
    
    target = req[0]

    db.execute("UPDATE bounties SET traveler_id = ?, status = 'claimed' WHERE id = ?", 
               target["traveler_id"], target["bounty_id"])
    db.execute("UPDATE bounty_requests SET status = 'accepted' WHERE id = ?", request_id)
    db.execute("UPDATE bounty_requests SET status = 'rejected' WHERE bounty_id = ? AND id != ?", 
               target["bounty_id"], request_id)

    flash("Traveler accepted!")
    return redirect(f"/bounties/{target['bounty_id']}")


@app.route("/profile", methods=["POST", "GET"])
@login_required
def profile():

    rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    if not rows:
        return apology("User not found", 404)

    user = rows[0]

    s_total = (user.get("total_posted") or 0)
    s_completed = (user.get("completed_posted") or 0)
    shopper_rate = calculate_success_rate(s_completed, s_total)

    t_total = (user.get("total_claimed") or 0)
    t_completed = (user.get("completed_orders") or 0)
    traveler_rate = calculate_success_rate(t_completed, t_total)

    orders = db.execute("""
        SELECT bounties.*, users.username AS traveler_name, users.id AS traveler_id
        FROM bounties
        LEFT JOIN users ON bounties.traveler_id = users.id
        WHERE poster_id = ?
        ORDER BY bounties.id DESC
    """, session["user_id"])

    claims = db.execute("""
        SELECT bounties.*, users.username AS poster_name, users.id AS poster_id
        FROM bounties
        JOIN users ON bounties.poster_id = users.id
        WHERE traveler_id = ?
        ORDER BY bounties.id DESC
    """, session["user_id"])

    return render_template("profile.html", user=user,
                            shopper_rate=shopper_rate,
                            traveler_rate=traveler_rate,
                            orders=orders,
                            claims=claims)


@app.route("/delete_bounty", methods=["POST"])
@limiter.limit("10 per hour")
@login_required
def delete_bounty():
    bounty_id = request.form.get("bounty_id")
    if not bounty_id:
        return apology("Invalid bounty ID", 400)

    bounty = db.execute("SELECT * FROM bounties WHERE id = ? AND poster_id = ? AND status = 'pending'", 
                        bounty_id, session["user_id"])
    
    if not bounty:
        return apology("Bounty not found or unauthorized", 404)  

    db.execute("DELETE FROM bounties WHERE id = ?", bounty_id)
    flash("Bounty deleted successfully!")

    return redirect("/profile")


@app.route("/edit_bounty/<int:bounty_id>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
@login_required
def update_bounty(bounty_id):
    bounty = db.execute("SELECT * FROM bounties WHERE id = ? AND poster_id = ?", bounty_id, session["user_id"])

    if not bounty:
        return apology("Bounty not found or unauthorized", 403)
    
    bounty = bounty[0]

    if request.method == "GET":
        if bounty["status"] != "pending":
            return apology("Only pending bounties can be edited.", 400)
        return render_template("edit_bounty.html", bounty=bounty)
    
    else:
        item_name = request.form.get("item_name")
        price = request.form.get("price")
        reward = request.form.get("reward")
        description = request.form.get("description")
        dispatch_box = request.form.get("dispatch_box") or request.form.get("location")

        is_real, full_name = validate_city(dispatch_box)

        if not is_real:
            return apology("The city does not exist. Please check again!", 400)

        if not item_name or not price or not reward or not description or not dispatch_box:
            return apology("All fields are required", 400)
        
        if bounty["status"] != "pending":
            return apology("Only pending bounties can be edited.", 400)

        try:
            price = int(round(float(request.form.get("price")) * 100))
            reward = int(round(float(request.form.get("reward")) * 100))

            if price < 0 or reward < 0:
                return apology("Price and reward must be positive", 400)
            
        except ValueError:
            return apology("Price and reward must be numbers", 400)
        


        db.execute("UPDATE bounties SET item_name = ?, price = ?, reward_fee = ?, description = ?, dispatch_box = ? WHERE id = ?",
                   item_name, price, reward, description, full_name, bounty_id)
        
        flash("Bounty updated successfully!")
        return redirect("/profile")


@app.route("/completed_bounty", methods=["POST"])
@limiter.limit("20 per hour")
@login_required
def completed_bounty():
    bounty_id = request.form.get("bounty_id")
    user_id = session["user_id"]

    bounty = db.execute("SELECT * FROM bounties WHERE id = ? AND poster_id = ? AND status = 'claimed'", 
                        bounty_id, user_id)
    
    if not bounty:
        return apology("Bounty not found or unauthorized", 404)
    
    if bounty[0]["poster_id"] != session["user_id"]:
        return apology("You cannot mark this bounty as completed", 400)
    
    db.execute("UPDATE bounties SET status = 'completed' WHERE id = ?", bounty_id)
    db.execute("DELETE FROM bounty_requests WHERE bounty_id = ?", bounty_id)

    flash("Bounty marked as completed! Thank you.")
    return redirect("/profile")


@app.route("/user/<int:user_id>")
@limiter.limit("5 per minute")
@login_required
def view_public_profile(user_id):
    rows = db.execute("""SELECT username, email, 
                      total_posted, completed_posted, 
                      total_claimed, completed_orders 
                      FROM users 
                      WHERE id = ?""", user_id)
    if not rows:
        return apology("User not found", 404)
    target_user = rows[0]

    s_total = target_user["total_posted"] or 0
    s_completed = target_user["completed_posted"] or 0
    shopper_rate = calculate_success_rate(s_completed, s_total)

    t_total = target_user["total_claimed"] or 0
    t_completed = target_user["completed_orders"] or 0
    traveler_rate = calculate_success_rate(t_completed, t_total)


    return render_template("user_profile.html", 
                           user=target_user, 
                           shopper_rate=shopper_rate, 
                           traveler_rate=traveler_rate, 
                           role="view_only")




if __name__ == "__main__":
    app.run(debug=True)
