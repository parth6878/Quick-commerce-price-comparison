/**
 * QuickCompare Frontend Engine
 * Real-time asynchronous price comparison client
 */

(function () {
  'use strict';

  // State
  const state = {
    mode: 'demo', // 'demo' | 'live'
    query: 'milk',
    deals: [],
    singleStoreItems: [],
    summary: {},
    cached: false,
    selectedStoreFilter: 'all',
    selectedSort: 'savings_desc'
  };

  // DOM Elements
  const elements = {
    form: document.getElementById('search-form'),
    queryInput: document.getElementById('query-input'),
    clearBtn: document.getElementById('clear-btn'),
    btnModeDemo: document.getElementById('btn-mode-demo'),
    btnModeLive: document.getElementById('btn-mode-live'),
    refreshCheckbox: document.getElementById('refresh-cache'),
    chips: document.querySelectorAll('.chip'),
    loadingState: document.getElementById('loading-state'),
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
    // KPI elements
    kpiMatched: document.getElementById('kpi-matched-count'),
    kpiMaxSavings: document.getElementById('kpi-max-savings'),
    kpiTotalProducts: document.getElementById('kpi-total-products'),
    // Single store elements
    accordionToggle: document.getElementById('accordion-toggle'),
    singleStoreAccordion: document.querySelector('.single-store-accordion'),
    singleStoreBody: document.getElementById('single-store-body'),
    singleStoreCount: document.getElementById('single-store-count'),
    singleStoreGrid: document.getElementById('single-store-grid'),
    // Modal
    modal: document.getElementById('product-modal'),
    modalClose: document.getElementById('modal-close'),
    modalTitle: document.getElementById('modal-title'),
    modalBrand: document.getElementById('modal-brand'),
    modalBody: document.getElementById('modal-body'),
    // Theme toggle
    themeToggle: document.getElementById('btn-theme-toggle'),
    toastContainer: document.getElementById('toast-container')
  };

  // Initialize
  function init() {
    bindEvents();
    // Pre-populate query input with default demo query
    elements.queryInput.value = 'milk';
    // Load instant demo on initial render
    executeSearch('milk', false);
  }

  // Bind Event Listeners
  function bindEvents() {
    // Search Form Submit
    elements.form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = elements.queryInput.value.trim();
      if (q) {
        executeSearch(q, elements.refreshCheckbox.checked);
      }
    });

    // Input changes (clear button visibility)
    elements.queryInput.addEventListener('input', () => {
      elements.clearBtn.style.display = elements.queryInput.value.trim() ? 'block' : 'none';
    });

    elements.clearBtn.addEventListener('click', () => {
      elements.queryInput.value = '';
      elements.clearBtn.style.display = 'none';
      elements.queryInput.focus();
    });

    // Mode Selector
    elements.btnModeDemo.addEventListener('click', () => {
      setMode('demo');
      elements.queryInput.value = 'milk';
      executeSearch('milk', false);
    });

    elements.btnModeLive.addEventListener('click', () => {
      setMode('live');
      showToast('Live Mode enabled: Searches will scrape Blinkit, Zepto, and Amazon in real-time.', 'info');
    });

    // Quick Search Chips
    elements.chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        const queryVal = chip.getAttribute('data-query');
        elements.queryInput.value = queryVal;
        elements.clearBtn.style.display = 'block';
        // If clicking milk, can use demo; otherwise switch to live scrape
        if (queryVal === 'milk') {
          setMode('demo');
        } else {
          setMode('live');
        }
        executeSearch(queryVal, elements.refreshCheckbox.checked);
      });
    });

    // Filter by Store
    elements.storeFilter.addEventListener('change', (e) => {
      state.selectedStoreFilter = e.target.value;
      applyFilterAndSort();
    });

    // Sort Selection
    elements.sortSelect.addEventListener('change', (e) => {
      state.selectedSort = e.target.value;
      applyFilterAndSort();
    });

    // Single Store Accordion
    elements.accordionToggle.addEventListener('click', () => {
      const isExpanded = elements.singleStoreBody.style.display === 'block';
      elements.singleStoreBody.style.display = isExpanded ? 'none' : 'block';
      elements.singleStoreAccordion.classList.toggle('open', !isExpanded);
    });

    // Modal Close
    elements.modalClose.addEventListener('click', closeModal);
    elements.modal.addEventListener('click', (e) => {
      if (e.target === elements.modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });

    // Error retry button
    elements.btnRetry.addEventListener('click', () => {
      setMode('demo');
      elements.queryInput.value = 'milk';
      executeSearch('milk', false);
    });

    // Theme Toggle
    elements.themeToggle.addEventListener('click', () => {
      document.body.classList.toggle('light-theme');
      const isLight = document.body.classList.contains('light-theme');
      showToast(isLight ? 'Light theme activated' : 'Dark theme activated', 'info');
    });
  }

  function setMode(mode) {
    state.mode = mode;
    if (mode === 'demo') {
      elements.btnModeDemo.classList.add('active');
      elements.btnModeLive.classList.remove('active');
    } else {
      elements.btnModeLive.classList.add('active');
      elements.btnModeDemo.classList.remove('active');
    }
  }

  // Fetch Comparison Data
  async function executeSearch(query, bypassCache) {
    state.query = query;
    showLoading();

    let endpoint = '';
    if (state.mode === 'demo' && query.toLowerCase() === 'milk') {
      endpoint = '/api/demo';
    } else {
      endpoint = `/api/compare?query=${encodeURIComponent(query)}&refresh=${bypassCache ? 'true' : 'false'}`;
    }

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

      const totalMatched = state.deals.length;
      if (totalMatched > 0) {
        showToast(`Found ${totalMatched} multi-store matched deals for "${query}"!`, 'success');
      } else {
        showToast(`No multi-store overlaps for "${query}". Check single-store items.`, 'warning');
      }
    } catch (err) {
      console.error('Fetch error:', err);
      showError('Search Request Failed', err.message || 'Unable to communicate with the comparison server.');
    }
  }

  // Visual State Handlers
  function showLoading() {
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

  // Render Pipeline
  function renderResults() {
    // Header tags
    elements.currentQueryTag.textContent = `query: ${state.query}`;
    elements.cacheIndicator.style.display = state.cached ? 'inline-block' : 'none';

    // KPIs
    elements.kpiMatched.textContent = state.summary.total_matched || state.deals.length;
    elements.kpiTotalProducts.textContent = state.summary.total_products || (state.deals.length + state.singleStoreItems.length);

    let maxSav = 0;
    state.deals.forEach(d => {
      if (d.savings && d.savings > maxSav) maxSav = d.savings;
    });
    elements.kpiMaxSavings.textContent = maxSav > 0 ? `₹${maxSav}` : '₹0';

    // Filter & Sort
    applyFilterAndSort();

    // Single Store Items
    renderSingleStoreItems();
  }

  function applyFilterAndSort() {
    let filtered = [...state.deals];

    // Filter by store
    if (state.selectedStoreFilter !== 'all') {
      filtered = filtered.filter(deal => {
        return deal.prices && Object.keys(deal.prices).includes(state.selectedStoreFilter);
      });
    }

    // Sort deals
    filtered.sort((a, b) => {
      switch (state.selectedSort) {
        case 'savings_desc':
          return (b.savings || 0) - (a.savings || 0);
        case 'savings_pct_desc':
          return (b.savings_percentage || 0) - (a.savings_percentage || 0);
        case 'price_asc':
          return (a.lowest_price || 0) - (b.lowest_price || 0);
        case 'stores_desc':
          return (b.store_count || 0) - (a.store_count || 0);
        default:
          return 0;
      }
    });

    renderDeals(filtered);
  }

  // Render Deal Cards
  function renderDeals(deals) {
    elements.dealsGrid.innerHTML = '';

    if (!deals || deals.length === 0) {
      elements.noDealsBox.style.display = 'block';
      return;
    }
    elements.noDealsBox.style.display = 'none';

    deals.forEach((deal, idx) => {
      const card = document.createElement('div');
      card.className = 'deal-card';

      // Price rows
      let storeRowsHtml = '';
      const storeOrder = ['Blinkit', 'Zepto', 'Amazon'];
      storeOrder.forEach(storeName => {
        const detail = deal.store_details ? deal.store_details[storeName] : null;
        if (detail && detail.price !== null) {
          const isWinner = deal.cheapest_stores && deal.cheapest_stores.includes(storeName);
          const storeCssClass = storeName.toLowerCase().replace(/\s+/g, '');
          
          storeRowsHtml += `
            <div class="store-row ${isWinner ? 'is-winner' : ''}">
              <div class="store-meta">
                <span class="store-tag ${storeCssClass}">${storeName}</span>
                ${isWinner ? '<span class="winner-crown">👑 Lowest Price</span>' : ''}
              </div>
              <div class="price-meta">
                <span class="store-price">₹${detail.price}</span>
                ${detail.unit_price ? `<div class="unit-price-sub">₹${detail.unit_price} / unit</div>` : ''}
              </div>
            </div>
          `;
        }
      });

      // Savings Pill
      const hasSavings = deal.savings && deal.savings > 0;
      const savingsHtml = hasSavings
        ? `<div class="savings-pill">Save ₹${deal.savings} (${deal.savings_percentage}%)</div>`
        : `<div class="savings-pill" style="background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.1); color: var(--text-secondary); box-shadow: none;">Same Price Across Stores</div>`;

      card.innerHTML = `
        <div>
          <div class="deal-card-header">
            <div class="deal-tags">
              ${deal.brand ? `<span class="brand-badge">${escapeHtml(deal.brand)}</span>` : ''}
              ${deal.quantity ? `<span class="qty-badge">${escapeHtml(deal.quantity)}</span>` : ''}
            </div>
            ${savingsHtml}
          </div>

          <h3 class="deal-title" title="${escapeHtml(deal.canonical_name)}">
            ${escapeHtml(deal.canonical_name)}
          </h3>

          <div class="store-price-matrix">
            ${storeRowsHtml}
          </div>
        </div>

        <div class="card-footer">
          <div class="deal-summary-stat">
            Cheapest at: <strong style="color: #34d399;">${escapeHtml(deal.cheapest_store)}</strong>
          </div>
          <button type="button" class="view-breakdown-btn" data-deal-idx="${idx}">
            Store Breakdown
          </button>
        </div>
      `;

      // Attach click to breakdown button
      const btn = card.querySelector('.view-breakdown-btn');
      btn.addEventListener('click', () => openModal(deal));

      elements.dealsGrid.appendChild(card);
    });
  }

  // Render Single Store Items
  function renderSingleStoreItems() {
    const items = state.singleStoreItems || [];
    elements.singleStoreCount.textContent = items.length;
    elements.singleStoreGrid.innerHTML = '';

    if (items.length === 0) {
      elements.singleStoreGrid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No single-store items found.</div>';
      return;
    }

    items.forEach(item => {
      const storeName = Object.keys(item.prices || {})[0] || 'Store';
      const price = item.lowest_price;
      const storeCssClass = storeName.toLowerCase().replace(/\s+/g, '');

      const card = document.createElement('div');
      card.className = 'single-item-card';
      card.innerHTML = `
        <div class="single-item-title">${escapeHtml(item.canonical_name)}</div>
        <div class="single-item-meta">
          <span class="store-tag ${storeCssClass}">${escapeHtml(storeName)}</span>
          <strong style="font-family: var(--font-heading); font-size: 1rem;">₹${price}</strong>
        </div>
      `;
      elements.singleStoreGrid.appendChild(card);
    });
  }

  // Modal Dialog
  function openModal(deal) {
    elements.modalTitle.textContent = deal.canonical_name;
    elements.modalBrand.textContent = deal.brand || 'Quick Commerce';

    let tableRows = '';
    const details = deal.store_details || {};
    for (const [store, info] of Object.entries(details)) {
      const isWinner = deal.cheapest_stores && deal.cheapest_stores.includes(store);
      tableRows += `
        <tr>
          <td><strong>${escapeHtml(store)}</strong></td>
          <td>${escapeHtml(info.raw_name || '-')}</td>
          <td>${escapeHtml(info.quantity || deal.quantity || '-')}</td>
          <td>
            <span style="font-weight: 700; color: ${isWinner ? '#34d399' : 'inherit'}">
              ₹${info.price} ${isWinner ? '👑' : ''}
            </span>
          </td>
          <td>${info.unit_price ? `₹${info.unit_price}` : '-'}</td>
        </tr>
      `;
    }

    elements.modalBody.innerHTML = `
      <div style="margin-bottom: 16px; font-size: 0.9rem; color: var(--text-secondary);">
        Normalized Quantity: <strong>${escapeHtml(deal.quantity || 'Standard')}</strong> | 
        Lowest Available: <strong style="color: #34d399;">₹${deal.lowest_price}</strong> at <strong>${escapeHtml(deal.cheapest_store)}</strong>
      </div>
      <table class="modal-table">
        <thead>
          <tr>
            <th>Store</th>
            <th>Scraped Product Title</th>
            <th>Pack Size</th>
            <th>Price</th>
            <th>Unit Price</th>
          </tr>
        </thead>
        <tbody>
          ${tableRows}
        </tbody>
      </table>
    `;

    elements.modal.style.display = 'flex';
  }

  function closeModal() {
    elements.modal.style.display = 'none';
  }

  // Toast System
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.borderLeft = type === 'success' ? '4px solid #10b981' : (type === 'warning' ? '4px solid #f59e0b' : '4px solid #6366f1');
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3800);
  }

  // Utility: HTML Escaping
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Kickstart on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
