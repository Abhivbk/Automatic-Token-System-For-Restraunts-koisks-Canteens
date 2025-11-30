# app.py
from flask import (
    Flask, jsonify, request, render_template,
    abort, session, redirect, url_for
)
from uuid import uuid4
import datetime as dt
from functools import wraps
import random  # for OTP

from db import init_db, get_db, serialize_order

app = Flask(__name__)
# ⚠️ Change this in real deployment
app.config["SECRET_KEY"] = "super-secret-change-this"

# -------------------------
# Menu & allowed statuses
# -------------------------
MENU = {
    "espresso": {
        "display_name": "Espresso",
        "prices": {"small": 80, "medium": 100, "large": 120}
    },
    "latte": {
        "display_name": "Latte",
        "prices": {"small": 120, "medium": 150, "large": 180}
    },
    "cappuccino": {
        "display_name": "Cappuccino",
        "prices": {"small": 130, "medium": 160, "large": 190}
    },
    "mocha": {
        "display_name": "Mocha",
        "prices": {"small": 140, "medium": 170, "large": 200}
    }
}

ALLOWED_STATUSES = {"pending", "preparing", "ready", "completed", "cancelled"}

# Demo admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


# -------------------------
# Admin auth helper
# -------------------------
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


# -------------------------
# Customer cancel helper
# -------------------------
def can_customer_cancel(order: dict) -> tuple[bool, str]:
    """
    Rules:
      - Only scheduled orders
      - Not already completed / cancelled
      - More than 10 minutes remaining before scheduled time
    """
    if not order.get("is_scheduled"):
        return False, "Only scheduled orders can be cancelled."

    status = (order.get("status") or "").lower()
    if status in ("completed", "cancelled"):
        return False, "Order is already completed or cancelled."

    sched_str = order.get("scheduled_for")
    if not sched_str:
        return False, "Order has no scheduled time."

    sched_dt = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            sched_dt = dt.datetime.strptime(sched_str, fmt)
            break
        except ValueError:
            continue

    if not sched_dt:
        return False, "Invalid scheduled time for this order."

    now = dt.datetime.now()
    delta_seconds = (sched_dt - now).total_seconds()
    if delta_seconds <= 600:
        return False, "Too close to pickup time to cancel (less than 10 minutes remaining)."

    return True, ""


# -------------------------
# Page routes
# -------------------------

@app.route("/")
def customer_page():
    return render_template("customer.html")


@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            next_url = request.args.get("next") or url_for("admin_page")
            return redirect(next_url)
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html", error=None)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/track")
def track_page():
    return render_template("track.html")


@app.route("/receipt/<order_id>")
def receipt_page(order_id):
    order = serialize_order(order_id)
    if not order:
        abort(404)
    is_admin = bool(session.get("is_admin"))
    return render_template("receipt.html", order=order, items=order["items"], is_admin=is_admin)


@app.route("/refund/<order_id>")
def refund_page(order_id):
    order = serialize_order(order_id)
    if not order:
        abort(404)
    if (order.get("status") or "").lower() != "cancelled":
        return "Refund page is only available for cancelled orders.", 400
    return render_template("refund.html", order=order)


# -------------------------
# API routes
# -------------------------

@app.route("/api/menu", methods=["GET"])
def api_menu():
    return jsonify({"menu": MENU})


