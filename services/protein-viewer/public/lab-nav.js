/**
 * lab-nav.js — Inyecta botones "Open in Protein Viewer" y "Add to Variant Tracker"
 * en la columna izquierda de REEV, al mismo nivel que "Jump in Local IGV".
 */
(function () {
  'use strict';

  const PROTEIN_URL = 'https://protein.neuropedialab.org';
  const TRACKER_URL = 'https://tracker.neuropedialab.org';

  // ── Extraer info de variante ───────────────────────────────────────────────

  function parseURL() {
    const path = window.location.pathname;
    const orig = new URLSearchParams(window.location.search).get('orig') || '';

    const seqvarMatch = path.match(/\/seqvar\/([^/?]+)/);
    const geneMatch   = path.match(/\/gene\/([^/?]+)/);

    let coords = null;
    if (seqvarMatch) {
      const parts = seqvarMatch[1].split('-');
      if (parts.length >= 5) {
        coords = { build: parts[0], chrom: parts[1], pos: parts[2], ref: parts[3], alt: parts.slice(4).join('-') };
      }
    }

    const geneRe  = orig.match(/\(([A-Z][A-Z0-9-]+)\)/);
    const txRe    = orig.match(/^(NM_[0-9]+\.[0-9]+)/);
    const hgvsCRe = orig.match(/(c\.[^\s]+)/);

    return {
      isSeqvar:          !!seqvarMatch,
      geneURL:           geneMatch ? geneMatch[1] : null,
      coords,
      orig,
      geneFromOrig:      geneRe  ? geneRe[1]  : null,
      transcriptFromOrig:txRe    ? txRe[1]    : null,
      hgvsC:             hgvsCRe ? hgvsCRe[1] : null,
    };
  }

  function getGeneFromDOM() {
    const spans = document.querySelectorAll('.v-list-item .font-italic, .font-italic');
    for (const s of spans) {
      const txt = s.textContent.trim();
      if (txt && /^[A-Z][A-Z0-9-]+$/.test(txt) && txt.length > 1) return txt;
    }
    return null;
  }

  function buildURLs(info) {
    const gene = info.geneURL || info.geneFromOrig || getGeneFromDOM() || '';

    const proteinUrl = gene
      ? `${PROTEIN_URL}/?gene=${encodeURIComponent(gene)}`
      : PROTEIN_URL + '/';

    const tp = new URLSearchParams();
    if (info.coords) {
      tp.set('build', info.coords.build);
      tp.set('chrom', info.coords.chrom);
      tp.set('pos',   info.coords.pos);
      tp.set('ref',   info.coords.ref);
      tp.set('alt',   info.coords.alt);
    }
    if (gene)                      tp.set('gene',       gene);
    if (info.hgvsC)                tp.set('hgvs_c',     info.hgvsC);
    if (info.transcriptFromOrig)   tp.set('transcript', info.transcriptFromOrig);
    const trackerUrl = `${TRACKER_URL}/?${tp.toString()}`;

    return { proteinUrl, trackerUrl };
  }

  // ── Buscar el botón IGV (múltiples estrategias) ───────────────────────────

  function findIGVButton() {
    // 1. Por icono mdi-launch (más fiable que por texto)
    const byIcon = document.querySelector('.mdi-launch');
    if (byIcon) return byIcon.closest('button, a[class*="v-btn"]') || byIcon.parentElement;

    // 2. Por texto exacto en cualquier botón
    for (const el of document.querySelectorAll('button, a')) {
      if (el.textContent.includes('Jump in Local IGV')) return el;
    }

    // 3. Fallback: primer botón outlined en la columna sticky
    const sticky = document.querySelector('[style*="sticky"]');
    if (sticky) return sticky.querySelector('button, a');

    return null;
  }

  // ── Crear botón estilo REEV ───────────────────────────────────────────────

  function makeBtn(icon, label, url, id) {
    const btn = document.createElement('a');
    btn.id     = id;
    btn.href   = url;
    btn.target = '_blank';
    btn.rel    = 'noopener';
    // Mismas clases Vuetify que el botón IGV
    btn.className = 'v-btn v-btn--density-default v-btn--size-default v-btn--variant-outlined ma-2';
    btn.style.cssText = 'text-decoration:none;display:inline-flex;width:calc(100% - 16px)';
    btn.innerHTML = `
      <span class="v-btn__overlay"></span>
      <span class="v-btn__underlay"></span>
      <i class="mdi ${icon} v-icon notranslate v-icon--size-default" style="font-size:18px;margin-right:8px"></i>
      <span class="v-btn__content">${label}</span>
    `;
    return btn;
  }

  // ── Lógica principal de inyección ─────────────────────────────────────────

  let lastVariant = '';

  function inject() {
    // Solo en páginas de variante o gen
    if (!window.location.pathname.match(/\/(seqvar|gene)\//)) return false;

    const igvBtn = findIGVButton();
    if (!igvBtn) return false;

    const info = parseURL();
    const currentId = info.coords
      ? `${info.coords.chrom}-${info.coords.pos}-${info.coords.ref}-${info.coords.alt}`
      : window.location.pathname;

    // Ya inyectado para esta variante
    if (document.getElementById('__lab-protein-btn__') && lastVariant === currentId) return true;

    // Limpiar inyección previa si es otra variante
    document.getElementById('__lab-protein-btn__')?.remove();
    document.getElementById('__lab-tracker-btn__')?.remove();

    lastVariant = currentId;

    const urls  = buildURLs(info);
    const pBtn  = makeBtn('mdi-molecule',              'Open in Protein Viewer',  urls.proteinUrl, '__lab-protein-btn__');
    const tBtn  = makeBtn('mdi-clipboard-list-outline','Add to Variant Tracker',  urls.trackerUrl, '__lab-tracker-btn__');

    igvBtn.insertAdjacentElement('afterend', tBtn);
    igvBtn.insertAdjacentElement('afterend', pBtn);

    return true;
  }

  // ── Polling robusto (cada 400 ms, máx 30 s) ───────────────────────────────

  let pollTimer = null;
  let pollCount = 0;

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollCount = 0;
    pollTimer = setInterval(() => {
      pollCount++;
      if (inject() || pollCount > 75) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }, 400);
  }

  function onNavigate() {
    document.getElementById('__lab-protein-btn__')?.remove();
    document.getElementById('__lab-tracker-btn__')?.remove();
    lastVariant = '';
    startPolling();
  }

  // Interceptar navegación Vue Router
  const origPush = history.pushState.bind(history);
  history.pushState = function (...args) { origPush(...args); setTimeout(onNavigate, 50); };
  window.addEventListener('popstate', onNavigate);

  // Arrancar al cargar
  startPolling();
})();


