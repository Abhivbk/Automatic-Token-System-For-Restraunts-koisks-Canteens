// refund.js
document.addEventListener("DOMContentLoaded", () => {
    const backBtn = document.getElementById("backToTrackBtn");

    if (backBtn) {
        backBtn.addEventListener("click", () => {
            // Go back to track page
            window.location.href = "/track";
        });
    }
});