@app.route("/api/order", methods=["POST"])
def api_place_order():
    data = request.get_json(force=True)
    customer_name = (data.get("customer_name") or "Guest").strip() or "Guest"
    srn = (data.get("srn") or "").strip()
    items_data = data.get("items", [])

    fulfillment = (data.get("fulfillment") or "now").lower()  # "now" or "schedule"
    scheduled_for_raw = (data.get("scheduled_for") or "").strip()

    if not items_data:
        return jsonify({"error": "No items in order"}), 400

    order_items = []
    total = 0

    for item in items_data:
        drink_key = item.get("name")

        # raw size from client (e.g. "small" or "regular")
        size_raw = (item.get("size") or "small").lower()
        size = size_raw          # stored/displayed
        price_size_key = "medium" if size_raw == "regular" else size_raw  # used in MENU

        qty = item.get("qty", 1)
        sugar_level = item.get("sugar_level") or "normal"
        milk_type = item.get("milk_type") or "regular"
        extra_shot = bool(item.get("extra_shot", False))

        if drink_key not in MENU:
            return jsonify({"error": f"Invalid drink: {drink_key}"}), 400
        if price_size_key not in MENU[drink_key]["prices"]:
            return jsonify({"error": f"Invalid size '{size}' for {drink_key}"}), 400

        try:
            qty = int(qty)
        except ValueError:
            return jsonify({"error": f"Invalid quantity for {drink_key}"}), 400
        if qty <= 0:
            continue

        price_per_cup = MENU[drink_key]["prices"][price_size_key]
        if extra_shot:
            price_per_cup += 20  # extra shot charge

        line_total = price_per_cup * qty
        total += line_total

        order_items.append({
            "drink_key": drink_key,
            "display_name": MENU[drink_key]["display_name"],
            "size": size,
            "qty": qty,
            "sugar_level": sugar_level,
            "milk_type": milk_type,
            "extra_shot": extra_shot,
            "price_per_cup": price_per_cup,
            "line_total": line_total,
        })

    if not order_items:
        return jsonify({"error": "All quantities are zero or invalid."}), 400

    order_id = str(uuid4())[:8]
    created_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 4-digit pickup code
    completion_code = f"{random.randint(0, 9999):04d}"

    # Scheduling logic
    if fulfillment == "schedule" and scheduled_for_raw:
        scheduled_for = scheduled_for_raw.replace("T", " ")
        is_scheduled = 1
    else:
        scheduled_for = created_at
        is_scheduled = 0

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO orders (
            order_id, customer_name, srn, status, total,
            currency, created_at, completion_code,
            is_scheduled, scheduled_for
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, customer_name, srn, "pending", total,
        "INR", created_at, completion_code,
        is_scheduled, scheduled_for
    ))

    for it in order_items:
        cur.execute("""
            INSERT INTO order_items
            (order_id, drink_key, display_name, size, qty, sugar_level, milk_type,
             extra_shot, price_per_cup, line_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id, it["drink_key"], it["display_name"], it["size"], it["qty"],
            it["sugar_level"], it["milk_type"], int(it["extra_shot"]),
            it["price_per_cup"], it["line_total"]
        ))

    conn.commit()
    conn.close()

    order = serialize_order(order_id)
    return jsonify(order), 201


@app.route("/api/order/<order_id>", methods=["GET"])
def api_get_order(order_id):
    order = serialize_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)


@app.route("/api/cancel_order", methods=["POST"])
def api_cancel_order():
    data = request.get_json(force=True)
    order_id = (data.get("order_id") or "").strip()

    if not order_id:
        return jsonify({"error": "Order ID is required."}), 400

    order = serialize_order(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    ok, reason = can_customer_cancel(order)
    if not ok:
        return jsonify({"error": reason}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET status = ? WHERE order_id = ?",
        ("cancelled", order_id)
    )
    conn.commit()
    conn.close()

    refund_msg = "Refund initiated and will be reaching you within 2 working days."

    return jsonify({
        "message": "Order cancelled successfully.",
        "refund_message": refund_msg,
        "order_id": order_id,
        "status": "cancelled"
    })


@app.route("/api/order/<order_id>/status", methods=["PATCH"])
@admin_required
def api_update_status(order_id):
    data = request.get_json(force=True)
    new_status = (data.get("status") or "").lower()

    if new_status not in ALLOWED_STATUSES:
        return jsonify({"error": f"Invalid status '{new_status}'"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT status, completion_code, completion_queue FROM orders WHERE order_id = ?",
        (order_id,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    current_status = row["status"]
    db_code = row["completion_code"]

    # Once completed, cannot be changed
    if current_status == "completed":
        conn.close()
        return jsonify({
            "error": "Order is already completed and cannot be modified."
        }), 403

    if new_status == "completed":
        provided_code = (data.get("completion_code") or "").strip()
        if not provided_code:
            conn.close()
            return jsonify({"error": "Pickup code is required"}), 400
        if provided_code != (db_code or ""):
            conn.close()
            return jsonify({"error": "Invalid pickup code"}), 400

        # Assign next queue number
        cur.execute("SELECT MAX(completion_queue) FROM orders")
        row_max = cur.fetchone()
        max_queue = row_max[0] if row_max and row_max[0] is not None else 0
        next_queue = max_queue + 1

        cur.execute(
            "UPDATE orders SET status = ?, completion_queue = ? WHERE order_id = ?",
            (new_status, next_queue, order_id)
        )
    else:
        cur.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (new_status, order_id)
        )

    conn.commit()
    conn.close()

    order = serialize_order(order_id)
    return jsonify(order)


@app.route("/api/orders", methods=["GET"])
@admin_required
def api_list_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT order_id
        FROM orders
        ORDER BY is_scheduled ASC, scheduled_for ASC, created_at DESC
    """)
    ids = [row["order_id"] for row in cur.fetchall()]
    conn.close()

    now = dt.datetime.now()
    orders = []

    for oid in ids:
        o = serialize_order(oid)
        if not o:
            continue

        due_soon = False
        if o["is_scheduled"] and o["scheduled_for"]:
            sched_str = o["scheduled_for"]
            sched_dt = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    sched_dt = dt.datetime.strptime(sched_str, fmt)
                    break
                except ValueError:
                    continue

            if sched_dt:
                delta = (sched_dt - now).total_seconds()
                if 0 <= delta <= 600:
                    due_soon = True

        o["due_soon"] = due_soon
        orders.append(o)

    return jsonify(orders)


if __name__ == "__main__":
    init_db()
    print("Coffee app running at http://127.0.0.1:5001  ☕")
    app.run(debug=True, host="127.0.0.1", port=5001)