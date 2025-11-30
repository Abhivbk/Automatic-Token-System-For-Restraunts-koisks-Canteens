# db.py
import sqlite3
from flask import g

DB_PATH = "coffee.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT,
            srn TEXT,
            status TEXT,
            total INTEGER,
            currency TEXT,
            created_at TEXT,
            completion_code TEXT,
            is_scheduled INTEGER,
            scheduled_for TEXT,
            completion_queue INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            drink_key TEXT,
            display_name TEXT,
            size TEXT,
            qty INTEGER,
            sugar_level TEXT,
            milk_type TEXT,
            extra_shot INTEGER,
            price_per_cup INTEGER,
            line_total INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        )
    """)

    conn.commit()
    conn.close()


def serialize_order(order_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    o = cur.fetchone()
    if not o:
        conn.close()
        return None

    cur.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items_rows = cur.fetchall()
    conn.close()

    items = []
    for r in items_rows:
        items.append({
            "drink_key": r["drink_key"],
            "display_name": r["display_name"],
            "size": r["size"],
            "qty": r["qty"],
            "sugar_level": r["sugar_level"],
            "milk_type": r["milk_type"],
            "extra_shot": bool(r["extra_shot"]),
            "price_per_cup": r["price_per_cup"],
            "line_total": r["line_total"],
        })

    order = {
        "order_id": o["order_id"],
        "customer_name": o["customer_name"],
        "srn": o["srn"],
        "status": o["status"],
        "total": o["total"],
        "currency": o["currency"],
        "created_at": o["created_at"],
        "completion_code": o["completion_code"],
        "completion_queue": o["completion_queue"],
        "is_scheduled": bool(o["is_scheduled"]),
        "scheduled_for": o["scheduled_for"],
        "items": items,
    }
    return order
