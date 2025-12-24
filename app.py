import os
import requests

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, get_product_info


app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
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
    return render_template("index.html",)


@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        email_val = request.form.get("email")
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

    if request.method == "POST":
        name = request.form.get("username")
        if not name:
            return apology("Missing Name.", 400)

        password = request.form.get("password")
        if not password:
            return apology("Missing Password.", 400)
        
        email_val = request.form.get("email")
        if not email_val:
            return apology("Please enter your email address.", 400)

        confirmation = request.form.get("confirmation")
        if not confirmation:
            return apology("Missing Confirmation.", 400)

        if password != confirmation:
            return apology("Passwords do not match.", 400)

        hash_password = generate_password_hash(password)

        try:
            db.execute("INSERT INTO users (username, password_hash, email) VALUES(?, ?, ?)", 
                    name, hash_password, email_val)
        except:
            return apology("The username or email already exists.", 400)

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

        if not item_name or not category or not price or not reward or not description or not img_url:
            return apology("All fields are required", 400)

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
    
    if not data or not data.get("image"):
        placeholder = "/static/Bountygo.png"
        if data:
            data["image"] = placeholder
        else:
            data = {"title": "Unknown Product", "image": placeholder, "description": ""}

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

        bounties = db.execute(query, *params)
        return render_template("bounties.html", bounties=bounties, categories=categories, dispatch_boxes=dispatch_boxes)
    
    else:
        bounties = db.execute("SELECT * FROM bounties WHERE status = 'pending' ORDER BY price DESC")
        return render_template("bounties.html", bounties=bounties, categories=categories, dispatch_boxes=dispatch_boxes)
    

@app.route("/bounties/<int:bounty_id>")
@login_required
def bounty(bounty_id):
    bounty = db.execute("SELECT * FROM bounties WHERE id = ?", bounty_id)
    if not bounty:
        return apology("Bounty not found", 404)
    
    bounty = bounty[0]
    return render_template("bounty.html", bounty=bounty)


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





if __name__ == "__main__":
    app.run(debug=True)