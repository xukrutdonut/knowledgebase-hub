/**
 * lab-nav.js v6 — Inyecta botones Lab Tools en columna izquierda de REEV.
 * Usa console.error para visibilidad en DevTools aunque esté en modo Errors.
 */
try {
(function () {
  'use strict';

  const V = 'v6';
  const PROTEIN_URL = 'https://protein.neuropedialab.org';
  const TRACKER_URL = 'https://tracker.neuropedialab.org';
  const DBG = '[LabNav ' + V + ']';

  // Inject style to make the bookmark button red
  const style = document.createElement('style');
  style.textContent = `
    i.mdi-bookmark, i.mdi-bookmark-outline {
      color: #ef4444 !important;
    }
    .v-btn:has(.mdi-bookmark), .v-btn:has(.mdi-bookmark-outline) {
      color: #ef4444 !important;
      border-color: #ef4444 !important;
    }
  `;
  if (document.head) {
    document.head.appendChild(style);
  } else {
    document.documentElement.appendChild(style);
  }

  // Visual badge — confirma que el script se ejecuta
  function showBadge(msg) {
    const b = document.createElement('div');
    b.id = '__labnav-badge__';
    b.textContent = msg;
    b.style.cssText = 'position:fixed;bottom:12px;right:12px;z-index:99999;background:#1565c0;color:#fff;padding:6px 12px;border-radius:6px;font-size:13px;font-family:sans-serif;pointer-events:none';
    document.body?.appendChild(b);
    setTimeout(() => b.remove(), 5000);
  }

  function parseURL() {
    const path = window.location.pathname;
    const orig = new URLSearchParams(window.location.search).get('orig') || '';
    const seqvarMatch = path.match(/\/seqvar\/([^/?]+)/);
    const geneMatch   = path.match(/\/gene\/([^/?]+)/);
    let coords = null;
    if (seqvarMatch) {
      const p = seqvarMatch[1].split('-');
      if (p.length >= 5) coords = { build:p[0], chrom:p[1], pos:p[2], ref:p[3], alt:p.slice(4).join('-') };
    }
    const geneRe  = orig.match(/\(([A-Z][A-Z0-9-]+)\)/);
    const txRe    = orig.match(/^(NM_[0-9]+\.[0-9]+)/);
    const hgvsCRe = orig.match(/(c\.[^\s]+)/);
    return {
      isSeqvar: !!seqvarMatch, isGene: !!geneMatch,
      geneURL: geneMatch ? geneMatch[1] : null,
      coords, orig,
      geneFromOrig:       geneRe  ? geneRe[1]  : null,
      transcriptFromOrig: txRe    ? txRe[1]    : null,
      hgvsC:              hgvsCRe ? hgvsCRe[1] : null,
    };
  }

  function getGeneFromDOM() {
    for (const s of document.querySelectorAll('.font-italic')) {
      const t = s.textContent.trim();
      if (t && /^[A-Z][A-Z0-9-]+$/.test(t) && t.length > 1) return t;
    }
    return null;
  }

  function getHgvsPFromDOM() {
    const text = document.body.innerText;
    const match = text.match(/p\.(?:([A-Z][a-z]{2}|[A-Z]))(\d+)(?:([A-Z][a-z]{2}|[A-Z]))/);
    if (match) {
      return {
        hgvs_p: match[0],
        ref: match[1],
        pos: match[2],
        alt: match[3]
      };
    }
    return null;
  }

  function getAcmgFromDOM() {
    const text = document.body.innerText;
    if (text.match(/likely\s+pathogenic/i)) return "Likely_pathogenic";
    if (text.match(/pathogenic/i)) return "Pathogenic";
    if (text.match(/likely\s+benign/i)) return "Likely_benign";
    if (text.match(/benign/i)) return "Benign";
    if (text.match(/vus|uncertain/i)) return "Uncertain_significance";
    return "";
  }

  function buildURLs(info) {
    const gene = info.geneURL || info.geneFromOrig || getGeneFromDOM() || '';
    let proteinUrl = PROTEIN_URL + '/';
    if (gene) {
      proteinUrl += `?gene=${encodeURIComponent(gene)}`;
      const pInfo = getHgvsPFromDOM();
      if (pInfo) {
        proteinUrl += `&pos=${pInfo.pos}&ref=${pInfo.ref}&alt=${pInfo.alt}&hgvs=${encodeURIComponent(pInfo.hgvs_p)}`;
        const acmg = getAcmgFromDOM();
        if (acmg) {
          proteinUrl += `&acmg=${acmg}`;
        }
      }
      if (info.coords) {
        proteinUrl += `&chrom=${encodeURIComponent(info.coords.chrom)}&gpos=${encodeURIComponent(info.coords.pos)}&gref=${encodeURIComponent(info.coords.ref)}&galt=${encodeURIComponent(info.coords.alt)}&build=${encodeURIComponent(info.coords.build)}`;
      }
    }
    const tp = new URLSearchParams();
    if (info.coords) { tp.set('build',info.coords.build); tp.set('chrom',info.coords.chrom); tp.set('pos',info.coords.pos); tp.set('ref',info.coords.ref); tp.set('alt',info.coords.alt); }
    if (gene)                    tp.set('gene', gene);
    if (info.hgvsC)              tp.set('hgvs_c', info.hgvsC);
    if (info.transcriptFromOrig) tp.set('transcript', info.transcriptFromOrig);
    return { proteinUrl, trackerUrl: `${TRACKER_URL}/?${tp}` };
  }

  // Estrategias múltiples para encontrar el contenedor de navegación izquierda
  function findNavContainer() {
    // 1. Sticky div por style inline
    const sticky = document.querySelector('[style*="sticky"]');
    if (sticky) { console.error(DBG, 'findNav: sticky div found'); return sticky; }

    // 2. Div padre del v-list principal
    const vList = document.querySelector('.v-list');
    if (vList) { console.error(DBG, 'findNav: v-list parent found'); return vList.parentElement; }

    // 3. El v-navigation-drawer o aside izquierdo
    const drawer = document.querySelector('.v-navigation-drawer, aside');
    if (drawer) { console.error(DBG, 'findNav: drawer found'); return drawer; }

    console.error(DBG, 'findNav: NONE found. body children:', document.body?.children?.length);
    return null;
  }

  function makeBtn(icon, label, url, id) {
    const btn = document.createElement('a');
    btn.id = id; btn.href = url; btn.target = '_blank'; btn.rel = 'noopener';
    btn.className = 'v-btn v-btn--density-default v-btn--size-default v-btn--variant-outlined ma-2';
    btn.style.cssText = 'text-decoration:none;display:inline-flex;align-items:center;width:calc(100% - 16px);margin-top:4px';
    btn.innerHTML = `<span class="v-btn__overlay"></span><span class="v-btn__underlay"></span>` +
      `<i class="mdi ${icon} v-icon notranslate v-icon--size-default" aria-hidden="true" style="font-size:18px;margin-right:8px"></i>` +
      `<span class="v-btn__content" style="font-size:12px">${label}</span>`;
    return btn;
  }

  let lastVariant = '';

  function inject() {
    const path = window.location.pathname;
    if (!/\/(seqvar|gene)\//.test(path)) {
      return false; // Página normal de REEV, sin botones adicionales
    }

    const nav = findNavContainer();
    if (!nav) return false;

    const info = parseURL();
    const currentId = info.coords ? `${info.coords.chrom}-${info.coords.pos}` : path;

    if (document.getElementById('__lab-protein-btn__') && lastVariant === currentId) {
      const btn = document.getElementById('__lab-protein-btn__');
      const pInfo = getHgvsPFromDOM();
      if (path.includes('/seqvar/') && !btn.href.includes('&pos=') && pInfo) {
        const urls = buildURLs(info);
        btn.href = urls.proteinUrl;
        const tBtn = document.getElementById('__lab-tracker-btn__');
        if (tBtn) tBtn.href = urls.trackerUrl;
      }
      return (!path.includes('/seqvar/') || btn.href.includes('&pos='));
    }
    document.getElementById('__lab-protein-btn__')?.remove();
    document.getElementById('__lab-tracker-btn__')?.remove();
    lastVariant = currentId;

    const urls = buildURLs(info);
    console.error(DBG, 'Injecting buttons. Protein:', urls.proteinUrl.slice(0,60));
    console.error(DBG, 'Nav container:', nav.tagName, nav.className?.slice(0,50));

    const pBtn = makeBtn('mdi-molecule',               'Protein Viewer', urls.proteinUrl, '__lab-protein-btn__');
    const tBtn = makeBtn('mdi-clipboard-list-outline', 'Variant Tracker', urls.trackerUrl, '__lab-tracker-btn__');

    // Insertar después del v-list, dentro del contenedor sticky
    const vListInNav = nav.querySelector('.v-list') || nav;
    vListInNav.insertAdjacentElement('afterend', tBtn);
    vListInNav.insertAdjacentElement('afterend', pBtn);

    showBadge('✓ Lab Tools inyectados');
    console.error(DBG, 'Done. Parent of pBtn:', pBtn.parentElement?.tagName, pBtn.parentElement?.className?.slice(0,40));
    return (!path.includes('/seqvar/') || pBtn.href.includes('&pos='));
  }

  let pollTimer = null, pollCount = 0;
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollCount = 0;
    console.error(DBG, 'startPolling for:', window.location.pathname);
    pollTimer = setInterval(() => {
      pollCount++;
      if (pollCount % 5 === 0) console.error(DBG, 'poll#' + pollCount, 'path:', window.location.pathname);
      if (inject() || pollCount > 75) {
        clearInterval(pollTimer);
        pollTimer = null;
        if (pollCount > 75) console.error(DBG, 'Polling timeout — nav never found');
      }
    }, 400);
  }

  function onNavigate() {
    document.getElementById('__lab-protein-btn__')?.remove();
    document.getElementById('__lab-tracker-btn__')?.remove();
    lastVariant = '';
    setTimeout(startPolling, 50);
  }

  const origPush = history.pushState.bind(history);
  history.pushState = function (...a) { origPush(...a); onNavigate(); };
  window.addEventListener('popstate', onNavigate);

  console.error(DBG, 'Script loaded. Path:', window.location.pathname);
  showBadge('⚡ LabNav ' + V + ' cargado');
  startPolling();
})();
} catch(e) { console.error('[LabNav CRASH]', e.message, e.stack); }
