
let deferredPrompt = null;
const installBtn = document.getElementById("installBtn");

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  installBtn?.classList.remove("hidden");
});

window.addEventListener("appinstalled", () => {
  deferredPrompt = null;
  installBtn?.classList.add("hidden");
});

installBtn?.addEventListener("click", async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  installBtn.classList.add("hidden");
});

async function renderSeats(tripId) {
  const seatGrid = document.getElementById("seatGrid");
  const selectedSeatsInput = document.getElementById("selectedSeatsInput");
  const tripMeta = document.getElementById("tripMeta");
  const farePill = document.getElementById("farePill");
  if (!seatGrid || !selectedSeatsInput) return;
  seatGrid.innerHTML = "<p class='muted'>Loading seats...</p>";

  const response = await fetch(`/api/trips/${tripId}/seats`);
  if (!response.ok) {
    seatGrid.innerHTML = "<p class='muted'>No seats found.</p>";
    return;
  }

  const data = await response.json();
  const trip = data.trip;
  const seats = data.seats || [];
  const selected = new Set((selectedSeatsInput.value || "").split(",").map(s => s.trim()).filter(Boolean));

  if (data.queue_locked || data.can_book === false) {
    seatGrid.innerHTML = "<p class='muted'>This vehicle is waiting in the posting queue. Please book the current available vehicle first.</p>";
    selectedSeatsInput.value = "";
    if (farePill) farePill.textContent = `KSh ${trip.fare_per_seat || 0}`;
    return;
  }

  if (tripMeta) {
    tripMeta.innerHTML = `
      <strong>${trip.route_name}</strong>
      <p>${trip.vehicle_name} • ${trip.vehicle_type} • ${trip.total_seats} seats</p>
      <small>${trip.departure_date}${trip.departure_time ? " • " + trip.departure_time : ""}</small>
    `;
  }
  if (farePill) farePill.textContent = `KSh ${trip.fare_per_seat || 0}`;

  seatGrid.innerHTML = "";
  seats.forEach((seat) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "seat-btn" + (seat.taken ? " taken" : "");
    button.textContent = seat.label;
    if (selected.has(String(seat.label))) button.classList.add("selected");
    button.disabled = seat.taken;
    button.addEventListener("click", () => {
      if (button.classList.contains("selected")) {
        button.classList.remove("selected");
      } else {
        button.classList.add("selected");
      }
      const chosen = Array.from(seatGrid.querySelectorAll(".seat-btn.selected")).map(btn => btn.textContent);
      selectedSeatsInput.value = chosen.join(",");
    });
    seatGrid.appendChild(button);
  });
}

const tripSelect = document.getElementById("tripSelect");
if (tripSelect) {
  const load = () => renderSeats(tripSelect.value);
  tripSelect.addEventListener("change", load);
  load();
}

document.querySelectorAll(".flash").forEach((el) => {
  setTimeout(() => {
    el.style.transition = "opacity .3s ease, transform .3s ease";
    el.style.opacity = "0";
    el.style.transform = "translateY(-4px)";
  }, 5000);
});
