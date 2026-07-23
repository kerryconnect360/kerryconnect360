if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

const THEME_KEY = 'kerrie_theme';
const FONT_KEY = 'kerrie_font';

function applyLook(theme, font) {
  const body = document.body;
  if (!body) return;

  const themeClasses = ['theme-sunset', 'theme-midnight', 'theme-paper', 'theme-ocean', 'theme-forest', 'theme-restyle'];
  const fontClasses = ['font-system', 'font-sans', 'font-serif', 'font-rounded'];

  themeClasses.forEach((cls) => body.classList.remove(cls));
  fontClasses.forEach((cls) => body.classList.remove(cls));

  if (theme && themeClasses.includes(theme)) body.classList.add(theme);
  if (font && fontClasses.includes(font)) body.classList.add(font);
}

document.addEventListener('DOMContentLoaded', () => {
  const savedTheme = localStorage.getItem(THEME_KEY);
  const savedFont = localStorage.getItem(FONT_KEY);
  applyLook(savedTheme, savedFont);
});

document.addEventListener('click', (event) => {
  const opener = event.target.closest('[data-open-dialog]');
  if (opener) {
    const dialog = document.getElementById(opener.dataset.openDialog);
    if (dialog && typeof dialog.showModal === 'function') dialog.showModal();
  }

  const closer = event.target.closest('[data-close-dialog]');
  if (closer) {
    const dialog = document.getElementById(closer.dataset.closeDialog);
    if (dialog && typeof dialog.close === 'function') dialog.close();
  }

  const themeChoice = event.target.closest('[data-theme-choice]');
  if (themeChoice) {
    const nextTheme = themeChoice.dataset.themeChoice;
    localStorage.setItem(THEME_KEY, nextTheme);
    applyLook(nextTheme, localStorage.getItem(FONT_KEY));
  }

  const fontChoice = event.target.closest('[data-font-choice]');
  if (fontChoice) {
    const nextFont = fontChoice.dataset.fontChoice;
    localStorage.setItem(FONT_KEY, nextFont);
    applyLook(localStorage.getItem(THEME_KEY), nextFont);
  }

  const resetLook = event.target.closest('[data-reset-look]');
  if (resetLook) {
    localStorage.removeItem(THEME_KEY);
    localStorage.removeItem(FONT_KEY);
    window.location.reload();
  }

  const dialog = event.target.closest('dialog');
  if (dialog && event.target.matches('dialog')) {
    dialog.close();
  }
});
