let deferredPrompt = null;
const INSTALL_KEY = "kerrie-pwa-installed";
const THEME_KEY = "kerrie-theme";
const FONT_KEY = "kerrie-font-family";
const FONT_SIZE_KEY = "kerrie-font-size";
const BRIGHTNESS_KEY = "kerrie-brightness";
const RATING_KEY = "kerrie-rating";

const themeClassMap = {
  "kerrie-orange": "theme-kerrie-orange",
  sunrise: "theme-sunrise",
  clean: "theme-clean",
  midnight: "theme-midnight",
  paper: "theme-paper",
  ocean: "theme-ocean",
  forest: "theme-forest",
  aurora: "theme-aurora",
  restyle: "theme-restyle",
};

const body = document.body;
const root = document.documentElement;

function installUiRefs() {
  return {
    banner: document.getElementById("installBanner"),
    installBtn: document.getElementById("installBtn"),
    installNowBtn: document.getElementById("installNowBtn"),
    dismissInstallBtn: document.getElementById("dismissInstallBtn"),
    menuInstallBtn: document.getElementById("menuInstallBtn"),
  };
}

function isInstalled() {
  return localStorage.getItem(INSTALL_KEY) === "1" || window.matchMedia?.("(display-mode: standalone)")?.matches === true || window.navigator.standalone === true;
}

function hideInstallBanner(reason = "") {
  const { banner, installBtn } = installUiRefs();
  if (banner) {
    banner.classList.add("is-hiding");
    banner.classList.add("hidden");
    setTimeout(() => {
      banner.hidden = true;
      banner.classList.remove("is-hiding");
    }, 180);
  }
  if (installBtn) installBtn.classList.add("hidden");
  if (reason === "installed") localStorage.setItem(INSTALL_KEY, "1");
}

function showInstallBanner() {
  if (isInstalled()) return;
  const { banner, installBtn } = installUiRefs();
  if (banner) {
    banner.classList.remove("hidden");
    banner.hidden = false;
    banner.classList.add("is-visible");
    window.clearTimeout(showInstallBanner._timer);
    showInstallBanner._timer = window.setTimeout(() => {
      if (!banner.hidden) hideInstallBanner();
    }, 6500);
  }
  if (installBtn) installBtn.classList.remove("hidden");
}

function promptInstall() {
  if (!deferredPrompt) {
    // No prompt available yet. Keep the banner ready for the next browser-supported moment.
    showInstallBanner();
    return;
  }
  deferredPrompt.prompt();
  deferredPrompt.userChoice.finally(() => {
    deferredPrompt = null;
    hideInstallBanner();
  });
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event;
  if (!isInstalled()) showInstallBanner();
});

window.addEventListener("appinstalled", () => {
  deferredPrompt = null;
  hideInstallBanner("installed");
});

// Install UI wiring
const refs = installUiRefs();
refs.installBtn?.addEventListener("click", promptInstall);
refs.installNowBtn?.addEventListener("click", promptInstall);
refs.menuInstallBtn?.addEventListener("click", promptInstall);
refs.dismissInstallBtn?.addEventListener("click", () => {
  localStorage.setItem(INSTALL_KEY, isInstalled() ? "1" : "0");
  hideInstallBanner();
});

if (!isInstalled()) {
  // Show briefly so people who already need it can catch it, but do not force it.
  window.setTimeout(() => {
    if (deferredPrompt) showInstallBanner();
  }, 1200);
}

// Swipe-to-dismiss for the top banner.
(function setupBannerSwipe() {
  const { banner } = installUiRefs();
  if (!banner) return;
  let startX = null;
  banner.style.touchAction = "pan-y";
  banner.addEventListener("pointerdown", (e) => {
    startX = e.clientX;
  });
  banner.addEventListener("pointerup", (e) => {
    if (startX === null) return;
    const delta = e.clientX - startX;
    startX = null;
    if (Math.abs(delta) > 80) hideInstallBanner();
  });
})();

