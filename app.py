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

from helpers import apology, login_required, get_product_info


app = Flask(__name__)

# Ensure a secret key is set for securely signing the session cookie
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-please-change")
# Additional cookie/session hardening defaults (override in production as needed)
app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

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

db = SQL("sqlite:///bounty.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    # Home page route
    featured_bounties = db.execute("SELECT * FROM bounties WHERE status = 'pending' ORDER BY reward_fee DESC LIMIT 4")
    return render_template("index.html", featured_bounties=featured_bounties)


@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "POST":
        username = request.form.get("username").lower()
        email_val = request.form.get("email").lower()
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
def register():
    
    session.clear() # Clear any existing session data

    if request.method == "POST":
        name = request.form.get("username").lower()
        if not name:
            return apology("Missing Name.", 400)

        password = request.form.get("password")
        if not password:
            return apology("Missing Password.", 400)
        
        email_val = request.form.get("email").lower()
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
@login_required
def order():
    if request.method == "POST":

        item_name = request.form.get("item_name")
        category = request.form.get("category")
        price = request.form.get("price")
        reward = request.form.get("reward")
        description = request.form.get("description")
        img_url = request.form.get("img_url")
        dispatch_box = request.form.get("dispatch_box")

        if not item_name or not price or not reward or not description or not dispatch_box:
            return apology("All fields are required", 400)
        
        try:
            price = float(price)
            reward = float(reward)

            if price < 0 or reward < 0:
                return apology("Price and reward must be positive", 400)
            
        except ValueError:
            return apology("Price and reward must be numbers", 400)

        db.execute("INSERT INTO bounties (poster_id, item_name, category, price, reward_fee, description, img_url, dispatch_box) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                     session["user_id"], item_name, category, price, reward, description, img_url, dispatch_box)
        flash("Bounty successfully posted!")
        return redirect("/")
    else:
        return render_template("order.html")
    

@app.route("/fetch_url")
def fetch_url():
    url = request.args.get("url")
    data = get_product_info(url)

    placeholder = "/static/Bountygo.png"
    
    if not data:
        data = {"title": "Unknown Product", "image": placeholder, "description": ""}
    elif not data.get("image"):
        data["image"] = placeholder

    return jsonify(data)


@app.route("/bounties", methods=["GET", "POST"])
def bounties():
    query = "SELECT * FROM bounties WHERE status = 'pending'"
    params = []
    categories = db.execute("SELECT DISTINCT category FROM bounties")
    dispatch_boxes = db.execute("SELECT DISTINCT dispatch_box FROM bounties")

    if request.method == "POST":
        
        search_query = request.form.get("search_query")
        category = request.form.get("category")
        dispatch_box = request.form.get("dispatch_box")
        
        if search_query:
            query += " AND item_name LIKE ?"
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
            flash("No bounties found matching your search criteria.")
            return redirect("/bounties")
        
        return render_template("bounties.html", bounties=bounties, categories=categories, dispatch_boxes=dispatch_boxes)
    
    else:
        bounties = db.execute("SELECT * FROM bounties WHERE status = 'pending' ORDER BY price DESC")
        return render_template("bounties.html", bounties=bounties, categories=categories, dispatch_boxes=dispatch_boxes)
    

@app.route("/bounties/<int:bounty_id>")
@login_required
def bounty(bounty_id):
    bounty = db.execute("""SELECT bounties.*, users.username AS poster_name, users.id AS poster_id
        FROM bounties
        JOIN users ON bounties.poster_id = users.id
        WHERE bounties.id = ?
    """, bounty_id)
    
    if not bounty:
        return apology("Bounty not found", 404)
    
    bounty = bounty[0]
    return render_template("details.html", bounty=bounty)


@app.route("/claim", methods=["POST"])
@login_required
def claim():
    bounty_id = request.form.get("bounty_id")
    if not bounty_id:
        return apology("Invalid bounty ID", 400)

    bounty = db.execute("SELECT * FROM bounties WHERE id = ? AND status = 'pending'", bounty_id)
    if not bounty:
        return apology("Bounty not found or already claimed", 404)
    
    if bounty[0]["poster_id"] == session["user_id"]:
        return apology("You cannot claim your own bounty", 400)
       
    db.execute("UPDATE bounties SET status = 'claimed', traveler_id = ? WHERE id = ?", session["user_id"], bounty_id)
    flash("Bounty claimed successfully!")

    return redirect(f"/bounties/{bounty_id}")


@app.route("/profile", methods=["POST", "GET"])
@login_required
def profile():

    user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    if not user_info:
        return apology("User not found", 404)
    
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

    return render_template("profile.html", user=user_info[0], orders=orders, claims=claims)


@app.route("/delete_bounty", methods=["POST"])
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
        dispatch_box = request.form.get("dispatch_box")

        if not item_name or not price or not reward or not description or not dispatch_box:
            return apology("All fields are required", 400)
        
        if bounty["status"] != "pending":
            return apology("Only pending bounties can be edited.", 400)
    
        try:
            price = float(price)
            reward = float(reward)

            if price < 0 or reward < 0:
                return apology("Price and reward must be positive", 400)
            
        except ValueError:
            return apology("Price and reward must be numbers", 400)
        


        db.execute("UPDATE bounties SET item_name = ?, price = ?, reward_fee = ?, description = ?, dispatch_box = ? WHERE id = ?",
                   item_name, price, reward, description, dispatch_box, bounty_id)
        
        flash("Bounty updated successfully!")
        return redirect("/profile")


@app.route("/completed_bounty", methods=["POST"])
@login_required
def completed_bounty():
    bounty_id = request.form.get("bounty_id")
    user_id = session["user_id"]

    bounty = db.execute("SELECT * FROM bounties WHERE id = ? AND poster_id = ? AND status = 'claimed'", 
                        bounty_id, user_id)
    
    if not bounty:
        return apology("Bounty not found or unauthorized", 404)
    
    db.execute("UPDATE bounties SET status = 'completed' WHERE id = ?", bounty_id)

    flash("Bounty marked as completed! Thank you.")
    return redirect("/profile")


@app.route("/user/<int:user_id>")
@login_required
def view_public_profile(user_id):
    rows = db.execute("SELECT username, email FROM users WHERE id = ?", user_id)
    if not rows:
        return apology("User not found", 404)
    target_user = rows[0]

    stats_rows = db.execute("""
        SELECT 
            (SELECT COUNT(*) FROM bounties WHERE traveler_id = ? AND status = 'completed') as completed_as_traveler,
            (SELECT COUNT(*) FROM bounties WHERE poster_id = ? AND status = 'completed') as completed_as_poster
    """, user_id, user_id)

    stats = stats_rows[0] if stats_rows else {"completed_as_traveler": 0, "completed_as_poster": 0}

    return render_template("user_profile.html", user=target_user, stats=stats, role="view_only")


if __name__ == "__main__":
    app.run(debug=True)