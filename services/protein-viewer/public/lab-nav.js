/**
 * lab-nav.js — Inyecta accesos directos a Lab Tools en la columna izquierda de REEV.
 * Servido desde https://protein.neuropedialab.org/lab-nav.js
 */
(function () {
  'use strict';

  const PROTEIN_URL  = 'https://protein.neuropedialab.org';
  const TRACKER_URL  = 'https://tracker.neuropedialab.org';
  const JBROWSE_URL  = 'https://jbrowse.neuropedialab.org';

  // ── Extraer info de la variante desde la URL y el DOM ─────────────────────

  function parseURL() {
    const path   = window.location.pathname;
    const params = new URLSearchParams(window.location.search);
    const orig   = params.get('orig') || '';

    // /seqvar/grch37-4-113568536-G-GA
    const seqvarMatch = path.match(/\/seqvar\/([^/?]+)/);
    // /gene/SCN1A
    const geneMatch   = path.match(/\/gene\/([^/?]+)/);

    let coords = null;
    if (seqvarMatch) {
      const parts = seqvarMatch[1].split('-');
      if (parts.length >= 5) {
        coords = { build: parts[0], chrom: parts[1], pos: parts[2], ref: parts[3], alt: parts.slice(4).join('-') };
      }
    }

    // Extraer gen del HGVS original: "NM_001267039.1(LARP7):c.855dup" → LARP7
    let geneFromOrig = null;
    const geneRe = orig.match(/\(([A-Z][A-Z0-9-]+)\)/);
    if (geneRe) geneFromOrig = geneRe[1];

    // Extraer transcript del HGVS original: "NM_001267039.1(LARP7):c.855dup"
    let transcriptFromOrig = null;
    const txRe = orig.match(/^(NM_[0-9]+\.[0-9]+)/);
    if (txRe) transcriptFromOrig = txRe[1];

    // Extraer parte c. del HGVS
    let hgvsC = null;
    const hgvsCRe = orig.match(/(c\.[^\s]+)/);
    if (hgvsCRe) hgvsC = hgvsCRe[1];

    return {
      isSeqvar: !!seqvarMatch,
      isGene:   !!geneMatch,
      seqvarId: seqvarMatch ? seqvarMatch[1] : null,
      geneURL:  geneMatch   ? geneMatch[1]   : null,
      coords,
      orig,
      geneFromOrig,
      transcriptFromOrig,
      hgvsC,
    };
  }

  function getGeneFromDOM() {
    // En la columna izquierda, el gen se muestra en un <span class="font-italic">
    const spans = document.querySelectorAll('.v-list-item .font-italic');
    for (const s of spans) {
      const txt = s.textContent.trim();
      if (txt && /^[A-Z][A-Z0-9-]+$/.test(txt) && txt.length > 1) return txt;
    }
    return null;
  }

  function buildURLs(info) {
    const gene = info.geneURL || info.geneFromOrig || getGeneFromDOM() || '';

    // Protein Viewer
    const proteinUrl = gene
      ? `${PROTEIN_URL}/?gene=${encodeURIComponent(gene)}`
      : PROTEIN_URL + '/';

    // Variant Tracker — pre-rellena el formulario
    let trackerParams = new URLSearchParams();
    if (info.coords) {
      trackerParams.set('build', info.coords.build);
      trackerParams.set('chrom', info.coords.chrom);
      trackerParams.set('pos',   info.coords.pos);
      trackerParams.set('ref',   info.coords.ref);
      trackerParams.set('alt',   info.coords.alt);
    }
    if (gene)                     trackerParams.set('gene',       gene);
    if (info.hgvsC)               trackerParams.set('hgvs_c',     info.hgvsC);
    if (info.transcriptFromOrig)  trackerParams.set('transcript', info.transcriptFromOrig);
    const trackerUrl = `${TRACKER_URL}/?${trackerParams.toString()}`;

    // JBrowse2
    let jbrowseUrl = JBROWSE_URL + '/';
    if (info.coords) {
      jbrowseUrl += `?loc=${info.coords.chrom}:${info.coords.pos}`;
    }

    return { proteinUrl, trackerUrl, jbrowseUrl };
  }

  // ── Inyección en la columna izquierda ─────────────────────────────────────

  const SECTION_ID  = '__lab-nav-section__';
  let   lastSeqvar  = '';

  function removeSection() {
    document.getElementById(SECTION_ID)?.remove();
  }

  function inject() {
    // Sólo inyectar si hay items de navegación (seqvar o gene page)
    const navItems = document.querySelectorAll('[id$="-nav"]');
    if (!navItems.length) return false;

    const info = parseURL();
    const currentId = info.seqvarId || info.geneURL || window.location.pathname;

    // Evitar doble inyección para la misma variante
    const existing = document.getElementById(SECTION_ID);
    if (existing && lastSeqvar === currentId) return true;
    existing?.remove();
    lastSeqvar = currentId;

    // Encontrar el v-list contenedor
    const vList = navItems[0].closest('.v-list');
    if (!vList) return false;

    const urls = buildURLs(info);
    const gene = info.geneURL || info.geneFromOrig || getGeneFromDOM() || '';

    const div = document.createElement('div');
    div.id = SECTION_ID;
    div.style.cssText = 'border-top:1px solid rgba(255,255,255,.12);margin-top:8px;padding-top:6px';
    div.innerHTML = `
      <div style="padding:4px 16px 6px;font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.08em">
        🧬 Lab Tools
      </div>
      ${labLink('🔬', 'Protein Viewer', urls.proteinUrl, gene ? `Gen: ${gene}` : 'Visualizador 3D de proteínas')}
      ${labLink('📊', 'Variant Tracker', urls.trackerUrl, 'Registrar y seguir esta variante')}
      ${labLink('🧬', 'JBrowse2', urls.jbrowseUrl, info.coords ? `${info.coords.chrom}:${info.coords.pos}` : 'Navegador genómico')}
    `;
    vList.appendChild(div);
    return true;
  }

  function labLink(icon, label, url, tooltip) {
    return `<a href="${url}" target="_blank" title="${tooltip}"
      style="display:flex;align-items:center;gap:10px;padding:6px 16px;color:inherit;text-decoration:none;
             font-size:13px;border-radius:4px;transition:background .12s"
      onmouseover="this.style.background='rgba(255,255,255,.06)'"
      onmouseout="this.style.background=''"
    ><span style="font-size:16px;line-height:1">${icon}</span>${label}</a>`;
  }

  // ── Observer + SPA routing ─────────────────────────────────────────────────

  let observer = null;

  function tryInject() {
    if (inject()) return;

    // Aún no han renderizado los nav items — observar cambios
    if (observer) return;
    observer = new MutationObserver(() => {
      if (inject()) {
        observer.disconnect();
        observer = null;
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Vue Router usa history.pushState para SPA navigation
  const origPush = history.pushState.bind(history);
  history.pushState = function (...args) {
    origPush(...args);
    removeSection();
    setTimeout(tryInject, 200);
  };
  window.addEventListener('popstate', () => { removeSection(); setTimeout(tryInject, 200); });

  // Arrancar
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryInject);
  } else {
    tryInject();
  }
})();
