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


const ratingWidget = document.querySelector("[data-rating-widget]");
if (ratingWidget) {
  const storageKey = "kerrie-public-rating";
  const stars = Array.from(ratingWidget.querySelectorAll("[data-rating-value]"));
  const feedback = ratingWidget.querySelector("[data-rating-feedback]");
  const saved = Number(localStorage.getItem(storageKey) || 0);

  const paint = (value) => {
    stars.forEach((button) => {
      const active = Number(button.dataset.ratingValue) <= value;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-checked", active ? "true" : "false");
    });
    if (feedback) {
      feedback.textContent = value ? `Thanks for rating ${value} star${value > 1 ? "s" : ""}.` : "Tap a star to leave a quick rating.";
    }
  };

  paint(saved);
  stars.forEach((button) => {
    button.addEventListener("click", () => {
      const value = Number(button.dataset.ratingValue);
      localStorage.setItem(storageKey, String(value));
      paint(value);
    });
  });
}
