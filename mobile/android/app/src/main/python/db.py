"""KHOLA database helpers (SQLite)."""
import sqlite3
from datetime import datetime

from flask import g

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, phone TEXT,
  email TEXT UNIQUE, password_hash TEXT, address TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, name TEXT,
  phone TEXT UNIQUE, pin_hash TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT, stock INTEGER);
CREATE TABLE IF NOT EXISTS sizes(id INTEGER PRIMARY KEY, product_id INTEGER,
  label TEXT, price INTEGER);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER, size_id INTEGER,
  product_id INTEGER, product_name TEXT, size_label TEXT, qty INTEGER, total INTEGER,
  channel TEXT, reference TEXT, status TEXT, deducted INTEGER DEFAULT 0,
  refund_requested INTEGER DEFAULT 0, created TEXT, verified_at TEXT);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, user_id INTEGER,
  message TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS club(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, created TEXT);
CREATE TABLE IF NOT EXISTS pin_resets(id INTEGER PRIMARY KEY, admin_id INTEGER,
  token TEXT, created TEXT, used INTEGER DEFAULT 0);
"""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def db():
    """One database connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    """Create tables and first-time stock if the database is new."""
    con = sqlite3.connect(config.DB_PATH)
    con.executescript(SCHEMA)
    # upgrade older databases (made before verified_at existed)
    cols = [r[1] for r in con.execute("PRAGMA table_info(orders)")]
    if "verified_at" not in cols:
        con.execute("ALTER TABLE orders ADD COLUMN verified_at TEXT")
    defaults = {"brand": config.DEFAULT_BRAND, "motto": config.DEFAULT_MOTTO,
                "photo": config.DEFAULT_PHOTO}
    for k, v in defaults.items():
        con.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    if not con.execute("SELECT 1 FROM products").fetchone():
        for name, stock, sizes in config.SEED_PRODUCTS:
            pid = con.execute("INSERT INTO products(name,stock) VALUES(?,?)", (name, stock)).lastrowid
            for label, price in sizes:
                con.execute("INSERT INTO sizes(product_id,label,price) VALUES(?,?,?)", (pid, label, price))
    con.commit()
    con.close()


def setting(key):
    r = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else ""


def set_setting(key, value):
    db().execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, value))
    db().commit()


def notify(user_id, message):
    """Add a notification to a customer's dashboard (caller commits)."""
    db().execute("INSERT INTO notifications(user_id,message,created) VALUES(?,?,?)",
                 (user_id, message, now()))


def order_no(oid):
    return f"Chichi {oid:04d}"


def sales_summary():
    """Numbers for the admin Today's Sales card."""
    d = db()
    day = datetime.now().strftime("%Y-%m-%d") + "%"

    def one(sql, *args):
        return dict(d.execute(sql, args).fetchone())

    verified = one("SELECT COUNT(*) n, COALESCE(SUM(qty),0) birds, COALESCE(SUM(total),0) money "
                   "FROM orders WHERE status='APPROVED' AND COALESCE(verified_at, created) LIKE ?", day)
    placed = one("SELECT COUNT(*) n FROM orders WHERE created LIKE ?", day)
    waiting = one("SELECT COUNT(*) n, COALESCE(SUM(total),0) money FROM orders "
                  "WHERE status='WAITING' AND reference IS NOT NULL")
    refunds = one("SELECT COUNT(*) n FROM orders WHERE refund_requested=1 AND status!='REFUNDED'")
    alltime = one("SELECT COALESCE(SUM(total),0) money, COALESCE(SUM(qty),0) birds "
                  "FROM orders WHERE status='APPROVED'")
    return dict(verified=verified, placed=placed["n"], waiting=waiting,
                refunds=refunds["n"], alltime=alltime)
