(() => {
  const tree = document.querySelector('#location-tree');
  const results = document.querySelector('#location-results');
  const error = document.querySelector('#location-error');
  if (!tree || !results) return;
  const storageKey = 'tema-location-tree-v2';
  let request = null;
  const save = () => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({
        top: tree.scrollTop,
        nodes: [...tree.querySelectorAll('details[data-node]')].map(node => [node.dataset.node, node.open]),
      }));
    } catch (_) { /* Navigation also works when storage is unavailable. */ }
  };
  const highlight = () => {
    const selected = results.dataset.selected;
    tree.querySelectorAll('a[data-location]').forEach(link => {
      if (link.dataset.location === selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  try {
    const state = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
    if (state && Array.isArray(state.nodes)) {
      const nodes = new Map(state.nodes);
      tree.querySelectorAll('details[data-node]').forEach(node => {
        if (nodes.has(node.dataset.node)) node.open = nodes.get(node.dataset.node);
      });
      tree.scrollTop = state.top || 0;
    }
  } catch (_) { /* Ignore stale saved state. */ }
  highlight();
  tree.addEventListener('scroll', save, {passive: true});
  tree.addEventListener('toggle', save, true);
  window.addEventListener('pagehide', save);

  async function load(url, push) {
    request?.abort();
    const controller = new AbortController();
    request = controller;
    results.setAttribute('aria-busy', 'true');
    error.hidden = true;
    save();
    try {
      const response = await fetch(url, {signal: controller.signal});
      if (!response.ok) throw new Error('Unable to load');
      const document = new DOMParser().parseFromString(await response.text(), 'text/html');
      const incoming = document.querySelector('#location-results');
      if (!incoming) throw new Error('Missing results');
      if (controller.signal.aborted) return;
      results.innerHTML = incoming.innerHTML;
      results.dataset.selected = incoming.dataset.selected;
      results.scrollTop = 0;
      if (push) history.pushState(null, '', url);
      highlight();
    } catch (exception) {
      if (exception.name !== 'AbortError') error.hidden = false;
    } finally {
      if (request === controller) results.removeAttribute('aria-busy');
    }
  }
  tree.addEventListener('click', event => {
    const link = event.target.closest('a[data-location]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    load(link.href, true);
  });
  window.addEventListener('popstate', () => load(window.location.href, false));
})();
