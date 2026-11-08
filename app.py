"""
KHOLA - Live chicken sales website (Flask + SQLite)

Folders:
  app.py        - the website routes (this file)
  config.py     - business settings: payment numbers, contacts, admin invite code
  db.py         - database tables and helpers
  templates/    - HTML pages
  static/       - css, js, icon, manifest.json, sw.js, uploads/

Run:   python app.py
Open:  http://127.0.0.1:5000
"""
import os
import secrets
import sqlite3
import urllib.parse
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
from db import close_db, db, init_db, notify, now, order_no, sales_summary, set_setting, setting

os.makedirs(config.UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = config.load_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("HTTPS") == "1"  # set HTTPS=1 when online with https
app.teardown_appcontext(close_db)
app.jinja_env.globals["no"] = order_no


# ------------------------------------------------------------------- security
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
        if not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Security check failed. Go back, refresh the page and try again.")


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("user_id"):
            flash("Please log in first.")
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return f(*a, **k)
    return w


@app.context_processor
def inject():
    return dict(brand=setting("brand"), motto=setting("motto"), user=current_user(),
                is_admin=bool(session.get("admin_id")), contact_email=config.CONTACT_EMAIL,
                contact_wa=config.CONTACT_WHATSAPP)


# ------------------------------------------------------------------- app files (PWA)
@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ------------------------------------------------------------------- customer routes
@app.route("/")
def home():
    products = db().execute("SELECT * FROM products").fetchall()
    sizes = {p["id"]: db().execute("SELECT * FROM sizes WHERE product_id=?", (p["id"],)).fetchall()
             for p in products}
    return render_template("home.html", products=products, sizes=sizes,
                           photo=setting("photo"), channels=config.PAY_CHANNELS,
                           low_limit=config.LOW_STOCK_LIMIT)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        f = request.form
        try:
            db().execute("INSERT INTO users(name,phone,email,password_hash,address,created) VALUES(?,?,?,?,?,?)",
                         (f["name"].strip(), f["phone"].strip(), f["email"].strip().lower(),
                          generate_password_hash(f["password"]), f["address"].strip(), now()))
            db().commit()
        except sqlite3.IntegrityError:
            flash("That email is already registered. Please log in.")
            return redirect(url_for("login"))
        flash("Account created. Please log in.")
        return redirect(url_for("login"))
    return render_template("auth.html", title="Sign Up", mode="signup", link=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session["user_id"] = u["id"]
            return redirect(url_for("home"))
        flash("Wrong email or password.")
    return render_template("auth.html", title="Log In", mode="login", link=None)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    link = None
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        u = db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if u:
            token = secrets.token_urlsafe(24)
            session["reset_" + token] = u["id"]
            link = url_for("reset", token=token, _external=True)
            print("PASSWORD RESET LINK:", link)  # send by email in production
        flash("If that email exists, a reset link has been created.")
        if not config.SHOW_RESET_LINK:
            link = None
    return render_template("auth.html", title="Forgot Password", mode="forgot", link=link)


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    uid = session.get("reset_" + token)
    if not uid:
        flash("Reset link invalid or expired. Request a new one.")
        return redirect(url_for("forgot"))
    if request.method == "POST":
        db().execute("UPDATE users SET password_hash=? WHERE id=?",
                     (generate_password_hash(request.form["password"]), uid))
        db().commit()
        session.pop("reset_" + token, None)
        flash("Password changed. Please log in.")
        return redirect(url_for("login"))
    return render_template("auth.html", title="Set New Password", mode="reset", link=None)


@app.route("/account")
@login_required
def my_account():
    uid = session["user_id"]
    orders = db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    notes = db().execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,)).fetchall()
    return render_template("account.html", orders=orders, notes=notes, channels=config.PAY_CHANNELS)


@app.route("/order/start", methods=["POST"])
@login_required
def order_start():
    try:
        size_id = int(request.form["size_id"])
        qty = int(request.form["qty"])
    except (KeyError, ValueError):
        return jsonify(ok=False, error="Invalid order.")
    s = db().execute("SELECT s.*, p.name pname, p.stock FROM sizes s JOIN products p ON p.id=s.product_id WHERE s.id=?",
                     (size_id,)).fetchone()
    if not s or qty < 1:
        return jsonify(ok=False, error="Invalid order.")
    if s["stock"] < qty:
        return jsonify(ok=False, error=f"Sorry, only {s['stock']} available in the Khola right now.")
    cur = db().execute(
        "INSERT INTO orders(user_id,size_id,product_id,product_name,size_label,qty,total,status,created) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (session["user_id"], size_id, s["product_id"], s["pname"], s["label"], qty,
         qty * s["price"], "WAITING", now()))
    db().commit()
    return jsonify(ok=True, id=cur.lastrowid, order_no=order_no(cur.lastrowid), total=qty * s["price"])


