/* eslint-disable no-undef */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // =============== Helpers =================
  const $  = (sel, ctx=document) => ctx.querySelector(sel);
  const $$ = (sel, ctx=document) => Array.from(ctx.querySelectorAll(sel));

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function normalizeText(t) {
    return (t || '')
      .toString()
      .trim()
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .replace(/[€\s]/g, '')
      .replace(/,/g, '.');
  }

  function parsePrice(text) {
    // "€12.345,67" -> 12345.67 | "12,95" -> 12.95 | "12.95" -> 12.95
    const n = (text || '')
      .replace(/[^\d,.-]/g, '')
      .replace(/\.(?=\d{3}(?:\D|$))/g, '') // punt als duizendtal weg
      .replace(',', '.');
    const val = parseFloat(n);
    return Number.isFinite(val) ? val : Number.POSITIVE_INFINITY;
  }

  // Cookies + localStorage
  function setComparisonSlugs(slugsArray) {
    const slugs = (slugsArray || []).filter(Boolean);
    const isHttps = location.protocol === 'https:';
    const attrs = ['path=/','max-age=604800','SameSite=Lax', isHttps ? 'Secure' : ''].filter(Boolean).join('; ');
    document.cookie = 'comparison_slugs=' + encodeURIComponent(slugs.join(',')) + '; ' + attrs;
    try { localStorage.setItem('comparison_slugs', JSON.stringify(slugs)); } catch {}
  }
  function getComparisonSlugs() {
    const m = document.cookie.match(/(?:^|;\s*)comparison_slugs=([^;]+)/);
    if (m) return decodeURIComponent(m[1]).split(',').filter(Boolean);
    try { return JSON.parse(localStorage.getItem('comparison_slugs') || '[]'); } catch { return []; }
  }
  window.setComparisonSlugs = setComparisonSlugs; // backwards compatible

  // GA4 / beacon
  function pushEvent(name, params={}) {
    const payload = { event: name, ...params };
    try {
      if (typeof gtag === 'function') {
        gtag('event', name, params);
      } else if (navigator.sendBeacon) {
        const blob = new Blob([JSON.stringify(payload)], { type:'application/json' });
        navigator.sendBeacon('/log_event', blob);
      }
    } catch (err) { console.warn('Analytics event mislukt:', err); }
  }

  // A11y announcer
  function announce(msg) {
    let region = document.getElementById('sr-status');
    if (!region) {
      region = document.createElement('div');
      region.id = 'sr-status';
      region.setAttribute('role', 'status');
      region.setAttribute('aria-live', 'polite');
      region.style.position = 'absolute';
      region.style.left = '-9999px';
      document.body.appendChild(region);
    }
    region.textContent = msg;
  }

  // =============== DOM refs =================
  const table = $('#vergelijk-tabel');
  if (!table) return;

  const headerRow = table.tHead?.rows?.[0];
  const tbody     = table.tBodies?.[0];
  const wrap      = document.querySelector('.vergelijk-tabel-wrap');
  const caption   = $('#table-help');

  // Helpers die header/body nodig hebben
  function getLeavesFromTable() {
    const ths = document.querySelectorAll('#vergelijk-tabel thead th[data-slug]');
    return Array.from(ths)
      .map(th => (th.dataset.slug || '').split('/').filter(Boolean).pop())
      .filter(Boolean);
  }

  function updateShareUrl(replace = false) {
    const leaves = getLeavesFromTable();
    if (leaves.length >= 2) {
      const combo = leaves.sort().join('-vs-');
      const url = `${location.origin}/vergelijk/${combo}/`;
      const shareBtn = document.getElementById('share-compare');
      if (shareBtn) shareBtn.dataset.url = url;
      if (replace && history.replaceState) history.replaceState(null, '', url);
    } else {
      if (replace && history.replaceState) history.replaceState(null, '', '/vergelijk');
    }
  }

  function refreshPinDropdown() {
    const pinSel = $('#pin-provider');
    if (!pinSel || !headerRow) return;
    const providerThs = Array.from(headerRow.cells).slice(1);
    pinSel.innerHTML = '<option value="">— kies —</option>' + providerThs.map((th, i) => {
      const name = th.querySelector('.provider-heading')?.textContent?.trim() || `Aanbieder ${i+1}`;
      const slug = th.dataset.slug || '';
      return `<option value="${i+1}" data-slug="${slug}">${name}</option>`;
    }).join('');
  }

  function recalcDiffIfActive() {
    const btn = $('#toggle-diff');
    const on  = btn && btn.getAttribute('aria-pressed') === 'true';
    if (!on || !tbody) return;

    const norm = (t) => (t||'').toString().trim().toLowerCase().replace(/\s+/g,' ').replace(/[€\s]/g,'').replace(/,/g,'.');
    Array.from(tbody.rows).forEach(tr => {
      const tds = Array.from(tr.cells).slice(1);
      const vals = tds.map(td => norm(td.textContent).replace(/^(—|-)?$/, ''));
      const nonEmpty = vals.filter(v => v !== '');
      const equal = nonEmpty.length <= 1 || nonEmpty.every(v => v === nonEmpty[0]);
      tds.forEach(td => td.classList.toggle('diff-cell', !equal));
    });
  }

  // =============== UI: pin dropdown vullen ===============
  refreshPinDropdown();

  // =============== Acties boven de tabel ===============
  $('#clear-comparison')?.addEventListener('click', () => {
    fetch('/clear_comparison', {
      method:'POST',
      headers:{ 'Content-Type':'application/json', 'X-CSRFToken':getCsrfToken() },
      credentials:'same-origin'
    })
    .then((r)=> r.ok ? (location.href = '/') : console.error('Wissen mislukt:', r.statusText))
    .catch((e)=> console.error('Fout bij clear_comparison:', e));
  });

  // --- Alles wissen (UI + state + URL) ---
