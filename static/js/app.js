if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

document.addEventListener('click', (event) => {
  const opener = event.target.closest('[data-open-dialog]');
  if (opener) {
    const dialog = document.getElementById(opener.dataset.openDialog);
    if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
  }
  const dialog = event.target.closest('dialog');
  if (dialog && event.target.matches('dialog')) {
    dialog.close();
  }
});