@app.route("/order/<int:oid>/pay", methods=["POST"])
@login_required
def order_pay(oid):
    o = db().execute("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, session["user_id"])).fetchone()
    channel = request.form.get("channel")
    ref = " ".join(request.form.get("reference", "").split()).upper()
    if not o or channel not in config.PAY_CHANNELS or not ref:
        flash("Payment details incomplete.")
        return redirect(url_for("home"))
    if o["status"] != "WAITING":
        flash("This order can no longer be changed.")
        return redirect(url_for("my_account"))
    # one payment reference can only be used on one order
    if db().execute("SELECT 1 FROM orders WHERE reference=? AND id!=?", (ref, oid)).fetchone():
        flash("That payment reference was already used on another order. Check the code you typed "
              "or contact the admin on WhatsApp " + config.CONTACT_WHATSAPP + ". "
              "You can enter it again under My Orders.")
        return redirect(url_for("my_account"))
    db().execute("UPDATE orders SET channel=?, reference=? WHERE id=?", (channel, ref, oid))
    db().commit()
    flash(f"{order_no(oid)} is WAITING. The admin will verify your payment soon.")
    return redirect(url_for("my_account"))


@app.route("/order/<int:oid>/refund", methods=["POST"])
@login_required
def request_refund(oid):
    db().execute("UPDATE orders SET refund_requested=1 WHERE id=? AND user_id=? AND status IN ('WAITING','REJECTED')",
                 (oid, session["user_id"]))
    db().commit()
    flash("Refund request sent to admin.")
    return redirect(url_for("my_account"))


@app.route("/club")
def club():
    member = False
    if session.get("user_id"):
        member = bool(db().execute("SELECT 1 FROM club WHERE user_id=?", (session["user_id"],)).fetchone())
    return render_template("club.html", member=member)


@app.route("/club/join", methods=["POST"])
@login_required
def club_join():
    db().execute("INSERT OR IGNORE INTO club(user_id,created) VALUES(?,?)", (session["user_id"], now()))
    db().commit()
    flash("You are now in the Daily Customer Club.")
    return redirect(url_for("club"))


@app.route("/club/leave", methods=["POST"])
@login_required
def club_leave():
    db().execute("DELETE FROM club WHERE user_id=?", (session["user_id"],))
    db().commit()
    return redirect(url_for("club"))


@app.route("/privacy")
def privacy():
    c = ("<p>We collect only the details needed to process your orders: name, phone, email, address, "
         "order history and payment reference codes.</p>"
         "<p>Passwords are stored encrypted (hashed). We never see your mobile money PIN: you only enter "
         "the transaction reference after you pay.</p>"
         "<p>Your data is used for order verification, delivery, refunds and (if you join) stock alerts. "
         "We do not sell or share it with third parties.</p>"
         f"<p>To request deletion of your data, contact {config.CONTACT_EMAIL}.</p>")
    return render_template("page.html", title="Privacy Policy", content=c)


@app.route("/terms")
def terms():
    c = ("<p><b>If payment is done and admin verifies, the number of chickens is subtracted from the Khola; "
         "if not verified, the customer has the right to reclaim a refund.</b></p>"
         "<p>Orders are WAITING until verified by the admin. Stock shown is live and may change.</p>"
         "<p>Customers must enter the correct transaction reference. Refund requests are approved by the admin "
         "based on a true request (e.g. money sent but goods not available).</p>")
    return render_template("page.html", title="Terms and Conditions", content=c)


# ------------------------------------------------------------------- admin routes
def admin_page(mode, title, **kw):
    return render_template("admin_auth.html", mode=mode, title=title,
                           admin_contact=config.ADMIN_CONTACT, wa=None, sms=None, **kw)


@app.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    if request.method == "POST":
        f = request.form
        pin = f.get("pin", "")
        if f.get("invite") != config.ADMIN_INVITE_CODE:
            flash("Invalid admin invite code.")
        elif not (pin.isdigit() and len(pin) == 4):
            flash("PIN must be 4 digits.")
        else:
            try:
                db().execute("INSERT INTO admins(name,phone,pin_hash,created) VALUES(?,?,?,?)",
                             (f["name"].strip(), f["phone"].strip(), generate_password_hash(pin), now()))
                db().commit()
                flash("Admin registered. Log in with your PIN.")
                return redirect(url_for("admin_login"))
            except sqlite3.IntegrityError:
                flash("That phone number is already registered.")
    return admin_page("signup", "Admin Sign Up")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if session.get("fails", 0) >= 5:
            flash("Too many wrong attempts. Close the browser and try later.")
        else:
            a = db().execute("SELECT * FROM admins WHERE phone=?", (request.form["phone"].strip(),)).fetchone()
            if a and check_password_hash(a["pin_hash"], request.form.get("pin", "")):
                session["admin_id"] = a["id"]
                session["fails"] = 0
                return redirect(url_for("admin_dashboard"))
            session["fails"] = session.get("fails", 0) + 1
            flash("Wrong phone or PIN.")
    return admin_page("login", "Admin Login")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("home"))