function clearComparisonUI() {
  if (!headerRow || !tbody) return;

  // verwijder alle aanbiederskolommen (alles > index 0)
  const totalCols = headerRow.cells.length;
  let removed = 0;
  for (let col = totalCols - 1; col >= 1; col--) {
    document.querySelectorAll('#vergelijk-tabel tr').forEach(tr => {
      if (tr.children[col]) tr.children[col].remove();
    });
    removed++;
  }

  // state leegmaken
  try { setComparisonSlugs([]); } catch (_) {}
  // URL netjes terugzetten
  if (history.replaceState) history.replaceState(null, '', '/vergelijk');

  // UI bijwerken
  updateShareUrl(true);      // zal ook /vergelijk zetten bij <2 leaves
  refreshPinDropdown();
  recalcDiffIfActive();
  announce('Vergelijking geleegd.');

  // optioneel: backend laten weten (negeren bij 404)
  try {
    fetch('/clear_comparison', {
      method:'POST',
      headers:{ 'Content-Type':'application/json', 'X-CSRFToken':getCsrfToken() },
      credentials:'same-origin'
    }).catch(() => {});
  } catch (_) {}

  // mobile navigator/hints verversen (functies bestaan verderop)
  try { buildMobileNav(); onScrollSync(); } catch (_) {}

  // analytics
  pushEvent('vergelijk_wissen', { kolommen: removed });
}

