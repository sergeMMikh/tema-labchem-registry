(() => {
  const drawer = document.querySelector('#quick-drawer');
  const backdrop = document.querySelector('#drawer-backdrop');
  let opener = null;
  if (!drawer || !backdrop) return;

  const close = () => {
    drawer.classList.remove('open');
    drawer.setAttribute('aria-hidden', 'true');
    backdrop.hidden = true;
    document.body.style.overflow = '';
    if (opener) opener.focus();
  };
  const open = async (row) => {
    opener = row;
    drawer.innerHTML = '<div class="empty"><p>Loading…</p></div>';
    drawer.classList.add('open');
    drawer.setAttribute('aria-hidden', 'false');
    backdrop.hidden = false;
    document.body.style.overflow = 'hidden';
    try {
      const response = await fetch(row.dataset.quickUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
      if (!response.ok) throw new Error('Request failed');
      drawer.innerHTML = await response.text();
      drawer.querySelector('.drawer-close')?.addEventListener('click', close);
      drawer.querySelector('.drawer-close')?.focus();
    } catch (_) {
      drawer.innerHTML = '<div class="empty"><h2>Unable to load</h2><button class="button drawer-close">Close</button></div>';
      drawer.querySelector('.drawer-close')?.addEventListener('click', close);
    }
  };
  document.querySelectorAll('[data-quick-url]').forEach((row) => {
    row.querySelector('.quick-open')?.addEventListener('click', (event) => { event.stopPropagation(); open(row); });
    row.addEventListener('keydown', (event) => { if (event.key === 'Enter' && event.target === row) open(row); });
  });
  backdrop.addEventListener('click', close);
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && drawer.classList.contains('open')) close(); });
})();