@app.route("/admin/forgot", methods=["GET", "POST"])
def admin_forgot():
    wa = sms = None
    if request.method == "POST":
        phone = request.form["phone"].strip()
        a = db().execute("SELECT * FROM admins WHERE phone=?", (phone,)).fetchone()
        if a:
            token = str(secrets.randbelow(900000) + 100000)
            cur = db().execute("INSERT INTO pin_resets(admin_id,token,created) VALUES(?,?,?)",
                               (a["id"], token, now()))
            db().commit()
            print("ADMIN PIN RESET TOKEN:", token)
            text = f"KHOLA admin PIN reset request. Phone: {phone}. Request #{cur.lastrowid}"
            sms = f"sms:{config.ADMIN_CONTACT}?body={urllib.parse.quote(text)}"
            wa = f"https://wa.me/265{config.ADMIN_CONTACT[1:]}?text={urllib.parse.quote(text)}"
        else:
            flash("No admin with that phone number.")
    return render_template("admin_auth.html", mode="forgot", title="Restore PIN",
                           admin_contact=config.ADMIN_CONTACT, wa=wa, sms=sms)


@app.route("/admin/reset", methods=["GET", "POST"])
def admin_reset():
    if request.method == "POST":
        f = request.form
        pin = f.get("pin", "")
        r = db().execute("SELECT r.* FROM pin_resets r JOIN admins a ON a.id=r.admin_id "
                         "WHERE a.phone=? AND r.token=? AND r.used=0", (f["phone"].strip(), f["token"].strip())).fetchone()
        if r and pin.isdigit() and len(pin) == 4:
            db().execute("UPDATE admins SET pin_hash=? WHERE id=?", (generate_password_hash(pin), r["admin_id"]))
            db().execute("UPDATE pin_resets SET used=1 WHERE id=?", (r["id"],))
            db().commit()
            flash("PIN changed. Log in now.")
            return redirect(url_for("admin_login"))
        flash("Invalid token or PIN.")
    return admin_page("reset", "Reset PIN")


@app.route("/admin")
@admin_required
def admin_dashboard():
    d = db()
    products = d.execute("SELECT * FROM products").fetchall()
    sizes = {p["id"]: d.execute("SELECT * FROM sizes WHERE product_id=?", (p["id"],)).fetchall() for p in products}
    orders = d.execute("SELECT o.*, u.name cname, u.phone cphone FROM orders o JOIN users u ON u.id=o.user_id "
                       "ORDER BY o.id DESC LIMIT 100").fetchall()
    customers = d.execute("SELECT u.*, COUNT(o.id) n, SUM(CASE WHEN o.status='APPROVED' THEN o.total END) spent "
                          "FROM users u LEFT JOIN orders o ON o.user_id=u.id GROUP BY u.id ORDER BY u.id DESC").fetchall()
    members = d.execute("SELECT u.id,u.name,u.phone FROM club c JOIN users u ON u.id=c.user_id").fetchall()
    admins = d.execute("SELECT * FROM admins").fetchall()
    resets = d.execute("SELECT r.*, a.name, a.phone FROM pin_resets r JOIN admins a ON a.id=r.admin_id "
                       "WHERE r.used=0 ORDER BY r.id DESC LIMIT 10").fetchall()
    low = [p for p in products if p["stock"] <= config.LOW_STOCK_LIMIT]
    return render_template("admin.html", products=products, sizes=sizes, orders=orders,
                           summary=sales_summary(), low=low, low_limit=config.LOW_STOCK_LIMIT,
                           customers=customers, members=members, admins=admins, resets=resets,
                           presets=config.PRESET_PHOTOS, admin_contact=config.ADMIN_CONTACT)


