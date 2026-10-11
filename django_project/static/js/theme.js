/* Apply the saved appearance before styles paint, without requiring storage access. */
(() => {
  const root = document.documentElement;
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = null;
  let toggle = null;
  try {
    const saved = window.localStorage.getItem('arcave-theme');
    if (saved === 'light' || saved === 'dark') preference = saved;
  } catch (_) { /* Private browsing can disable storage. */ }

  function apply(theme) {
    root.dataset.theme = theme;
    if (toggle) toggle.setAttribute('aria-checked', String(theme === 'dark'));
  }
  apply(preference || (system.matches ? 'dark' : 'light'));
  system.addEventListener('change', (event) => {
    if (!preference) apply(event.matches ? 'dark' : 'light');
  });
  document.addEventListener('DOMContentLoaded', () => {
    toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    toggle.hidden = false;
    apply(root.dataset.theme);
    toggle.addEventListener('click', () => {
      preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
      apply(preference);
      try { window.localStorage.setItem('arcave-theme', preference); }
      catch (_) { /* The theme still works for this page. */ }
    });
  });
})();
