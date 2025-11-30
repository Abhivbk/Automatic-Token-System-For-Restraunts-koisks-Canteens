document.addEventListener("DOMContentLoaded", () => {
    const activeBody = document.getElementById("ordersBody");
    const completedBody = document.getElementById("completedOrdersBody");
    const cancelledBody = document.getElementById("cancelledOrdersBody");

    function statusClass(status) {
        status = (status || "").toLowerCase();
        return "status-badge status-" + status;
    }

    function buildItemsHtml(items) {
        return (items || []).map(it => {
            const extras = [];
            if (it.sugar_level) extras.push("Sugar: " + it.sugar_level);
            if (it.milk_type) extras.push("Milk: " + it.milk_type);
            if (it.extra_shot) extras.push("Extra shot");
            return (
                it.display_name + " (" + it.size + ") x" + it.qty +
                " – ₹" + it.line_total +
                (extras.length ? " [" + extras.join(", ") + "]" : "")
            );
        }).join("<br>");
    }

    function renderActiveOrders(orders) {
        if (!orders.length) {
            activeBody.innerHTML =
                "<tr><td colspan='10'>No active orders.</td></tr>";
            return;
        }

        activeBody.innerHTML = "";
        orders.forEach(o => {
            const tr = document.createElement("tr");

            const itemsHtml = buildItemsHtml(o.items);
            const pickupType = o.is_scheduled ? "Scheduled" : "Now";

            // Only COMPLETED orders are locked in UI
            const isLocked = (o.status === "completed");

            tr.innerHTML = `
                <td><a href="/receipt/${o.order_id}" target="_blank">${o.order_id}</a></td>
                <td>${o.customer_name}</td>
                <td>${o.srn || "-"}</td>
                <td>${pickupType}</td>
                <td>${o.scheduled_for || "-"}</td>
                <td><span class="${statusClass(o.status)}">${o.status}</span></td>
                <td>${o.total}</td>
                <td>${o.created_at}</td>
                <td class="items">${itemsHtml}</td>
                <td>
                    <select class="status-select" ${isLocked ? "disabled" : ""}>
                        <option value="pending">pending</option>
                        <option value="preparing">preparing</option>
                        <option value="ready">ready</option>
                        <option value="completed">completed</option>
                        <option value="cancelled">cancelled</option>
                    </select>
                    <button class="update-btn" ${isLocked ? "disabled" : ""}>
                        Update
                    </button>
                </td>
            `;

            const select = tr.querySelector(".status-select");
            select.value = o.status;
            const btn = tr.querySelector(".update-btn");

            // highlight due-soon scheduled orders (within 10 mins)
            if (o.is_scheduled && o.due_soon && o.status !== "completed") {
                tr.classList.add("due-soon");
            }

            if (!isLocked) {
                btn.addEventListener("click", async () => {
                    const newStatus = select.value;
                    const body = { status: newStatus };

                    if (newStatus === "completed") {
                        const code = window.prompt(
                            "Enter pickup code from customer to complete this order:"
                        );
                        if (!code) {
                            alert("Pickup code is required.");
                            return;
                        }
                        body.completion_code = code.trim();
                    }

                    try {
                        const resp = await fetch(`/api/order/${o.order_id}/status`, {
                            method: "PATCH",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(body)
                        });
                        const data = await resp.json();
                        if (!resp.ok) {
                            alert("Error: " + (data.error || "Failed to update"));
                            return;
                        }
                        loadOrders();
                    } catch (err) {
                        console.error(err);
                        alert("Network error");
                    }
                });
            }

            activeBody.appendChild(tr);
        });
    }

    function renderCompletedOrders(orders) {
        if (!orders.length) {
            completedBody.innerHTML =
                "<tr><td colspan='9'>No completed orders yet.</td></tr>";
            return;
        }

        // sort by queue number ascending
        orders.sort((a, b) => {
            const qa = a.completion_queue || 0;
            const qb = b.completion_queue || 0;
            return qa - qb;
        });

        completedBody.innerHTML = "";
        orders.forEach(o => {
            const tr = document.createElement("tr");
            const itemsHtml = buildItemsHtml(o.items);
            const pickupType = o.is_scheduled ? "Scheduled" : "Now";
            const q = o.completion_queue || "-";

            tr.innerHTML = `
                <td>${q}</td>
                <td><a href="/receipt/${o.order_id}" target="_blank">${o.order_id}</a></td>
                <td>${o.customer_name}</td>
                <td>${o.srn || "-"}</td>
                <td>${pickupType}</td>
                <td>${o.scheduled_for || "-"}</td>
                <td>${o.total}</td>
                <td>${o.created_at}</td>
                <td class="items">${itemsHtml}</td>
            `;

            completedBody.appendChild(tr);
        });
    }

    function renderCancelledOrders(orders) {
        if (!orders.length) {
            cancelledBody.innerHTML =
                "<tr><td colspan='9'>No cancelled orders.</td></tr>";
            return;
        }

        cancelledBody.innerHTML = "";
        orders.forEach(o => {
            const tr = document.createElement("tr");
            const itemsHtml = buildItemsHtml(o.items);
            const pickupType = o.is_scheduled ? "Scheduled" : "Now";

            tr.innerHTML = `
                <td><a href="/receipt/${o.order_id}" target="_blank">${o.order_id}</a></td>
                <td>${o.customer_name}</td>
                <td>${o.srn || "-"}</td>
                <td>${pickupType}</td>
                <td>${o.scheduled_for || "-"}</td>
                <td><span class="${statusClass(o.status)}">${o.status}</span></td>
                <td>${o.total}</td>
                <td>${o.created_at}</td>
                <td class="items">${itemsHtml}</td>
            `;

            tr.classList.add("row-cancelled");
            cancelledBody.appendChild(tr);
        });
    }

    async function loadOrders() {
        try {
            const resp = await fetch("/api/orders");
            const data = await resp.json();

            // 💡 HARD SEGREGATION
            const active = data.filter(o =>
                o.status === "pending" ||
                o.status === "preparing" ||
                o.status === "ready"
            );
            const completed = data.filter(o => o.status === "completed");
            const cancelled = data.filter(o => o.status === "cancelled");

            renderActiveOrders(active);
            renderCompletedOrders(completed);
            renderCancelledOrders(cancelled);
        } catch (err) {
            console.error(err);
            activeBody.innerHTML =
                "<tr><td colspan='10'>Failed to load orders.</td></tr>";
            completedBody.innerHTML =
                "<tr><td colspan='9'>Failed to load completed orders.</td></tr>";
            cancelledBody.innerHTML =
                "<tr><td colspan='9'>Failed to load cancelled orders.</td></tr>";
        }
    }

    loadOrders();
    setInterval(loadOrders, 5000);
});
