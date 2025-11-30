document.addEventListener("DOMContentLoaded", () => {

    loadMenu();

    const fulfillNow = document.getElementById("fulfillNow");
    const fulfillSchedule = document.getElementById("fulfillSchedule");

    // FIXED: Changed 'scheduleTime' to 'scheduleInput' to match HTML
    const scheduleInput = document.getElementById("scheduleInput");

    // Only run if elements exist to prevent crashes
    if (fulfillNow && fulfillSchedule && scheduleInput) {
        fulfillNow.addEventListener("change", () => scheduleInput.disabled = true);
        fulfillSchedule.addEventListener("change", () => scheduleInput.disabled = false);

        // Initialize state
        scheduleInput.disabled = fulfillNow.checked;
    }

    const placeOrderBtn = document.getElementById("placeOrderBtn");
    if (placeOrderBtn) {
        placeOrderBtn.addEventListener("click", placeOrder);
    }
});

async function loadMenu() {
    try {
        const resp = await fetch("/api/menu");
        const data = await resp.json();

        const tbody = document.getElementById("menuBody");
        tbody.innerHTML = "";

        Object.keys(data.menu).forEach(key => {
            const drink = data.menu[key];
            const tr = document.createElement("tr");

            // DRINK
            const tdName = document.createElement("td");
            tdName.innerText = drink.display_name;
            tr.appendChild(tdName);

            // PRICES
            const tdPrices = document.createElement("td");
            tdPrices.innerText = `Small: ₹${drink.prices.small} | Regular: ₹${drink.prices.medium}`;
            tr.appendChild(tdPrices);

            // SIZE
            const tdSize = document.createElement("td");
            const sizeSelect = document.createElement("select");
            sizeSelect.innerHTML = `
                <option value="small">Small</option>
                <option value="regular">Regular</option>
            `;
            sizeSelect.dataset.drinkKey = key;
            tdSize.appendChild(sizeSelect);
            tr.appendChild(tdSize);

            // QTY
            const tdQty = document.createElement("td");
            const qtyInput = document.createElement("input");
            qtyInput.type = "number";
            qtyInput.value = 0;
            qtyInput.min = 0;
            qtyInput.dataset.drinkKey = key;
            tdQty.appendChild(qtyInput);
            tr.appendChild(tdQty);

            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error loading menu:", err);
    }
}

async function placeOrder() {
    // FIXED: Changed IDs to match HTML
    const nameInput = document.getElementById("nameInput");
    const srnInput = document.getElementById("srnInput");
    const scheduleInput = document.getElementById("scheduleInput");
    const fulfillNowEl = document.getElementById("fulfillNow");

    // Get values safely
    const name = nameInput ? nameInput.value : "Guest";
    const srn = srnInput ? srnInput.value : "";
    const fulfillNow = fulfillNowEl ? fulfillNowEl.checked : true;
    const scheduleTime = scheduleInput ? scheduleInput.value : "";

    const items = [];

    document.querySelectorAll("#menuBody tr").forEach(row => {
        const sizeSelect = row.querySelector("select");
        const qtyInput = row.querySelector("input");

        const size = sizeSelect.value;
        const qty = parseInt(qtyInput.value);
        const key = sizeSelect.dataset.drinkKey;

        if (qty > 0) {
            items.push({
                name: key,
                size: size,
                qty: qty,
                sugar_level: "normal",    // default for backend
                milk_type: "regular",
                extra_shot: false
            });
        }
    });

    if (items.length === 0) {
        alert("Please select at least one drink");
        return;
    }

    const payload = {
        customer_name: name,
        srn: srn,
        items: items,
        fulfillment: fulfillNow ? "now" : "schedule"
    };

    if (!fulfillNow) {
        payload.scheduled_for = scheduleTime;
    }

    try {
        const resp = await fetch("/api/order", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        if (data.error) {
            alert("Error: " + data.error);
            return;
        }

        const code = data.pickup_code || data.completion_code;

        document.getElementById("orderResult").innerText = `
Order ID: ${data.order_id}
Pickup Code: ${code}
Total: ₹${data.total}
Status: ${data.status}
        `;
    } catch (err) {
        console.error("Order failed:", err);
        alert("Failed to place order.");
    }
}