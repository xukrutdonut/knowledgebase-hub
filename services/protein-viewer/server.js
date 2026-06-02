/**
 * Protein Viewer Server
 * Proxy API para AlphaFold, PDB, UniProt + mapeo de variantes
 * El frontend usa Mol* directamente desde CDN
 */

const express = require("express");
const cors = require("cors");
const compression = require("compression");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

const ALPHAFOLD_API = process.env.ALPHAFOLD_API || "https://alphafold.ebi.ac.uk/api";
const PDB_API = process.env.PDB_API || "https://data.rcsb.org/rest/v1";
const UNIPROT_API = process.env.UNIPROT_API || "https://rest.uniprot.org";
const REEV_API = process.env.REEV_API_URL || "http://reev-backend:8080";

app.use(cors());
app.use(compression());
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

const FETCH_HEADERS = {
  "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
  "Accept": "application/json",
};

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { ...FETCH_HEADERS, ...(options.headers || {}) },
    signal: AbortSignal.timeout(20000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${url}`);
  return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// API: AlphaFold
// ─────────────────────────────────────────────────────────────────────────────

/** GET /api/alphafold/:uniprotId — metadatos + URL del modelo CIF */
app.get("/api/alphafold/:uniprotId", async (req, res) => {
  try {
    const { uniprotId } = req.params;
    const data = await fetchJSON(`${ALPHAFOLD_API}/prediction/${uniprotId}`);
    const entry = Array.isArray(data) ? data[0] : data;
    res.json({
      uniprotId,
      entryId: entry.entryId,
      gene: entry.gene,
      uniprotDescription: entry.uniprotDescription,
      taxId: entry.taxId,
      organismScientificName: entry.organismScientificName,
      cifUrl: entry.cifUrl,
      pdbUrl: entry.pdbUrl,
      paeImageUrl: entry.paeImageUrl,
      paeDocUrl: entry.paeDocUrl,
      confidenceAvgLocalScore: entry.confidenceAvgLocalScore,
      latestVersion: entry.latestVersion,
    });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// API: UniProt → buscar por gen/organismo
// ─────────────────────────────────────────────────────────────────────────────

/** GET /api/uniprot/search?gene=SCN1A&organism=9606 */
app.get("/api/uniprot/search", async (req, res) => {
  try {
    const { gene, organism = "9606" } = req.query;
    if (!gene) return res.status(400).json({ error: "gene requerido" });

    const query = `gene_exact:${gene} AND organism_id:${organism} AND reviewed:true`;
    const url = `${UNIPROT_API}/uniprotkb/search?query=${encodeURIComponent(query)}&fields=accession,gene_names,protein_name,organism_name,length&format=json&size=5`;
    const data = await fetchJSON(url);

    res.json(
      (data.results || []).map((r) => ({
        accession: r.primaryAccession,
        gene: r.genes?.[0]?.geneName?.value,
        protein: r.proteinDescription?.recommendedName?.fullName?.value,
        length: r.sequence?.length,
      }))
    );
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Proxy CIF — sirve archivos CIF desde EBI/RCSB para evitar CORS en el browser
// ─────────────────────────────────────────────────────────────────────────────

/** GET /api/cif/alphafold/:uniprotId — proxy del CIF de AlphaFold */
app.get("/api/cif/alphafold/:uniprotId", async (req, res) => {
  try {
    const { uniprotId } = req.params;
    // Obtener URL exacta desde el API de AlphaFold
    const meta = await fetchJSON(`${ALPHAFOLD_API}/prediction/${uniprotId}`);
    const cifUrl = meta?.[0]?.cifUrl;
    if (!cifUrl) throw new Error("No cifUrl en metadata AlphaFold");
    const response = await fetch(cifUrl, { headers: FETCH_HEADERS, signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    res.set("Content-Type", "text/plain; charset=utf-8");
    res.set("Cache-Control", "public, max-age=86400");
    res.send(await response.text());
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

/** GET /api/cif/pdb/:pdbId — proxy del CIF de RCSB */
app.get("/api/cif/pdb/:pdbId", async (req, res) => {
  try {
    const pdbId = req.params.pdbId.toUpperCase();
    const url = `https://files.rcsb.org/download/${pdbId}.cif`;
    const response = await fetch(url, { headers: FETCH_HEADERS, signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    res.set("Content-Type", "text/plain; charset=utf-8");
    res.set("Cache-Control", "public, max-age=86400");
    const text = await response.text();
    res.send(text);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// API: PDB — estructuras experimentales para un UniProt
// ─────────────────────────────────────────────────────────────────────────────

/** GET /api/pdb/:uniprotId — usa EBI PDBe best_structures */
app.get("/api/pdb/:uniprotId", async (req, res) => {
  try {
    const { uniprotId } = req.params;
    // EBI PDBe API: devuelve estructuras ordenadas por cobertura y resolución
    const data = await fetchJSON(
      `https://www.ebi.ac.uk/pdbe/api/mappings/best_structures/${uniprotId}`
    );
    const entries = (data?.[uniprotId] || []).slice(0, 10).map((e) => ({
      pdbId: e.pdb_id?.toUpperCase(),
      title: e.pdb_id?.toUpperCase(),
      method: e.experimental_method,
      resolution: e.resolution,
      coverage: e.coverage ? Math.round(e.coverage * 100) + "%" : null,
      chainId: e.chain_id,
      uniprotStart: e.uniprot_start,
      uniprotEnd: e.uniprot_end,
      cifUrl: `https://files.rcsb.org/download/${e.pdb_id?.toUpperCase()}.cif`,
    }));
    res.json(entries);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// API: Portales gen-específicos del Grupo Lal (Broad Institute)
// ─────────────────────────────────────────────────────────────────────────────

const LAL_PORTALS = {
  SCN1A: { url: "https://scn-portal.broadinstitute.org/", label: "SCN Portal (Broad)" },
  SCN2A: { url: "https://scn-portal.broadinstitute.org/", label: "SCN Portal (Broad)" },
  SCN8A: { url: "https://scn-portal.broadinstitute.org/", label: "SCN Portal (Broad)" },
  CACNA1A: { url: "https://cacna1a-portal.broadinstitute.org/", label: "CACNA1A Portal (Broad)" },
  GRIN1: { url: "https://grin-portal.broadinstitute.org/", label: "GRIN Portal (Broad)" },
  GRIN2A: { url: "https://grin-portal.broadinstitute.org/", label: "GRIN Portal (Broad)" },
  GRIN2B: { url: "https://grin-portal.broadinstitute.org/", label: "GRIN Portal (Broad)" },
  SATB2: { url: "https://satb2-portal.broadinstitute.org/", label: "SATB2 Portal (Broad)" },
};

const LOVD_GENES = {
  SCN1A: "https://databases.lovd.nl/shared/genes/SCN1A",
  KCNQ2: "https://databases.lovd.nl/shared/genes/KCNQ2",
  CDKL5: "https://databases.lovd.nl/shared/genes/CDKL5",
  PCDH19: "https://databases.lovd.nl/shared/genes/PCDH19",
  SCN2A: "https://databases.lovd.nl/shared/genes/SCN2A",
};

/** GET /api/gene-portals/:gene — devuelve links a portales relevantes */
app.get("/api/gene-portals/:gene", (req, res) => {
  const gene = req.params.gene.toUpperCase();
  const portals = [];

  if (LAL_PORTALS[gene]) portals.push({ type: "lal_broad", ...LAL_PORTALS[gene] });
  if (LOVD_GENES[gene]) portals.push({ type: "lovd", url: LOVD_GENES[gene], label: `LOVD — ${gene}` });

  // Links siempre disponibles
  portals.push(
    { type: "gnomad", url: `https://gnomad.broadinstitute.org/gene/${gene}`, label: "gnomAD" },
    { type: "decipher", url: `https://www.deciphergenomics.org/sequence-variant/search?q=${gene}`, label: "Decipher" },
    { type: "omim", url: `https://www.omim.org/search?search=${gene}`, label: "OMIM" },
    { type: "clinvar", url: `https://www.ncbi.nlm.nih.gov/clinvar/?term=${gene}%5Bgene%5D`, label: "ClinVar" },
    { type: "uniprot", url: `https://www.uniprot.org/uniprotkb?query=${gene}+AND+organism_id:9606+AND+reviewed:true`, label: "UniProt" },
  );

  res.json({ gene, portals });
});

// ─────────────────────────────────────────────────────────────────────────────
// API: AlphaMissense scores (EBI AlphaFold, acceso público sin auth)
// Descarga CSV: AF-{UniProt}-F1-aa-substitutions.csv y devuelve scores
// filtrados por posición/variante
// ─────────────────────────────────────────────────────────────────────────────

/** GET /api/alphamissense/:uniprotId?pos=1708&ref=A&alt=E */
app.get("/api/alphamissense/:uniprotId", async (req, res) => {
  const { uniprotId } = req.params;
  const { pos, ref, alt } = req.query;

  try {
    const csvUrl = `https://alphafold.ebi.ac.uk/files/AF-${uniprotId}-F1-aa-substitutions.csv`;
    const response = await fetch(csvUrl, { signal: AbortSignal.timeout(30000) });
    if (!response.ok) throw new Error(`AlphaMissense CSV no disponible para ${uniprotId}`);

    const text = await response.text();
    const lines = text.trim().split("\n");
    const header = lines[0].split(","); // protein_variant,am_pathogenicity,am_class

    let rows = lines.slice(1).map((l) => {
      const [variant, score, cls] = l.split(",");
      return {
        variant,                         // e.g. "A1708E"
        am_pathogenicity: parseFloat(score),
        am_class: cls?.trim(),           // "likely_pathogenic" | "ambiguous" | "likely_benign"
        position: parseInt(variant.slice(1, -1)),
        ref_aa: variant[0],
        alt_aa: variant.slice(-1),
      };
    });

    // Filtrar si se proporcionan parámetros
    if (pos) rows = rows.filter((r) => r.position === parseInt(pos));
    if (ref) rows = rows.filter((r) => r.ref_aa === ref.toUpperCase());
    if (alt) rows = rows.filter((r) => r.alt_aa === alt.toUpperCase());

    // Límite 500 filas para evitar respuestas masivas sin filtro
    const total = rows.length;
    rows = rows.slice(0, 500);

    res.json({ uniprotId, total, returned: rows.length, rows });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// API: Pathogenicity predictors — links/scores disponibles online
// ─────────────────────────────────────────────────────────────────────────────

/** GET /api/predictors/:chrom/:pos/:ref/:alt?build=GRCh38 */
app.get("/api/predictors/:chrom/:pos/:ref/:alt", (req, res) => {
  const { chrom, pos, ref, alt } = req.params;
  const build = req.query.build || "GRCh38";
  const hg = build === "GRCh38" ? "hg38" : "hg19";

  res.json({
    variant: `${chrom}:${pos}:${ref}:${alt}`,
    predictors: [
      {
        name: "CADD",
        url: `https://cadd.gs.washington.edu/snv/${hg}_${chrom}_${pos}_${ref}_${alt}`,
        description: "Combined Annotation Dependent Depletion",
      },
      {
        name: "SpliceAI Lookup",
        url: `https://spliceailookup.broadinstitute.org/?variant=${chrom}-${pos}-${ref}-${alt}&hg=${hg === "hg38" ? "38" : "19"}`,
        description: "Predicción impacto en splicing",
      },
      {
        name: "MutPred2",
        url: "http://mutpred.mutdb.org/",
        description: "Predicción patogenicidad y mecanismo molecular",
      },
      {
        name: "DynaMut2",
        url: "http://biosig.unimelb.edu.au/dynamut2/",
        description: "Efecto en estabilidad proteica",
      },
      {
        name: "Missense3D",
        url: "http://www.sbg.bio.ic.ac.uk/~missense3d/",
        description: "Impacto estructural de variantes missense",
      },
      {
        name: "EVE",
        url: "https://evemodel.org/",
        description: "Evolutionary model of Variant Effect (DeepMind/Harvard)",
      },
      {
        name: "AlphaMissense",
        url: `https://alphamissense.hegelab.org/`,
        description: "Predicción patogenicidad missense (Google DeepMind)",
      },
    ],
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Sirve la SPA para todas las rutas no-API
// ─────────────────────────────────────────────────────────────────────────────

app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`🔬 Protein Viewer running on http://0.0.0.0:${PORT}`);
});
