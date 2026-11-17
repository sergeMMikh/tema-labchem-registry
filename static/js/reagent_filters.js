(() => {
  const lab = document.querySelector('#filter-lab');
  const sheet = document.querySelector('#filter-sheet');
  if (!lab || !sheet) return;

  const placeholder = sheet.options[0].cloneNode(true);
  const options = [...sheet.options].slice(1).map(option => option.cloneNode(true));

  function updateSheets(selected = '') {
    sheet.replaceChildren(
      placeholder.cloneNode(true),
      ...options.filter(option => option.dataset.lab === lab.value).map(option => option.cloneNode(true)),
    );
    sheet.value = selected;
    if (sheet.selectedIndex < 0) sheet.value = '';
    sheet.disabled = !lab.value || sheet.options.length === 1;
  }

  updateSheets(sheet.value);
  lab.addEventListener('change', () => updateSheets());
})();