// knop laten werken
document.getElementById('clear-comparison')?.addEventListener('click', (e) => {
  e.preventDefault();
  clearComparisonUI();
});


  // Outgoing link analytics
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;
    const name = link.dataset.gtm;
    if (!name) return;
    const ab = link.dataset.abonnement || 'onbekend';
    pushEvent(name, { abonnement:ab, destination:link.href, pagina:location.pathname });
  });

  // Verschillen highlighten
  (function setupDiffToggle(){
    const btn = $('#toggle-diff');
    if (!tbody || !btn) return;

    function valuesEqual(cells) {
      const vals = cells.map((td) => normalizeText(td.textContent).replace(/^(—|-)?$/, ''));
      const nonEmpty = vals.filter(v => v !== '');
      if (nonEmpty.length <= 1) return true;
      return nonEmpty.every(v => v === nonEmpty[0]);
    }
    function toggleDifferences(on) {
      Array.from(tbody.rows).forEach(tr => {
        const dataTds = Array.from(tr.cells).slice(1);
        if (dataTds.length <= 1) return;
        const equal = valuesEqual(dataTds);
        dataTds.forEach(td => td.classList.toggle('diff-cell', !!on && !equal));
      });
    }
    btn.addEventListener('click', () => {
      const active = btn.getAttribute('aria-pressed') === 'true';
      const next = !active;
      btn.setAttribute('aria-pressed', String(next));
      btn.textContent = next ? 'Verberg verschillen' : 'Toon verschillen';
      toggleDifferences(next);
      pushEvent('toggle_verschillen', { aan: next });
    });
  })();

  // =============== Kolommen herordenen (sorteren/pinnen) ===============
  function moveColumn(fromIndex, toIndex) {
    const rows = [headerRow, ...Array.from(tbody.rows)];
    rows.forEach(tr => {
      const cells = Array.from(tr.children);
      const node  = cells[fromIndex];
      if (!node) return;
      if (toIndex >= tr.children.length) tr.appendChild(node);
      else tr.insertBefore(node, tr.children[toIndex]);
    });
  }

  function announceSort(dir) {
    if (!caption) return;
    const base = 'Geselecteerde abonnementen vergelijken';
    const txt  = dir === 'asc' ? 'Gesorteerd op prijs: oplopend' : 'Gesorteerd op prijs: aflopend';
    caption.textContent = `${base} – ${txt}`;
  }

  function sortByPrice(direction='asc') {
    const priceRow = Array.from(tbody.rows).find(r =>
      r.querySelector('th[scope="row"]')?.textContent.trim().toLowerCase() === 'prijs'
    );
    if (!priceRow) return;

    // maak lijst van {slug, price}
    const items = Array.from(headerRow.cells).slice(1).map((th, i) => {
      const slug = th.dataset.slug;
      const td   = priceRow.cells[i]; // body heeft geen labelcel
      return { slug, price: parsePrice(td?.textContent || '') };
    });

    const sign = direction === 'desc' ? -1 : 1;
    items.sort((a, b) => sign * (a.price - b.price));

    // verplaats volgorde volgens sort
    items.forEach((it, order) => {
      const target = 1 + order; // index 1 = eerste aanbiederkolom
      const current = Array.from(headerRow.cells).findIndex(h => h.dataset.slug === it.slug);
      if (current > -1 && current !== target) moveColumn(current, target);
    });

    announceSort(direction);
  }

  $('#sort-price')?.addEventListener('click', (e) => {
    const btn = e.currentTarget;
    const dir = btn.getAttribute('data-sort') === 'asc' ? 'desc' : 'asc';
    sortByPrice(dir);
    btn.setAttribute('data-sort', dir);
    btn.textContent = dir === 'asc' ? 'Sorteer op prijs ↑' : 'Sorteer op prijs ↓';
    pushEvent('sorteer_op_prijs', { richting: dir });
  });

  $('#pin-provider')?.addEventListener('change', (e) => {
    const idx = parseInt(e.target.value, 10);
    if (!Number.isFinite(idx)) return;
    moveColumn(idx, 1);
    pushEvent('pin_aanbieder', { kolom: idx });
  });

  // =============== Kolom verwijderen ====================
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.remove-col');
    if (!btn) return;
    e.preventDefault();

    const th = btn.closest('th');
    const theadRow = document.querySelector('#vergelijk-tabel thead tr');
    if (!th || !theadRow) return;

    // Kolomindex bepalen (0 = labelkolom "Aanbieder")
    const headers = Array.from(theadRow.children);
    const colIndex = headers.indexOf(th);
    if (colIndex <= 0) return; // labelkolom nooit verwijderen

    const providerName = th.querySelector('.provider-heading')?.textContent?.trim() || '';
    const slugFull = th.dataset.slug || '';
    const slugLeaf = slugFull.split('/').filter(Boolean).pop();

    // Verwijder de kolom in alle rijen
    document.querySelectorAll('#vergelijk-tabel tr').forEach(tr => {
      if (tr.children[colIndex]) tr.children[colIndex].remove();
    });

    // Slug-state updaten
    try {
      const current = getComparisonSlugs();
      const next = current.filter(s => s !== slugFull && s !== slugLeaf);
      setComparisonSlugs(next);
    } catch (_) {}

    // UI bijwerken
    updateShareUrl(true);
    refreshPinDropdown();
    recalcDiffIfActive();
    announce(`'${providerName || slugLeaf}' verwijderd uit de vergelijking.`);
    pushEvent('verwijder_kolom', { slug: slugLeaf });
  });

  // =============== Delen ================================
  $('#share-compare')?.addEventListener('click', async () => {
    const leaves = getLeavesFromTable();
    const url = (leaves.length >= 2)
      ? `${location.origin}/vergelijk/${leaves.sort().join('-vs-')}/`
      : location.href;

    try {
      await navigator.clipboard.writeText(url);
      alert('Deelbare link gekopieerd!');
      pushEvent('deel_vergelijk', { aantal: leaves.length });
    } catch {
      prompt('Kopieer de link:', url.toString());
    }
  });

  // =============== Mobiel UX: navigator + hints =================
  if (!wrap || !headerRow) return;

  // hulpfunctie: haal CSS var op of meet de 2e kolom
  function getProviderWidth() {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--col-provider').trim();
    let n = parseFloat(raw);
    if (!Number.isFinite(n) || n <= 0) {
      const second = headerRow.cells[1];
      if (second) n = Math.round(second.getBoundingClientRect().width) || 220;
      else n = 220;
    }
    return n;
  }

  const mq = window.matchMedia('(max-width: 768px)');
  let nav, btnPrev, btnNext, status, providerCount = 0, idx = 0, COL_W = getProviderWidth();

  function buildMobileNav() {
    providerCount = Math.max(0, headerRow.cells.length - 1);
    if (!mq.matches || providerCount <= 1) { destroyMobileNav(); return; }

    if (!nav) {
      nav = document.createElement('div');
      nav.className = 'mobile-col-nav';
      nav.setAttribute('aria-label', 'Navigeer tussen aanbieders');

      btnPrev = document.createElement('button');
      btnPrev.className = 'nav-btn'; btnPrev.type = 'button';
      btnPrev.setAttribute('aria-label','Vorige aanbieder'); btnPrev.textContent = '←';

      status = document.createElement('span');
      status.className = 'mobile-col-status'; status.setAttribute('aria-live','polite');

      btnNext = document.createElement('button');
      btnNext.className = 'nav-btn'; btnNext.type = 'button';
      btnNext.setAttribute('aria-label','Volgende aanbieder'); btnNext.textContent = '→';

      nav.append(btnPrev, status, btnNext);
      wrap.parentNode.insertBefore(nav, wrap);

      btnPrev.addEventListener('click', () => scrollToIndex(idx - 1));
      btnNext.addEventListener('click', () => scrollToIndex(idx + 1));
    }

    idx = Math.min(providerCount - 1, Math.max(0, Math.round(wrap.scrollLeft / COL_W)));
    updateNav();
  }

  function destroyMobileNav() {
    if (nav?.parentNode) nav.parentNode.removeChild(nav);
    nav = btnPrev = btnNext = status = null;
  }

  function updateNav() {
    if (!nav) return;
    status.textContent = `Aanbieder ${idx + 1} / ${providerCount}`;
    btnPrev.disabled = idx <= 0;
    btnNext.disabled = idx >= providerCount - 1;
  }

  function scrollToIndex(newIdx) {
    idx = Math.min(providerCount - 1, Math.max(0, newIdx));
    wrap.scrollTo({ left: idx * COL_W, behavior: 'smooth' });
    updateNav();
  }

  function onScrollSync() {
    if (!mq.matches || providerCount <= 1) return;
    const newIdx = Math.min(providerCount - 1, Math.max(0, Math.round(wrap.scrollLeft / COL_W)));
    if (newIdx !== idx) { idx = newIdx; updateNav(); }

    // fade/hint
    const start = wrap.scrollLeft <= 1;
    const end   = Math.ceil(wrap.scrollLeft + wrap.clientWidth) >= wrap.scrollWidth - 1;
    wrap.classList.toggle('hide-hint', !start || end);
  }

  function onResize() {
    COL_W = getProviderWidth();
    buildMobileNav();
    onScrollSync();
  }

  // Hints & nav initialiseren
  mq.addEventListener ? mq.addEventListener('change', onResize) : mq.addListener(onResize);
  window.addEventListener('resize', onResize);
  wrap.addEventListener('scroll', onScrollSync, { passive:true });
  window.addEventListener('load', onScrollSync);

  buildMobileNav();
  onScrollSync();

  // =============== Desktop: drag-to-scroll (niet op mobiel) ===============
  const canDrag = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  if (canDrag) {
    let isDown = false, startX = 0, startScroll = 0, moved = false;

    wrap.addEventListener('pointerdown', (e) => {
      if (e.pointerType !== 'mouse' && e.pointerType !== 'pen') return; // geen touch
      // klik op interactief element? dan niet draggen
      if (e.target.closest('button, a, input, select, textarea, .remove-col')) return;
      isDown = true; moved = false;
      startX = e.clientX; startScroll = wrap.scrollLeft;
      wrap.setPointerCapture?.(e.pointerId);
      wrap.style.cursor = 'grabbing';
    });

    wrap.addEventListener('pointermove', (e) => {
      if (!isDown) return;
      const dx = e.clientX - startX;
      if (Math.abs(dx) > 3) moved = true;
      wrap.scrollLeft = startScroll - dx;
    }, { passive:true });

    ['pointerup','pointercancel','pointerleave'].forEach(ev => {
      wrap.addEventListener(ev, (e) => {
        if (moved) e.preventDefault?.(); // click-ghost voorkomen
        isDown = false; moved = false;
        wrap.style.cursor = '';
      });
    });
  }

  // =============== A11y extras ==========================
  const diffBtn = $('#toggle-diff');
  diffBtn?.addEventListener('click', () => {
    const next = (diffBtn.getAttribute('aria-pressed') !== 'true');
    diffBtn.setAttribute('aria-pressed', String(next));
  });

  const sortBtn = $('#sort-price');
  sortBtn?.addEventListener('click', () => {
    const dir = sortBtn.getAttribute('data-sort') === 'asc' ? 'descending' : 'ascending';
    // we communiceren sort via caption (announceSort), maar zet ook hint op headerRow
    headerRow?.removeAttribute('aria-sort');
    headerRow?.setAttribute('aria-sort', dir);
  });
});
