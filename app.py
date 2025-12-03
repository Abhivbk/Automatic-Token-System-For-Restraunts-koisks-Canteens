import streamlit as st
import sqlite3
import uuid
import random
import time
from datetime import datetime
import pandas as pd
import razorpay
from streamlit.components.v1 import html

# --- CONFIGURATION ---
DB_PATH = "coffee.db"
RAZORPAY_KEY_ID = "rzp_test_RmlHmXyKcUNH23"
RAZORPAY_KEY_SECRET = "SC0ooNKNmGZkljuPll1auJgg"

# --- FIX: THREAD SAFETY ---
@st.cache_resource
def get_razorpay_client():
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

client = get_razorpay_client()

# --- MENU DATA ---
MENU = {
    "Hot Beverages": [
        {"name": "Black Coffee (Espresso/Americano)", "small": 30, "regular": 45},
        {"name": "Café Mocha", "small": None, "regular": 45},
        {"name": "Cappuccino", "small": 30, "regular": 45},
        {"name": "Flavoured Cappuccino", "small": 40, "regular": 70},
        {"name": "Café Latte", "small": None, "regular": 45},
        {"name": "Chai (Masala/Ginger/Cardamom)", "small": 35, "regular": 45},
        {"name": "Garam Chai / Lemon Tea / Green Tea", "small": 30, "regular": 45},
        {"name": "Boost / Horlicks", "small": 35, "regular": 55},
    ],
    "Cold Beverages": [
        {"name": "Chocolate Moksha", "price": 50},
        {"name": "Cold Coffee (Classic/Hazelnut/Caramel)", "price": 80},
        {"name": "Milkshakes (Classic Chocolate/Berry)", "price": 80},
    ],
    "Ready to Drink": [
        {"name": "Storm Energy Drink", "price": 0},
        {"name": "Cold Coffee (Bottle)", "price": 0},
        {"name": "Rush Fruit Juice", "price": 0},
        {"name": "Buttermilk", "price": 0},
        {"name": "Tender Coconut Water", "price": 0},
    ]
}

