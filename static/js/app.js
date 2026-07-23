if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

document.addEventListener('click', (event) => {
  const opener = event.target.closest('[data-open-dialog]');
  if (opener) {
    const parentDialog = opener.closest('dialog');
    if (parentDialog && typeof parentDialog.close === 'function' && parentDialog.open) {
      parentDialog.close();
    }
    const dialog = document.getElementById(opener.dataset.openDialog);
    if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
  }
  const dialog = event.target.closest('dialog');
  if (dialog && event.target.matches('dialog')) {
    dialog.close();
  }
});

const installReminder = document.getElementById('installReminder');
const installNowBtn = document.getElementById('installNowBtn');
const menuInstallBtn = document.getElementById('menuInstallBtn');
const dismissInstallBtn = document.getElementById('dismissInstallBtn');
let deferredPrompt = null;
let installVisible = false;
let reminderTimer = null;
let reminderCooldown = 0;
const REMINDER_INTERVAL_MS = 45000;
const REMINDER_HIDE_MS = 8000;
const REMINDER_SUPPRESS_MS = 60000;

function syncInstallButtons(enabled) {
  [installNowBtn, menuInstallBtn].forEach((btn) => {
    if (!btn) return;
    btn.disabled = !enabled;
    btn.setAttribute('aria-disabled', enabled ? 'false' : 'true');
  });
}

function isInstalledApp() {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}

function hideInstallReminder(permanent = false) {
  installVisible = false;
  if (installReminder) installReminder.hidden = true;
  if (permanent) {
    reminderCooldown = Date.now() + REMINDER_SUPPRESS_MS;
  }
}

function showInstallReminder() {
  if (!installReminder || isInstalledApp()) return;
  if (!deferredPrompt) return;
  if (Date.now() < reminderCooldown) return;
  installVisible = true;
  installReminder.hidden = false;
  window.clearTimeout(reminderTimer);
  reminderTimer = window.setTimeout(() => hideInstallReminder(), REMINDER_HIDE_MS);
}

async function promptInstall() {
  if (!deferredPrompt) {
    showInstallReminder();
    return;
  }
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  hideInstallReminder(true);
}

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  deferredPrompt = event;
  syncInstallButtons(true);
  showInstallReminder();
});

window.addEventListener('appinstalled', () => {
  deferredPrompt = null;
  syncInstallButtons(false);
  hideInstallReminder(true);
});

syncInstallButtons(false);
installNowBtn?.addEventListener('click', promptInstall);
menuInstallBtn?.addEventListener('click', promptInstall);
dismissInstallBtn?.addEventListener('click', () => hideInstallReminder(true));

window.addEventListener('load', () => {
  window.setInterval(() => {
    if (!installVisible) showInstallReminder();
  }, REMINDER_INTERVAL_MS);
  if (!isInstalledApp()) {
    window.setTimeout(showInstallReminder, 6000);
  }
});

async function renderSeats(tripId) {
  const seatGrid = document.getElementById('seatGrid');
  const selectedSeatsInput = document.getElementById('selectedSeatsInput');
  const tripMeta = document.getElementById('tripMeta');
  const farePill = document.getElementById('farePill');
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
  const selected = new Set((selectedSeatsInput.value || '').split(',').map(s => s.trim()).filter(Boolean));

  if (data.queue_locked || data.can_book === false) {
    seatGrid.innerHTML = "<p class='muted'>This vehicle is waiting in the posting queue. Please book the current available vehicle first.</p>";
    selectedSeatsInput.value = '';
    if (farePill) farePill.textContent = `KSh ${trip.fare_per_seat || 0}`;
    return;
  }

  if (tripMeta) {
    tripMeta.innerHTML = `
      <strong>${trip.route_name}</strong>
      <p>${trip.vehicle_name} • ${trip.vehicle_type} • ${trip.total_seats} seats</p>
      <small>${trip.departure_date}${trip.departure_time ? ' • ' + trip.departure_time : ''}</small>
    `;
  }
  if (farePill) farePill.textContent = `KSh ${trip.fare_per_seat || 0}`;

  seatGrid.innerHTML = '';
  seats.forEach((seat) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'seat-btn' + (seat.taken ? ' taken' : '');
    button.textContent = seat.label;
    if (selected.has(String(seat.label))) button.classList.add('selected');
    button.disabled = seat.taken;
    button.addEventListener('click', () => {
      if (button.classList.contains('selected')) {
        button.classList.remove('selected');
      } else {
        button.classList.add('selected');
      }
      const chosen = Array.from(seatGrid.querySelectorAll('.seat-btn.selected')).map(btn => btn.textContent);
      selectedSeatsInput.value = chosen.join(',');
    });
    seatGrid.appendChild(button);
  });
}

