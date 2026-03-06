/* =============================================
   買取価格表 フィルター機能
   ============================================= */

document.addEventListener('DOMContentLoaded', function () {
  // --- Kind (model type) filter ---
  const kindCheckboxes = document.querySelectorAll('.kind-cb');
  kindCheckboxes.forEach(cb => {
    cb.addEventListener('change', applyKindFilter);
  });

  // --- Shop (store) filter ---
  const shopCheckboxes = document.querySelectorAll('.shop-cb');
  shopCheckboxes.forEach(cb => {
    cb.addEventListener('change', applyShopFilter);
  });

  // --- Reset button ---
  const resetBtn = document.getElementById('btn-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', resetFilters);
  }

  function applyKindFilter() {
    const checkedKinds = new Set();
    kindCheckboxes.forEach(cb => {
      if (cb.checked) checkedKinds.add(cb.value);
    });

    const rows = document.querySelectorAll('table.price-table tbody tr[data-kind]');
    rows.forEach(row => {
      const kind = row.getAttribute('data-kind');
      if (checkedKinds.has(kind)) {
        row.classList.remove('hidden-row');
      } else {
        row.classList.add('hidden-row');
      }
    });
  }

  function applyShopFilter() {
    const checkedShops = new Set();
    shopCheckboxes.forEach(cb => {
      if (cb.checked) checkedShops.add(cb.value);
    });

    // Get all shop columns (th and td with data-shop attribute)
    const table = document.querySelector('table.price-table');
    if (!table) return;

    // Find column indices for shops in header rows
    const headerRows = table.querySelectorAll('thead tr');
    const shopColMap = {}; // shop-id -> array of column indices

    headerRows.forEach(row => {
      const cells = row.querySelectorAll('th, td');
      cells.forEach(cell => {
        const shopId = cell.getAttribute('data-shop');
        if (shopId) {
          if (checkedShops.has(shopId)) {
            cell.classList.remove('hidden-col');
          } else {
            cell.classList.add('hidden-col');
          }
        }
      });
    });

    // Body rows
    const bodyRows = table.querySelectorAll('tbody tr');
    bodyRows.forEach(row => {
      const cells = row.querySelectorAll('td, th');
      cells.forEach(cell => {
        const shopId = cell.getAttribute('data-shop');
        if (shopId) {
          if (checkedShops.has(shopId)) {
            cell.classList.remove('hidden-col');
          } else {
            cell.classList.add('hidden-col');
          }
        }
      });
    });
  }

  function resetFilters() {
    // Check all checkboxes
    document.querySelectorAll('.kind-cb, .shop-cb').forEach(cb => {
      cb.checked = true;
    });
    // Show all rows
    document.querySelectorAll('table.price-table tbody tr.hidden-row').forEach(row => {
      row.classList.remove('hidden-row');
    });
    // Show all columns
    document.querySelectorAll('.hidden-col').forEach(el => {
      el.classList.remove('hidden-col');
    });
  }

  // --- Margin Sort ---
  let sortAsc = false; // default: descending (highest margin first)
  const sortBtn = document.getElementById('sort-margin');
  if (sortBtn) {
    sortBtn.addEventListener('click', sortByMargin);
  }

  // --- Margin % Sort ---
  let sortPctAsc = false;
  const sortPctBtn = document.getElementById('sort-pct');
  if (sortPctBtn) {
    sortPctBtn.addEventListener('click', sortByPct);
  }

  function parseMarginValue(text) {
    // Remove commas, whitespace, and parse as number. "+22,020" -> 22020, "-8,980" -> -8980
    const cleaned = text.replace(/,/g, '').replace(/\s/g, '').replace(/\+/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : num;
  }

  function sortByMargin() {
    const table = document.querySelector('table.price-table');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll('tr[data-kind]'));

    rows.sort((a, b) => {
      const aCell = a.querySelector('.left-sticky-5');
      const bCell = b.querySelector('.left-sticky-5');
      const aVal = aCell ? parseMarginValue(aCell.textContent) : 0;
      const bVal = bCell ? parseMarginValue(bCell.textContent) : 0;
      return sortAsc ? aVal - bVal : bVal - aVal;
    });

    // Re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));

    // Toggle direction and update indicator
    sortAsc = !sortAsc;
    sortBtn.innerHTML = '差益<br>(利益順) ' + (sortAsc ? '▲' : '▼');
  }

  function sortByPct() {
    const table = document.querySelector('table.price-table');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll('tr[data-kind]'));

    rows.sort((a, b) => {
      const aCell = a.querySelector('.left-sticky-6');
      const bCell = b.querySelector('.left-sticky-6');
      const aVal = aCell ? parseFloat(aCell.getAttribute('data-pct') || '0') : 0;
      const bVal = bCell ? parseFloat(bCell.getAttribute('data-pct') || '0') : 0;
      return sortPctAsc ? aVal - bVal : bVal - aVal;
    });

    rows.forEach(row => tbody.appendChild(row));

    sortPctAsc = !sortPctAsc;
    sortPctBtn.innerHTML = '差益率<br>(%) ' + (sortPctAsc ? '▲' : '▼');
  }
});
