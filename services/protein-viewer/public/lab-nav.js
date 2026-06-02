/**
 * lab-nav.js — Inyecta botones "Open in Protein Viewer" y "Add to Variant Tracker"
 * en la columna izquierda de REEV, al mismo nivel que "Jump in Local IGV".
 * Servido desde https://reev.neuropedialab.org/lab-nav.js
 */
(function () {
  'use strict';

  const PROTEIN_URL = 'https://protein.neuropedialab.org';
  const TRACKER_URL = 'https://tracker.neuropedialab.org';

  // ── Extraer info de variante ───────────────────────────────────────────────

  function parseURL() {
    const path   = window.location.pathname;
    const orig   = new URLSearchParams(window.location.search).get('orig') || '';

    const seqvarMatch = path.match(/\/seqvar\/([^/?]+)/);
    const geneMatch   = path.match(/\/gene\/([^/?]+)/);

    let coords = null;
    if (seqvarMatch) {
      const parts = seqvarMatch[1].split('-');
      if (parts.length >= 5) {
        coords = { build: parts[0], chrom: parts[1], pos: parts[2], ref: parts[3], alt: parts.slice(4).join('-') };
      }
    }

    const geneRe      = orig.match(/\(([A-Z][A-Z0-9-]+)\)/);
    const txRe        = orig.match(/^(NM_[0-9]+\.[0-9]+)/);
    const hgvsCRe     = orig.match(/(c\.[^\s]+)/);

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
    const spans = document.querySelectorAll('.v-list-item .font-italic');
    for (const s of spans) {
      const txt = s.textContent.trim();
      if (txt && /^[A-Z][A-Z0-9-]+$/.test(txt) && txt.length > 1) return txt;
    }
    return null;
  }

  // ── Construir URLs con parámetros ─────────────────────────────────────────

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

  // ── Inyección de botones ──────────────────────────────────────────────────

  // Clases Vuetify idénticas al botón "Jump in Local IGV"
  const BTN_CLASS = 'v-btn v-btn--density-default v-btn--size-default v-btn--variant-outlined ma-2';

  function makeBtn(icon, label, url) {
    const btn = document.createElement('a');
    btn.href   = url;
    btn.target = '_blank';
    btn.rel    = 'noopener';
    btn.className = BTN_CLASS;
    btn.style.cssText = 'text-decoration:none;display:inline-flex;width:calc(100% - 16px)';
    btn.innerHTML = `
      <span class="v-btn__overlay"></span>
      <span class="v-btn__underlay"></span>
      <i class="mdi ${icon} v-icon notranslate v-icon--size-default me-2" style="font-size:18px"></i>
      <span class="v-btn__content" data-no-activator="">${label}</span>
    `;
    return btn;
  }

  let injected    = false;
  let lastVariant = '';
  let observer    = null;

  function inject() {
    // Buscar el botón IGV por texto
    let igvBtn = null;
    document.querySelectorAll('.v-btn').forEach(el => {
      if (el.textContent.includes('Jump in Local IGV')) igvBtn = el;
    });
    if (!igvBtn) return false;

    const info = parseURL();
    const currentId = info.coords
      ? `${info.coords.chrom}-${info.coords.pos}-${info.coords.ref}-${info.coords.alt}`
      : window.location.pathname;

    // Evitar doble inyección
    if (injected && lastVariant === currentId) return true;

    // Eliminar botones anteriores si la variante cambió
    document.getElementById('__lab-protein-btn__')?.remove();
    document.getElementById('__lab-tracker-btn__')?.remove();

    lastVariant = currentId;
    injected    = true;

    const urls = buildURLs(info);

    const pBtn = makeBtn('mdi-molecule', 'Open in Protein Viewer', urls.proteinUrl);
    pBtn.id = '__lab-protein-btn__';

    const tBtn = makeBtn('mdi-clipboard-list-outline', 'Add to Variant Tracker', urls.trackerUrl);
    tBtn.id = '__lab-tracker-btn__';

    igvBtn.insertAdjacentElement('afterend', tBtn);
    igvBtn.insertAdjacentElement('afterend', pBtn);

    return true;
  }

  function tryInject() {
    if (inject()) return;
    if (observer) return;
    observer = new MutationObserver(() => {
      if (inject()) { observer.disconnect(); observer = null; }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function onNavigate() {
    injected = false;
    document.getElementById('__lab-protein-btn__')?.remove();
    document.getElementById('__lab-tracker-btn__')?.remove();
    setTimeout(tryInject, 200);
  }

  const origPush = history.pushState.bind(history);
  history.pushState = function (...args) { origPush(...args); onNavigate(); };
  window.addEventListener('popstate', onNavigate);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryInject);
  } else {
    tryInject();
  }
})();