const tripSelect = document.getElementById('tripSelect');
if (tripSelect) {
  const load = () => renderSeats(tripSelect.value);
  tripSelect.addEventListener('change', load);
  load();
}

document.querySelectorAll('.flash').forEach((el) => {
  setTimeout(() => {
    el.style.transition = 'opacity .3s ease, transform .3s ease';
    el.style.opacity = '0';
    el.style.transform = 'translateY(-4px)';
  }, 5000);
});

const THEME_KEY = 'kerrie-theme';
const FONT_KEY = 'kerrie-font-family';
const FONT_SIZE_KEY = 'kerrie-font-size';
const BRIGHTNESS_KEY = 'kerrie-brightness';
const themeButtons = document.querySelectorAll('[data-theme-choice]');
const fontSelect = document.querySelector('[data-font-select]');
const fontSizeInput = document.querySelector('[data-font-size]');

function applyTheme(themeName) {
  const themes = ['theme-kerrie-orange', 'theme-sunrise', 'theme-clean', 'theme-midnight', 'theme-paper', 'theme-ocean', 'theme-forest', 'theme-aurora', 'theme-restyle'];
  themes.forEach((theme) => document.body.classList.remove(theme));
  document.body.classList.add(`theme-${themeName}`);
  localStorage.setItem(THEME_KEY, themeName);
}

function applyFontFamily(fontValue) {
  document.documentElement.style.setProperty('--app-font-family', fontValue);
  if (fontSelect) fontSelect.value = fontValue;
  localStorage.setItem(FONT_KEY, fontValue);
}

function applyFontSize(percent) {
  const value = Math.max(90, Math.min(120, Number(percent) || 100));
  document.documentElement.style.setProperty('--app-font-scale', String(value / 100));
  if (fontSizeInput) fontSizeInput.value = String(value);
  localStorage.setItem(FONT_SIZE_KEY, String(value));
}

function applyBrightness(level) {
  const allowed = ['dim', 'balanced', 'bright'];
  const value = allowed.includes(level) ? level : 'balanced';
  document.body.classList.remove('brightness-dim', 'brightness-balanced', 'brightness-bright');
  document.body.classList.add(`brightness-${value}`);
  localStorage.setItem(BRIGHTNESS_KEY, value);
}

const savedTheme = localStorage.getItem(THEME_KEY);
if (savedTheme) applyTheme(savedTheme);
const savedFont = localStorage.getItem(FONT_KEY);
if (savedFont) applyFontFamily(savedFont);
const savedFontSize = localStorage.getItem(FONT_SIZE_KEY);
if (savedFontSize) applyFontSize(savedFontSize);
const savedBrightness = localStorage.getItem(BRIGHTNESS_KEY);
if (savedBrightness) applyBrightness(savedBrightness);

themeButtons.forEach((button) => {
  button.addEventListener('click', () => applyTheme(button.dataset.themeChoice));
});

fontSelect?.addEventListener('change', () => applyFontFamily(fontSelect.value));
fontSizeInput?.addEventListener('input', () => applyFontSize(fontSizeInput.value));

document.querySelectorAll('[data-brightness-choice]').forEach((button) => {
  button.addEventListener('click', () => applyBrightness(button.dataset.brightnessChoice));
});

const ratingWidgets = document.querySelectorAll('[data-rating-widget]');
if (ratingWidgets.length) {
  const storageKey = 'kerrie-public-rating';
  const saved = Number(localStorage.getItem(storageKey) || 0);

  ratingWidgets.forEach((ratingWidget) => {
    const stars = Array.from(ratingWidget.querySelectorAll('[data-rating-value]'));
    const feedback = ratingWidget.querySelector('[data-rating-feedback]');

    const paint = (value) => {
      stars.forEach((button) => {
        const active = Number(button.dataset.ratingValue) <= value;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-checked', active ? 'true' : 'false');
      });
      if (feedback) {
        feedback.textContent = value ? `Thanks for rating ${value} star${value > 1 ? 's' : ''}.` : 'Tap a star to leave a quick rating.';
      }
    };

    paint(saved);
    stars.forEach((button) => {
      button.addEventListener('click', () => {
        const value = Number(button.dataset.ratingValue);
        localStorage.setItem(storageKey, String(value));
        paint(value);
      });
    });
  });
}