# --- DATABASE FUNCTIONS ---
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            srn TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    # Note: Status will default to 'pending'
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT,
            srn TEXT,
            status TEXT,
            total INTEGER,
            created_at TEXT,
            completion_code TEXT,
            is_scheduled INTEGER,
            scheduled_for TEXT,
            razorpay_order_id TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            drink_name TEXT,
            size TEXT,
            qty INTEGER,
            addons TEXT,
            line_total INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        )
    """)
    conn.commit()
    conn.close()

def check_user_exists(srn):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE srn = ?", (srn,))
    data = c.fetchone()
    conn.close()
    return data is not None

def create_user(srn, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO users (srn, password) VALUES (?, ?)", (srn, password))
    conn.commit()
    conn.close()

def verify_user(srn, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE srn = ?", (srn,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == password:
        return True
    return False

def place_order(name, srn, items, scheduled_for=None):
    if not items: return None, None, None, None

    order_id = str(uuid.uuid4())[:8]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    completion_code = f"{random.randint(0, 9999):04d}"
    is_scheduled = 1 if scheduled_for else 0
    scheduled_time = scheduled_for if scheduled_for else created_at
    total = sum(item['line_total'] for item in items)

    # RAZORPAY
    amount_paise = total * 100
    try:
        razorpay_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": order_id,
            "payment_capture": 1
        })
        razorpay_order_id = razorpay_order['id']
    except Exception as e:
        st.error(f"Error connecting to Payment Gateway: {e}")
        return None, None, None, None

    conn = get_connection()
    c = conn.cursor()
    # ORDER IS CREATED WITH STATUS 'pending'
    c.execute("""
        INSERT INTO orders (order_id, customer_name, srn, status, total, created_at, completion_code, is_scheduled, scheduled_for, razorpay_order_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, name, srn, "pending", total, created_at, completion_code, is_scheduled, scheduled_time, razorpay_order_id))

    for item in items:
        c.execute("""
            INSERT INTO order_items (order_id, drink_name, size, qty, addons, line_total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, item['name'], item['size'], item['qty'], item['addons'], item['line_total']))
    conn.commit()
    conn.close()

    return order_id, completion_code, razorpay_order_id, total

def get_orders_by_srn(srn):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM orders WHERE srn = ? AND status NOT IN ('completed', 'cancelled') ORDER BY created_at DESC", conn, params=(srn,))
    conn.close()
    return df

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="CCD Ordering",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.set_page_config(
    page_title="CCD Ordering",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="expanded"
)

def main():
    init_db()
    if 'payment_step' not in st.session_state:
        st.session_state.payment_step = False
        st.session_state.order_details = {}

    st.image("https://th.bing.com/th?q=Cafe+Coffee+Day+Logo.png&w=120&h=120&c=1&rs=1&qlt=70&o=7&cb=1&dpr=1.3&pid=InlineBlock&rm=3&mkt=en-IN&cc=IN&setlang=en&adlt=strict&t=1&mw=247", width=100)
    st.title("CCD Xpress Order")

    tab1, tab2 = st.tabs(["☕ Place Order", "🔍 Track Status"])

    # --- TAB 1: ORDERING ---
    with tab1:
        if not st.session_state.payment_step:
            with st.form("order_form"):
                st.subheader("Customer Details")
                c1, c2 = st.columns(2)
                name = c1.text_input("Name")
                srn = c2.text_input("SRN (Required)").strip().upper()

                st.info("ℹ️ **First time?** Enter a password below to create your secure account.")
                password = st.text_input("Password (Required for new users)", type="password")

                st.write("---")
                st.subheader("Pickup Time")
                schedule_type = st.radio("When do you want it?", ["Now", "Schedule for Later"], horizontal=True)
                scheduled_time = None
                if schedule_type == "Schedule for Later":
                    scheduled_time_val = st.time_input("Select Pickup Time")
                    scheduled_time = f"{datetime.now().strftime('%Y-%m-%d')} {scheduled_time_val}"

                cart_items = []
                st.write("---")
                st.subheader("Menu Selection")

                st.markdown("##### 🔥 Hot Beverages")
                for item in MENU["Hot Beverages"]:
                    with st.expander(f"{item['name']}"):
                        c_opt, c_qty = st.columns([3, 1])
                        options = []
                        if item.get('small'): options.append(f"Small (₹{item['small']})")
                        if item.get('regular'): options.append(f"Regular (₹{item['regular']})")

                        if options:
                            selection = c_opt.radio(f"Size for {item['name']}", options, horizontal=True)
                            addons = c_opt.multiselect(f"Add-ons for {item['name']}", ["Extra Sugar", "Less Sugar", "Strong", "No Sugar"])
                            addon_str = ", ".join(addons) if addons else "None"
                        else:
                            selection = None
                            addon_str = "None"

                        qty = c_qty.number_input(f"Qty", 0, 10, key=f"q_{item['name']}")

                        if qty > 0 and selection:
                            price = int(selection.split('₹')[1].replace(')', ''))
                            size_name = selection.split(' ')[0]
                            cart_items.append({
                                "name": item['name'],
                                "size": size_name,
                                "qty": qty,
                                "addons": addon_str,
                                "line_total": price * qty
                            })

                st.markdown("##### ❄️ Cold Beverages")
                for item in MENU["Cold Beverages"]:
                     with st.expander(f"{item['name']} - ₹{item['price']}"):
                        c_opt, c_qty = st.columns([3, 1])
                        addons = c_opt.multiselect(f"Add-ons", ["Extra Ice", "No Ice", "Less Sugar"], key=f"add_{item['name']}")
                        qty = c_qty.number_input("Qty", 0, 10, key=f"qc_{item['name']}")

                        if qty > 0:
                            cart_items.append({
                                "name": item['name'],
                                "size": "Std",
                                "qty": qty,
                                "addons": ", ".join(addons) if addons else "None",
                                "line_total": item['price'] * qty
                            })

                st.divider()
                submitted = st.form_submit_button("Proceed to Payment", type="primary")

                if submitted:
                    if not srn or not name:
                        st.error("Name and SRN are required!")
                    elif not cart_items:
                        st.error("Cart is empty!")
                    else:
                        user_exists = check_user_exists(srn)
                        if not user_exists:
                            if not password:
                                st.error("⚠️ **First Time Order:** You must set a password.")
                                st.stop()
                            else:
                                create_user(srn, password)

                        oid, code, rzp_oid, total = place_order(name, srn, cart_items, scheduled_time)

                        if oid:
                            st.session_state.payment_step = True
                            st.session_state.order_details = {
                                "oid": oid,
                                "code": code,
                                "rzp_id": rzp_oid,
                                "total": total,
                                "items": cart_items,
                                "customer": name
                            }
                            st.rerun()

        # --- PAYMENT SUMMARY STEP ---
        else:
            details = st.session_state.order_details

            st.success("✅ Order Created! Select payment method.")

            customer_name = details.get('customer', 'Valued Customer')

            with st.container(border=True):
                st.subheader("🧾 Order Summary")
                st.write(f"**Customer:** {customer_name}")
                st.write(f"**Order ID:** {details['oid']}")
                st.divider()
                for item in details['items']:
                    st.write(f"• {item['qty']}x {item['name']} ({item['size']}) - ₹{item['line_total']}")
                st.divider()
                st.markdown(f"### Total: ₹{details['total']}")

            st.write("---")

            # --- PAY AT COUNTER BUTTON ---
            c_later, c_or = st.columns([2, 1])
            with c_later:
                if st.button("✨ Pay at Counter (Cash)", type="secondary", use_container_width=True):
                    # We DO NOT update status here. It remains 'pending'.
                    # This allows the Admin to see it as a normal Pending order.
                    st.session_state.payment_step = False
                    st.session_state.order_details = {}
                    st.balloons()
                    st.success("Order confirmed! Please pay cash at the counter.")
                    time.sleep(2)
                    st.rerun()

            st.caption("OR Pay via Online")

            # --- RAZORPAY HTML ---
            payment_button_html = f"""
            <html>
            <head>
            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <style>
                .pay-btn-container {{
                    display: flex;
                    justify-content: center;
                    margin-top: 10px;
                }}
                button#rzp-button1 {{
                    background-color: #FF4B4B; 
                    color: white; 
                    padding: 14px 28px; 
                    border: none; 
                    border-radius: 8px; 
                    cursor: pointer; 
                    font-size: 20px; 
                    font-weight: bold;
                    width: 100%;
                    max-width: 300px;
                    transition: background-color 0.3s;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                button#rzp-button1:hover {{
                    background-color: #ff3333;
                }}
            </style>
            </head>
            <body>
                <div class="pay-btn-container">
                    <button id="rzp-button1">Pay Now ₹{details['total']}</button>
                </div>
                
                <script>
                var options = {{
                    "key": "{RAZORPAY_KEY_ID}",
                    "amount": "{details['total'] * 100}",
                    "currency": "INR",
                    "name": "CCD Xpress",
                    "description": "Order #{details['oid']}",
                    "image": "https://th.bing.com/th?q=Cafe+Coffee+Day+Logo.png&w=120&h=120&c=1",
                    "order_id": "{details['rzp_id']}",
                    "handler": function (response){{
                        alert("Payment Successful! Payment ID: " + response.razorpay_payment_id);
                    }},
                    "theme": {{
                        "color": "#FF4B4B"
                    }}
                }};
                
                var rzp1 = new Razorpay(options);
                
                document.getElementById('rzp-button1').onclick = function(e){{
                    rzp1.open();
                    e.preventDefault();
                }}
                </script>
            </body>
            </html>
            """
            html(payment_button_html, height=1000, scrolling=True)

            if st.button("Cancel & Go Back"):
                st.session_state.payment_step = False
                st.rerun()

    # --- TAB 2: TRACKING ---
    with tab2:
        st.subheader("My Active Orders")
        t_c1, t_c2 = st.columns(2)
        track_srn = t_c1.text_input("Enter SRN").strip().upper()
        track_pass = t_c2.text_input("Enter Password", type="password")

        if st.button("Check Status"):
            if track_srn and track_pass:
                if verify_user(track_srn, track_pass):
                    orders = get_orders_by_srn(track_srn)
                    if not orders.empty:
                        st.dataframe(orders[['order_id', 'status', 'completion_code', 'scheduled_for', 'total']], hide_index=True, use_container_width=True)
                    else:
                        st.info("No active orders found.")
                else:
                    st.error("❌ Invalid Password or SRN not registered.")
            else:
                st.warning("Please enter both SRN and Password.")

if __name__ == "__main__":
    main()
