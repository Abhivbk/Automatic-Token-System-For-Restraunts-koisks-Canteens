import streamlit as st
import sqlite3
import pandas as pd
import time

# --- CONFIG ---
DB_PATH = "coffee.db"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

st.set_page_config(page_title="CCD Admin", page_icon="🔒", layout="wide")

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def get_orders_data(status_list, sort_asc=True):
    conn = get_connection()
    order_type = "ASC" if sort_asc else "DESC"
    placeholders = ','.join(['?']*len(status_list))
    q = f"SELECT * FROM orders WHERE status IN ({placeholders}) ORDER BY created_at {order_type}"
    
    try:
        orders = pd.read_sql_query(q, conn, params=status_list)
    except Exception as e:
        conn.close()
        return []

    full_data = []
    for _, row in orders.iterrows():
        items = pd.read_sql_query("SELECT * FROM order_items WHERE order_id = ?", conn, params=(row['order_id'],))
        item_str = ""
        for _, item in items.iterrows():
            item_str += f"{item['qty']}x {item['drink_name']} ({item['size']}) [{item['addons']}]\n"
        
        full_data.append({
            "order_id": row['order_id'],
            "customer": f"{row['customer_name']} ({row['srn']})",
            "type": "Scheduled" if row['is_scheduled'] else "Now",
            "time": row['scheduled_for'],
            "items": item_str.strip(),
            "status": row['status'],
            "code": row['completion_code']
        })
    conn.close()
    return full_data

def update_status(order_id, new_status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

# --- AUTH ---
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "active"

if not st.session_state.admin_logged_in:
    st.title("Admin Login")
    c1, c2 = st.columns([1, 2])
    with c1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login", type="primary"):
            if u == ADMIN_USER and p == ADMIN_PASS:
                st.session_state.admin_logged_in = True
                st.rerun()
else:
    # --- HEADER ---
    c1, c2, c3 = st.columns([6, 2, 1])
    c1.title("👨‍🍳 Kitchen Display")
    
    if st.session_state.view_mode == "active":
        if c2.button("📜 View History"):
            st.session_state.view_mode = "history"
            st.rerun()
    else:
        if c2.button("🔥 View Active"):
            st.session_state.view_mode = "active"
            st.rerun()

    if c3.button("Logout"):
        st.session_state.admin_logged_in = False
        st.rerun()

    st.markdown("---")

    # === VIEW: ACTIVE ORDERS ===
    if st.session_state.view_mode == "active":
        if st.button("🔄 Refresh Data"):
            st.rerun()

        st.subheader("🔥 Active Orders")
        
        # Get data as list of dicts
        orders = get_orders_data(['pending', 'preparing', 'ready'])
        
        if not orders:
            st.info("No active orders.")
        else:
            # HEADER ROW
            h1, h2, h3, h4, h5 = st.columns([1, 2, 3, 2, 2])
            h1.markdown("**Order ID**")
            h2.markdown("**Customer**")
            h3.markdown("**Items**")
            h4.markdown("**Pickup Time**")
            h5.markdown("**Status Action**")
            st.divider()

            # DATA ROWS
            for order in orders:
                c1, c2, c3, c4, c5 = st.columns([1, 2, 3, 2, 2])
                
                c1.write(f"#{order['order_id']}")
                c2.write(order['customer'])
                c3.text(order['items']) # using text to preserve newlines
                c4.write(f"{order['type']}\n{order['time']}")
                
                # --- SMART BUTTON LOGIC ---
                status = order['status']
                oid = order['order_id']
                
                with c5:
                    if status == "pending":
                        # Button: Pending -> Preparing
                        if st.button("⏳ Pending", key=f"btn_{oid}", help="Click to start preparing"):
                            update_status(oid, "preparing")
                            st.rerun()
                            
                    elif status == "preparing":
                        # Button: Preparing -> Ready (Blue)
                        if st.button("👨‍🍳 Preparing", key=f"btn_{oid}", type="primary", help="Click when ready"):
                            update_status(oid, "ready")
                            st.rerun()
                            
                    elif status == "ready":
                        # Button: Ready -> Complete (Green)
                        # Instead of a simple button, we use a popover or expander for the code check
                        with st.popover("✅ Ready (Pickup)", use_container_width=True):
                            st.write(f"**Verify Code for Order #{oid}**")
                            code_input = st.text_input("Enter Customer Code", key=f"code_{oid}")
                            if st.button("Confirm Pickup", key=f"confirm_{oid}"):
                                if str(code_input).strip() == str(order['code']):
                                    update_status(oid, "completed")
                                    st.success("Completed!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("Wrong Code")
            
            st.divider()

    # === VIEW: HISTORY ===
    else:
        st.subheader("📜 Completed Order History")
        if st.button("🔄 Refresh History"):
            st.rerun()

        # Re-use the function but strictly for data display
        history_data = get_orders_data(['completed', 'cancelled'], sort_asc=False)
        
        if history_data:
            # Convert back to DF for easy table display since no buttons needed
            df = pd.DataFrame(history_data)
            st.dataframe(
                df[['order_id', 'time', 'customer', 'items', 'status']], 
                use_container_width=True, 
                hide_index=True,
                column_config={"items": st.column_config.TextColumn("Items", width="large")}
            )
        else:
            st.info("No history found.")