@app.route("/admin/order/<int:oid>/verify", methods=["POST"])
@admin_required
def admin_verify(oid):
    d = db()
    o = d.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not o or o["status"] != "WAITING":
        return redirect(url_for("admin_dashboard"))
    p = d.execute("SELECT * FROM products WHERE id=?", (o["product_id"],)).fetchone()
    if p["stock"] < o["qty"]:
        flash(f"Not enough stock for {order_no(oid)} (only {p['stock']} left). Reject and refund instead.")
        return redirect(url_for("admin_dashboard"))
    d.execute("UPDATE products SET stock=stock-? WHERE id=?", (o["qty"], o["product_id"]))
    d.execute("UPDATE orders SET status='APPROVED', deducted=1, verified_at=? WHERE id=?", (now(), oid))
    notify(o["user_id"], f"{order_no(oid)} VERIFIED. Your {o['qty']} x {o['product_name']} "
                         f"({o['size_label']}) is confirmed. Thank you!")
    d.commit()
    flash(f"{order_no(oid)} verified. Stock updated, customer notified.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/order/<int:oid>/reject", methods=["POST"])
@admin_required
def admin_reject(oid):
    d = db()
    o = d.execute("SELECT * FROM orders WHERE id=? AND status='WAITING'", (oid,)).fetchone()
    if o:
        d.execute("UPDATE orders SET status='REJECTED' WHERE id=?", (oid,))
        notify(o["user_id"], f"{order_no(oid)} could not be verified. You may reclaim a refund from your dashboard.")
        d.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/order/<int:oid>/refund", methods=["POST"])
@admin_required
def admin_refund(oid):
    d = db()
    o = d.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if o and o["status"] != "REFUNDED":
        if o["deducted"]:
            d.execute("UPDATE products SET stock=stock+? WHERE id=?", (o["qty"], o["product_id"]))
        d.execute("UPDATE orders SET status='REFUNDED', deducted=0 WHERE id=?", (oid,))
        notify(o["user_id"], f"Refund approved for {order_no(oid)} (K{o['total']:,}). "
                             f"Money will be returned to your {o['channel']} account.")
        d.commit()
        flash(f"{order_no(oid)} refunded. Remember to send the money back manually.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/stock", methods=["POST"])
@admin_required
def admin_stock():
    d = db()
    for key, val in request.form.items():
        if val.isdigit():
            if key.startswith("stock_"):
                d.execute("UPDATE products SET stock=? WHERE id=?", (int(val), int(key[6:])))
            elif key.startswith("price_"):
                d.execute("UPDATE sizes SET price=? WHERE id=?", (int(val), int(key[6:])))
    d.commit()
    flash("Stock and prices saved.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/settings", methods=["POST"])
@admin_required
def admin_settings():
    set_setting("brand", request.form.get("brand", "KHOLA").strip() or "KHOLA")
    set_setting("motto", request.form.get("motto", "").strip())
    flash("Home page updated.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/photo", methods=["POST"])
@admin_required
def admin_photo():
    f = request.files.get("file")
    url = request.form.get("url", "").strip() or request.form.get("preset", "").strip()
    if f and f.filename:
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            flash("Use a JPG, PNG or WEBP image.")
            return redirect(url_for("admin_dashboard"))
        name = f"home_{secrets.token_hex(4)}{ext}"
        f.save(os.path.join(config.UPLOAD_DIR, name))
        set_setting("photo", url_for("static", filename="uploads/" + name))
    elif url.startswith(("http://", "https://")):
        set_setting("photo", url)
    else:
        flash("Choose a file or paste an http(s) image URL.")
        return redirect(url_for("admin_dashboard"))
    flash("Home photo changed.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/customer/<int:uid>")
@admin_required
def admin_customer(uid):
    c = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not c:
        abort(404)
    orders = db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    return render_template("customer_history.html", c=c, orders=orders)


@app.route("/admin/club/send", methods=["POST"])
@admin_required
def admin_club_send():
    msg = request.form.get("message", "").strip()
    members = db().execute("SELECT user_id FROM club").fetchall()
    for m in members:
        notify(m["user_id"], "Club alert: " + msg)
    db().commit()
    flash(f"Alert sent to {len(members)} member(s).")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/club/<int:uid>/remove", methods=["POST"])
@admin_required
def admin_club_remove(uid):
    db().execute("DELETE FROM club WHERE user_id=?", (uid,))
    db().commit()
    return redirect(url_for("admin_dashboard"))


init_db()

if __name__ == "__main__":
    # host 0.0.0.0 lets other phones on the same Wi-Fi open http://YOUR-PHONE-IP:5000
    app.run(host="0.0.0.0", port=5000, debug=False)