async function renderSeats(tripId) {
  const seatGrid = document.getElementById("seatGrid");
  const selectedSeatsInput = document.getElementById("selectedSeatsInput");
  const tripMeta = document.getElementById("tripMeta");
  const farePill = document.getElementById("farePill");
  if (!seatGrid || !selectedSeatsInput) return;
  seatGrid.innerHTML = "<p class='muted'>Loading seats...</p>";

  try {
    const response = await fetch(`/api/trips/${tripId}/seats`);
    if (!response.ok) {
      seatGrid.innerHTML = "<p class='muted'>No seats found.</p>";
      return;
    }

    const data = await response.json();
    const trip = data.trip;
    const seats = data.seats || [];
    const selected = new Set((selectedSeatsInput.value || "").split(",").map((s) => s.trim()).filter(Boolean));

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
        button.classList.toggle("selected");
        const chosen = Array.from(seatGrid.querySelectorAll(".seat-btn.selected")).map((btn) => btn.textContent);
        selectedSeatsInput.value = chosen.join(",");
      });
      seatGrid.appendChild(button);
    });
  } catch (error) {
    seatGrid.innerHTML = "<p class='muted'>Unable to load seats right now.</p>";
  }
}

const tripSelect = document.getElementById("tripSelect");
if (tripSelect) {
  const load = () => renderSeats(tripSelect.value);
  tripSelect.addEventListener("change", load);
  load();
}

function showFlash(el) {
  if (!el) return;
  setTimeout(() => {
    el.style.transition = "opacity .3s ease, transform .3s ease";
    el.style.opacity = "0";
    el.style.transform = "translateY(-4px)";
  }, 5000);
}

document.querySelectorAll(".flash").forEach(showFlash);

function applyTheme(themeName) {
  Object.values(themeClassMap).forEach((themeClass) => body.classList.remove(themeClass));
  const mapped = themeClassMap[themeName] || themeClassMap["kerrie-orange"];
  body.classList.add(mapped);
  localStorage.setItem(THEME_KEY, themeName);
}

function applyFontFamily(fontValue) {
  root.style.setProperty("--ui-font-family", fontValue);
  localStorage.setItem(FONT_KEY, fontValue);
}

function applyFontSize(percent) {
  const scale = Math.max(90, Math.min(120, Number(percent) || 100)) / 100;
  root.style.setProperty("--ui-font-scale", String(scale));
  localStorage.setItem(FONT_SIZE_KEY, String(Math.round(scale * 100)));
}

function applyBrightness(level) {
  body.dataset.brightness = level;
  body.classList.remove("brightness-dim", "brightness-balanced", "brightness-bright");
  body.classList.add(`brightness-${level}`);
  localStorage.setItem(BRIGHTNESS_KEY, level);
}

// Restore saved display preferences.
const savedTheme = localStorage.getItem(THEME_KEY);
if (savedTheme) applyTheme(savedTheme);
const savedFont = localStorage.getItem(FONT_KEY);
if (savedFont) applyFontFamily(savedFont);
const savedFontSize = localStorage.getItem(FONT_SIZE_KEY);
if (savedFontSize) applyFontSize(savedFontSize);
const savedBrightness = localStorage.getItem(BRIGHTNESS_KEY);
if (savedBrightness) applyBrightness(savedBrightness);

// Theme controls.
document.querySelectorAll("[data-theme-choice]").forEach((button) => {
  button.addEventListener("click", () => applyTheme(button.dataset.themeChoice));
});

document.querySelectorAll("[data-font-select]").forEach((select) => {
  select.addEventListener("change", () => applyFontFamily(select.value));
  if (savedFont) select.value = savedFont;
});

document.querySelectorAll("[data-font-size]").forEach((range) => {
  range.addEventListener("input", () => applyFontSize(range.value));
  if (savedFontSize) range.value = savedFontSize;
});

document.querySelectorAll("[data-brightness-choice]").forEach((button) => {
  button.addEventListener("click", () => applyBrightness(button.dataset.brightnessChoice));
});

// Open/close dialog helpers.
document.querySelectorAll("[data-open-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    const dialog = document.getElementById(button.dataset.openDialog);
    if (dialog?.showModal) dialog.showModal();
  });
});

document.querySelectorAll("dialog.modal-panel").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

// Rating widgets.
document.querySelectorAll("[data-rating-widget]").forEach((widget) => {
  const feedback = widget.querySelector("[data-rating-feedback]");
  const stars = [...widget.querySelectorAll("[data-rating-value]")];
  const saved = Number(localStorage.getItem(RATING_KEY) || 0);
  const setRating = (value) => {
    stars.forEach((star) => star.classList.toggle("is-selected", Number(star.dataset.ratingValue) <= value));
    if (feedback) feedback.textContent = value ? `Thanks — you rated this ${value}/5.` : "Tap a star to leave a quick rating.";
    localStorage.setItem(RATING_KEY, String(value));
  };
  stars.forEach((star) => {
    star.addEventListener("click", () => setRating(Number(star.dataset.ratingValue)));
  });
  setRating(saved);
});
