let currentOrderData = null;

document.addEventListener("DOMContentLoaded", () => {
    const trackBtn = document.getElementById("trackBtn");
    const cancelBtn = document.getElementById("cancelBtn");

    if (trackBtn) {
        trackBtn.addEventListener("click", fetchStatus);
    }
    if (cancelBtn) {
        cancelBtn.addEventListener("click", cancelScheduledOrder);
    }
});

async function fetchStatus() {
    const orderIdInput = document.getElementById("orderIdInput");
    const resultEl = document.getElementById("trackResult");
    const cancelBtn = document.getElementById("cancelBtn");
    const msgEl = document.getElementById("cancelMessage");

    const orderId = (orderIdInput.value || "").trim();

    msgEl.textContent = "";
    msgEl.style.color = "";
    cancelBtn.style.display = "none";

    if (!orderId) {
        resultEl.textContent = "Please enter an Order ID.";
        return;
    }

    try {
        const resp = await fetch(`/api/order/${encodeURIComponent(orderId)}`);
        const data = await resp.json();

        if (!resp.ok) {
            resultEl.textContent = "Error: " + (data.error || "Could not fetch order");
            return;
        }

        currentOrderData = data;

        const lines = [];
        lines.push(`Order ID: ${data.order_id}`);
        lines.push(`Customer: ${data.customer_name}`);
        lines.push(`SRN: ${data.srn || "-"}`);
        lines.push(`Status: ${data.status}`);
        lines.push(`Pickup type: ${data.is_scheduled ? "Scheduled" : "Now"}`);
        lines.push(`Pickup time: ${data.scheduled_for || "-"}`);
        lines.push(`Pickup code: ${data.completion_code || "-"}`);
        lines.push("");
        lines.push("Items:");
        (data.items || []).forEach(it => {
            lines.push(
                `- ${it.display_name} (${it.size}) x${it.qty} | ₹${it.line_total}`
            );
        });
        lines.push("");
        lines.push(`Total: ₹${data.total}`);

        resultEl.textContent = lines.join("\n");

        // Show cancel button only for scheduled, non-final orders
        const statusLower = (data.status || "").toLowerCase();
        if (data.is_scheduled && !["completed", "cancelled"].includes(statusLower)) {
            cancelBtn.style.display = "inline-block";
            cancelBtn.disabled = false;
        } else {
            cancelBtn.style.display = "none";
        }

    } catch (err) {
        console.error(err);
        resultEl.textContent = "Request failed while fetching status.";
    }
}

async function cancelScheduledOrder() {
    if (!currentOrderData) return;

    const orderId = currentOrderData.order_id;
    const cancelBtn = document.getElementById("cancelBtn");
    const msgEl = document.getElementById("cancelMessage");
    const resultEl = document.getElementById("trackResult");

    cancelBtn.disabled = true;
    msgEl.style.color = "#374151";
    msgEl.textContent = "Processing cancellation...";

    try {
        const resp = await fetch("/api/cancel_order", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ order_id: orderId })
        });

        const data = await resp.json();

        if (!resp.ok) {
            msgEl.style.color = "#b91c1c";
            msgEl.textContent = data.error || "Unable to cancel this order.";
            cancelBtn.disabled = false;
            return;
        }

        // Success + refund message
        msgEl.style.color = "#065f46";
        msgEl.textContent =
            data.refund_message ||
            "Refund initiated and will be reaching you within 2 working days.";

        resultEl.textContent += `\n\nStatus updated: cancelled.`;

        // Hide cancel button after success
        cancelBtn.style.display = "none";

        // Redirect to refund page after short delay
        setTimeout(() => {
            window.location.href = `/refund/${encodeURIComponent(orderId)}`;
        }, 1200);

    } catch (err) {
        console.error(err);
        msgEl.style.color = "#b91c1c";
        msgEl.textContent = "Cancellation request failed. Please try again.";
        cancelBtn.disabled = false;
    }
}
