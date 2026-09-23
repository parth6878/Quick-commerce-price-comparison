/**
 * QuickCompare — sticker market price board
 * Search client for the Blinkit / Zepto / Amazon Fresh comparison engine.
 */

(function () {
  'use strict';

  const state = {
    query: 'milk',
    deals: [],
    singleStoreItems: [],
    summary: {},
    cached: false,
    selectedStoreFilter: 'all',
    selectedSort: 'savings_desc'
  };

  const STORE_ORDER = ['Blinkit', 'Zepto', 'Amazon'];

  const elements = {
    form: document.getElementById('search-form'),
    queryInput: document.getElementById('query-input'),
    clearBtn: document.getElementById('clear-btn'),
    btnModeLive: document.getElementById('btn-mode-live'),
    refreshCheckbox: document.getElementById('refresh-cache'),
    chips: document.querySelectorAll('.chip'),
    loadingState: document.getElementById('loading-state'),
    loadingStepText: document.getElementById('loading-step-text'),
    errorState: document.getElementById('error-state'),
    errorTitle: document.getElementById('error-title'),
    errorMessage: document.getElementById('error-message'),
    btnRetry: document.getElementById('btn-retry'),
    resultsSection: document.getElementById('results-section'),
    dealsGrid: document.getElementById('deals-grid'),
    noDealsBox: document.getElementById('no-deals-box'),
    currentQueryTag: document.getElementById('current-query-tag'),
    cacheIndicator: document.getElementById('cache-indicator'),
    storeFilter: document.getElementById('store-filter'),
    sortSelect: document.getElementById('sort-select'),
    kpiMatched: document.getElementById('kpi-matched-count'),
    kpiMaxSavings: document.getElementById('kpi-max-savings'),
    kpiTotalProducts: document.getElementById('kpi-total-products'),
    accordionToggle: document.getElementById('accordion-toggle'),
    singleStoreAccordion: document.querySelector('.single-store-accordion'),
    singleStoreBody: document.getElementById('single-store-body'),
    singleStoreCount: document.getElementById('single-store-count'),
    singleStoreGrid: document.getElementById('single-store-grid'),
    modal: document.getElementById('product-modal'),
    modalClose: document.getElementById('modal-close'),
    modalTitle: document.getElementById('modal-title'),
    modalBrand: document.getElementById('modal-brand'),
    modalBody: document.getElementById('modal-body'),
    themeToggle: document.getElementById('btn-theme-toggle'),
    toastContainer: document.getElementById('toast-container')
  };

  /* ------------------------------------------------------------------ *
   * Small DOM + imagery helpers
   * ------------------------------------------------------------------ */

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function placeholderUrl(name, store) {
    return `/api/image?name=${encodeURIComponent(name || 'Product')}` +
           `&store=${encodeURIComponent(store || '')}`;
  }

  // <img> with lazy loading and a guaranteed generated-art fallback.
  function makeImage(src, name, store, className, alt) {
    const img = el('img', className);
    img.loading = 'lazy';
    img.decoding = 'async';
    img.alt = alt || name || 'Product image';
    // Remote store CDNs may reject requests carrying a referrer; local
    // /static/img photos don't care either way.
    img.referrerPolicy = 'no-referrer';
    img.src = src || placeholderUrl(name, store);
    img.addEventListener('error', function onErr() {
      img.removeEventListener('error', onErr);
      img.src = placeholderUrl(name, store);
    });
    return img;
  }

  function storeClass(storeName) {
    return String(storeName || '').toLowerCase().replace(/\s+/g, '');
  }

  function hasPrice(detail) {
    return detail && detail.price !== null && detail.price !== undefined;
  }

  /* ------------------------------------------------------------------ *
   * Init & events
   * ------------------------------------------------------------------ */

  function init() {
    bindEvents();
    elements.queryInput.value = 'milk';
    executeSearch('milk', false);
  }

  function bindEvents() {
    elements.form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = elements.queryInput.value.trim();
      if (q) executeSearch(q, elements.refreshCheckbox.checked);
    });

    elements.queryInput.addEventListener('input', () => {
      elements.clearBtn.style.display = elements.queryInput.value.trim() ? 'block' : 'none';
    });

    elements.clearBtn.addEventListener('click', () => {
      elements.queryInput.value = '';
      elements.clearBtn.style.display = 'none';
      elements.queryInput.focus();
    });

    elements.btnModeLive.addEventListener('click', () => runWithMode());

    elements.chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        const queryVal = chip.getAttribute('data-query');
        elements.queryInput.value = queryVal;
        elements.clearBtn.style.display = 'block';
        executeSearch(queryVal, elements.refreshCheckbox.checked);
      });
    });

    elements.storeFilter.addEventListener('change', (e) => {
      state.selectedStoreFilter = e.target.value;
      applyFilterAndSort();
    });

    elements.sortSelect.addEventListener('change', (e) => {
      state.selectedSort = e.target.value;
      applyFilterAndSort();
    });

    elements.accordionToggle.addEventListener('click', () => {
      const isOpen = elements.singleStoreBody.style.display === 'block';
      elements.singleStoreBody.style.display = isOpen ? 'none' : 'block';
      elements.singleStoreAccordion.classList.toggle('open', !isOpen);
    });

    elements.modalClose.addEventListener('click', closeModal);
    elements.modal.addEventListener('click', (e) => {
      if (e.target === elements.modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });

    elements.btnRetry.addEventListener('click', () => {
      const q = elements.queryInput.value.trim() || state.query || 'milk';
      elements.queryInput.value = q;
      executeSearch(q, false);
    });

    elements.themeToggle.addEventListener('click', () => {
      document.body.classList.toggle('ink-mode');
      const isInk = document.body.classList.contains('ink-mode');
      showToast(isInk ? 'Board flipped to ink mode ◑' : 'Board flipped back to paper mode ◑', 'info');
    });
  }

  function runWithMode() {
    const q = elements.queryInput.value.trim() || state.query || 'milk';
    elements.queryInput.value = q;
    executeSearch(q, elements.refreshCheckbox.checked);
  }

  /* ------------------------------------------------------------------ *
   * Search
   * ------------------------------------------------------------------ */

  async function executeSearch(query, bypassCache) {
    state.query = query;
    showLoading();

    const endpoint = `/api/compare?query=${encodeURIComponent(query)}` +
      `&refresh=${bypassCache ? 'true' : 'false'}`;

    try {
      const response = await fetch(endpoint);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned ${response.status}`);
      }

      const data = await response.json();
      state.deals = data.matched_deals || [];
      state.singleStoreItems = data.single_store_items || [];
      state.summary = data.summary || {};
      state.cached = !!data.cached;

      renderResults();
      showResults();

      if (state.deals.length > 0) {
        showToast(`${state.deals.length} matched deals for “${query}” 🎉`, 'success');
      } else {
        showToast(`No overlaps for “${query}” — check single-store items.`, 'warning');
      }
    } catch (err) {
      console.error('Fetch error:', err);
      showError('Search failed', err.message || 'Cannot reach the comparison server.');
    }
  }

  /* ------------------------------------------------------------------ *
   * Visual states
   * ------------------------------------------------------------------ */

  function showLoading() {
    if (elements.loadingStepText) {
      elements.loadingStepText.textContent = 'Scraping Blinkit, Zepto and Amazon Fresh concurrently…';
    }
    elements.loadingState.style.display = 'block';
    elements.errorState.style.display = 'none';
    elements.resultsSection.style.display = 'none';
  }

  function showError(title, msg) {
    elements.loadingState.style.display = 'none';
    elements.errorState.style.display = 'block';
    elements.resultsSection.style.display = 'none';
    elements.errorTitle.textContent = title;
    elements.errorMessage.textContent = msg;
  }

  function showResults() {
    elements.loadingState.style.display = 'none';
    elements.errorState.style.display = 'none';
    elements.resultsSection.style.display = 'block';
  }

  /* ------------------------------------------------------------------ *
   * Render pipeline
   * ------------------------------------------------------------------ */

  function renderResults() {
    elements.currentQueryTag.textContent = `query: ${state.query}`;
    elements.cacheIndicator.style.display = state.cached ? 'inline-block' : 'none';

    elements.kpiMatched.textContent = state.summary.total_matched || state.deals.length;
    elements.kpiTotalProducts.textContent =
      state.summary.total_products || (state.deals.length + state.singleStoreItems.length);

    let maxSav = 0;
    state.deals.forEach((d) => { if (d.savings && d.savings > maxSav) maxSav = d.savings; });
    elements.kpiMaxSavings.textContent = maxSav > 0 ? `₹${maxSav}` : '₹0';

    applyFilterAndSort();
    renderSingleStoreItems();
  }

  function applyFilterAndSort() {
    let filtered = [...state.deals];

    if (state.selectedStoreFilter !== 'all') {
      filtered = filtered.filter((deal) =>
        deal.prices && Object.keys(deal.prices).includes(state.selectedStoreFilter)
      );
    }

    filtered.sort((a, b) => {
      switch (state.selectedSort) {
        case 'savings_desc': return (b.savings || 0) - (a.savings || 0);
        case 'savings_pct_desc': return (b.savings_percentage || 0) - (a.savings_percentage || 0);
        case 'price_asc': return (a.lowest_price || 0) - (b.lowest_price || 0);
        case 'stores_desc': return (b.store_count || 0) - (a.store_count || 0);
        default: return 0;
      }
    });

    renderDeals(filtered);
  }

  // ---- Deal cards -----------------------------------------------------

  function buildReceiptRow(deal, storeName, detail) {
    const isWinner = !!(deal.cheapest_stores && deal.cheapest_stores.includes(storeName));
    const row = el('div', 'receipt-row' + (isWinner ? ' is-winner' : ''));

    row.appendChild(makeImage(
      detail.image_url,
      detail.raw_name || deal.canonical_name,
      storeName,
      'row-thumb',
      storeName
    ));

    row.appendChild(el('span', `store-name ${storeClass(storeName)}`, storeName));
    row.appendChild(el('span', 'leader'));

    if (isWinner) row.appendChild(el('span', 'stamp', 'cheapest'));

    row.appendChild(el('span', 'row-price', `₹${detail.price}`));
    if (detail.unit_price) row.appendChild(el('span', 'row-unit', `₹${detail.unit_price}/unit`));

    return row;
  }

  function renderDeals(deals) {
    elements.dealsGrid.innerHTML = '';

    if (!deals || deals.length === 0) {
      elements.noDealsBox.style.display = 'block';
      return;
    }
    elements.noDealsBox.style.display = 'none';

    deals.forEach((deal) => {
      const card = el('article', 'deal-card');

      // Shot
      const shot = el('div', 'card-shot');
      shot.appendChild(makeImage(
        deal.representative_image,
        deal.canonical_name,
        '',
        '',
        deal.canonical_name
      ));

      const hasSavings = deal.savings && deal.savings > 0;
      shot.appendChild(el(
        'span',
        'sticker sticker-count',
        `${deal.store_count}/3 stores`
      ));
      shot.appendChild(el(
        'span',
        'sticker sticker-save' + (hasSavings ? '' : ' is-flat'),
        hasSavings ? `save ₹${deal.savings}` : 'same price'
      ));
      card.appendChild(shot);

      // Body
      const body = el('div', 'card-body');

      const tags = el('div', 'tag-row');
      if (deal.brand) tags.appendChild(el('span', 'tag tag-brand', deal.brand));
      if (deal.quantity) tags.appendChild(el('span', 'tag tag-qty', deal.quantity));
      body.appendChild(tags);

      const title = el('h3', 'card-title', deal.canonical_name);
      title.title = deal.canonical_name;
      body.appendChild(title);

      const receipt = el('div', 'receipt');
      STORE_ORDER.forEach((storeName) => {
        const detail = deal.store_details ? deal.store_details[storeName] : null;
        if (!hasPrice(detail)) return;
        receipt.appendChild(buildReceiptRow(deal, storeName, detail));
      });
      body.appendChild(receipt);
      card.appendChild(body);

      // Total / actions
      const total = el('div', 'card-total');
      const text = el('span', 'total-text');
      text.append('cheapest at ');
      text.appendChild(el('strong', null, deal.cheapest_store));
      total.appendChild(text);

      const btn = el('button', 'btn-mini', 'breakdown');
      btn.type = 'button';
      btn.addEventListener('click', () => openModal(deal));
      total.appendChild(btn);

      card.appendChild(total);
      elements.dealsGrid.appendChild(card);
    });
  }

  // ---- Single-store items --------------------------------------------

  function renderSingleStoreItems() {
    const items = state.singleStoreItems || [];
    elements.singleStoreCount.textContent = items.length;
    elements.singleStoreGrid.innerHTML = '';

    if (items.length === 0) {
      elements.singleStoreGrid.appendChild(
        el('div', 'no-items-note', 'No single-store items found.')
      );
      return;
    }

    items.forEach((item) => {
      const storeName = Object.keys(item.prices || {})[0] || 'Store';
      const detail = (item.store_details && item.store_details[storeName]) || {};

      const card = el('div', 'finding');
      card.appendChild(makeImage(
        item.representative_image || detail.image_url,
        item.canonical_name,
        storeName,
        '',
        item.canonical_name
      ));

      const info = el('div', 'finding-info');
      const title = el('div', 'finding-title', item.canonical_name);
      title.title = item.canonical_name;
      info.appendChild(title);

      const meta = el('div', 'finding-meta');
      meta.appendChild(el('span', `store-name ${storeClass(storeName)}`, storeName));
      meta.appendChild(el('span', 'finding-price', `₹${item.lowest_price}`));
      info.appendChild(meta);

      card.appendChild(info);
      elements.singleStoreGrid.appendChild(card);
    });
  }

  // ---- Modal ----------------------------------------------------------

  function openModal(deal) {
    elements.modalTitle.textContent = deal.canonical_name;
    elements.modalBrand.textContent = deal.brand || 'Quick Commerce';
    elements.modalBody.innerHTML = '';

    // Summary: polaroid photo + receipt lines
    const summary = el('div', 'modal-summary');

    const polaroid = el('div', 'polaroid');
    polaroid.appendChild(makeImage(
      deal.representative_image,
      deal.canonical_name,
      '',
      '',
      deal.canonical_name
    ));
    summary.appendChild(polaroid);

    const text = el('div', 'modal-summary-text');

    const packLine = el('div', 'summary-line');
    packLine.append('Pack size: ');
    packLine.appendChild(el('strong', null, deal.quantity || 'standard'));
    text.appendChild(packLine);

    const bestLine = el('div', 'summary-line');
    bestLine.append('Lowest: ');
    bestLine.appendChild(el('span', 'best', `₹${deal.lowest_price}`));
    bestLine.append(' at ');
    bestLine.appendChild(el('strong', null, deal.cheapest_store));
    text.appendChild(bestLine);

    const gapLine = el('div', 'summary-line');
    gapLine.textContent = deal.savings > 0
      ? `Gap ₹${deal.savings} (${deal.savings_percentage}%) between cheapest and priciest store.`
      : 'Identical pricing across every store.';
    text.appendChild(gapLine);

    summary.appendChild(text);
    elements.modalBody.appendChild(summary);

    // Per-store breakdown cards
    const breakdown = el('div', 'breakdown');
    STORE_ORDER.forEach((storeName) => {
      const info = deal.store_details ? deal.store_details[storeName] : null;
      if (!info) return;

      const isWinner = !!(deal.cheapest_stores && deal.cheapest_stores.includes(storeName));
      const item = el('div', 'breakdown-item' + (isWinner ? ' is-winner' : ''));
      item.appendChild(makeImage(
        info.image_url,
        info.raw_name || deal.canonical_name,
        storeName,
        '',
        storeName
      ));

      const details = el('div', 'breakdown-info');

      const top = el('div', 'breakdown-top');
      top.appendChild(el('span', `store-name ${storeClass(storeName)}`, storeName));
      if (isWinner) top.appendChild(el('span', 'stamp', 'cheapest'));
      details.appendChild(top);

      const title = el('div', 'breakdown-title', info.raw_name || '-');
      title.title = info.raw_name || '';
      details.appendChild(title);

      const price = el('div', 'breakdown-price', `₹${info.price}`);
      details.appendChild(price);
      if (info.unit_price) {
        details.appendChild(el('div', 'breakdown-unit', `₹${info.unit_price} / unit`));
      }

      item.appendChild(details);
      breakdown.appendChild(item);
    });

    elements.modalBody.appendChild(breakdown);
    elements.modal.style.display = 'flex';
  }

  function closeModal() {
    elements.modal.style.display = 'none';
  }

  // ---- Toasts ---------------------------------------------------------

  function showToast(message, type = 'info') {
    const toast = el('div', `toast ${type}`, message);
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(-24px)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 260);
    }, 3600);
  }

  // Kickstart
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
