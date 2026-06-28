"""
NeuropedGx Hub — Panel genético neuropediátrico multi-grupo
FastAPI backend
"""
from __future__ import annotations

import json
import os
import sqlite3
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Settings
# ─────────────────────────────────────────────────────────────

_APP_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    reev_api_url: str = "http://reev-backend:8080"
    reev_external_url: str = "http://localhost:8200"
    protein_viewer_url: str = "http://protein-viewer:3000"       # interno Docker
    protein_viewer_external_url: str = "https://protein.neuropedialab.org"  # URL del navegador
    reev_external_url: str = "https://reev.neuropedialab.org"
    variant_tracker_url: str = "http://variant-tracker:8000"
    in_silico_api_url: str = "http://in-silico-api:8000"
    gene_panel_path: Path = _APP_DIR / "data" / "gene_panel.yml"
    db_path: Path = Path("/tmp/knowledgebase.db")

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()

# ─────────────────────────────────────────────────────────────
#  Gene Panel Database (SQLite — generado desde YAML)
# ─────────────────────────────────────────────────────────────

DEFAULT_GROUP_METADATA: dict[str, dict[str, str]] = {
    # ── Canalopatías / Transportopatías ───────────────────────────────────────
    "channelopathy": {"label": "Canalopatías", "description": "Disfunción de canales iónicos (Na, K, Ca, Cl, HCN)"},
    "channelopathy_sodium": {"label": "→ Canales de Sodio", "description": "Canalopatías de sodio (SCN1A, SCN1B, SCN2A, SCN8A, SCN9A)"},
    "channelopathy_potassium": {"label": "→ Canales de Potasio", "description": "Canalopatías de potasio (KCNQ2, KCNQ3, KCNA1, KCNB1, KCNC1)"},
    "channelopathy_calcium": {"label": "→ Canales de Calcio", "description": "Canalopatías de calcio (CACNA1A, CACNA1D, CACNA1E, CACNB4)"},
    "channelopathy_chloride": {"label": "→ Canales de Cloro", "description": "Canalopatías de cloro (GABRG2, GABRA1, GABRD, SLC6A5)"},
    "channelopathy_glutamate": {"label": "→ Receptores de Glutamato", "description": "Canalopatías de glutamato (GRIN1, GRIN2A, GRIN2B, GRM1)"},
    "channelopathy_gaba": {"label": "→ Receptores de GABA", "description": "Canalopatías de GABA (GABRB2, GABRB3, GABRG2)"},
    "channelopathy_glycine": {"label": "→ Receptores de Glicina", "description": "Canalopatías de glicina (GLRA1, SLC6A5)"},
    "transportopathy": {"label": "Transportopatías", "description": "Alteraciones de transportadores de membrana: SLC, ABC, ATPasas"},
    "transportopathy_nt_reuptake": {"label": "→ Recaptación de NT", "description": "Transportadores de recaptación (SLC6A2, SLC6A3, SLC6A4)"},
    "transportopathy_vesicular": {"label": "→ Transportadores Vesiculares", "description": "Transportadores vesiculares de NT (SLC18A2, SLC18A3)"},
    "transportopathy_amino_acid": {"label": "→ Aminoácidos", "description": "Transportadores de aminoácidos (SLC7A5, SLC1A1, SLC25A12)"},
    "transportopathy_ion_pumps": {"label": "→ Bombas Iónicas", "description": "ATPasas y bombas iónicas (ATP1A3, ATP1B2, ATP2A2)"},
    "transportopathy_solute_carriers": {"label": "→ Otros SLC", "description": "Otros transportadores SLC (SLC25A1, SLC30A10, SLC9A6)"},
    # ── Errores NT & cofactores ───────────────────────────────────────────────
    "neurotransmitter_defect": {"label": "Errores NT (visión global)", "description": "Trastornos del metabolismo de neurotransmisores (marco García-Cazorla)"},
    "nt_synthesis": {"label": "Síntesis NT", "description": "Errores en síntesis de dopamina, serotonina, NA (GCH1, TH, SPR, AADC)"},
    "nt_vesicle": {"label": "Vesículas sinápticas NT", "description": "Almacenamiento y liberación vesicular de NT (SLC18A2, SNAP25, DNM1)"},
    "nt_reuptake": {"label": "Recaptación NT", "description": "Transportadores de recaptación presináptica (SLC6A2/3/4)"},
    "nt_catabolism": {"label": "Catabolismo NT", "description": "Degradación de neurotransmisores (MAOA, ALDH9A1)"},
    "cofactor_nt": {"label": "Cofactores NT (BH4/PLP/folato)", "description": "Metabolismo de BH4, piridoxina/PLP, folato cerebral (QDPR, PTS, DNAJC12, PNPO, FOLR1)"},
    "gaba_metabolism": {"label": "Metabolismo GABA", "description": "Síntesis y degradación de GABA (ALDH5A1/SSADH, ABAT/GABA-T, GAD1)"},
    "nkh": {"label": "Hiperglicinemia no cetósica (NKH)", "description": "Sistema de clivaje de glicina (GLDC, AMT, GCSH)"},
    "purine_metabolism": {"label": "Metabolismo de Purinas", "description": "Errores de purinas con manifestación neurológica (HPRT1/Lesch-Nyhan, ADSL, ATIC)"},
    # ── ECM clásicos ──────────────────────────────────────────────────────────
    "organic_acidemia": {"label": "Acidemias Orgánicas", "description": "Acidemias propiónica, metilmalónica, isovalérica y relacionadas"},
    "mitochondrial": {"label": "Mitocondrial", "description": "Trastornos de la cadena respiratoria y ADN mitocondrial"},
    "lysosomal": {"label": "Enfermedades Lisosomales", "description": "Enfermedades de depósito lisosomal con afectación neurológica"},
    "peroxisomal": {"label": "Enfermedades Peroxisomales", "description": "Biogénesis y función peroxisomal (PEX, ABCD1, PHYH)"},
    "cdg": {"label": "CDG (Glicosilación)", "description": "Trastornos congénitos de la glicosilación (PMM2, ALG, SRD5A3…)"},
    "creatine_disorder": {"label": "Trastornos de Creatina", "description": "Síntesis y transporte de creatina (GAMT, GATM, SLC6A8)"},
    "leukodystrophy": {"label": "Leucodistrofias", "description": "Trastornos de la sustancia blanca y mielina"},
    "metabolic": {"label": "Metabólico (otros ECM)", "description": "Otros errores innatos del metabolismo neurológico"},
    # ── Trastornos del Neurodesarrollo ────────────────────────────────────────
    "rasopathy": {"label": "Rasopatías", "description": "Alteraciones de la vía RAS/MAPK (Noonan, CFC, Costello, NF1…)"},
    "mtoropathy": {"label": "mTORopatías", "description": "Alteraciones de la vía PI3K/AKT/mTOR (TSC, PTEN, AKT3…)"},
    "cohesinopathy": {"label": "Cohesinopías", "description": "Alteraciones del complejo cohesina (Cornelia de Lange)"},
    "microtubulipathy": {"label": "Microtubulopatías", "description": "Alteraciones de tubulina y proteínas motoras (lissencefalia, PMG)"},
    "chromatin_remodeling": {"label": "Remodelación de cromatina", "description": "Modificadores de histonas, SWI/SNF, NuRD, metiltransferasas"},
    "transcription_factor": {"label": "Factores de transcripción", "description": "NDD por alteración de TF neurológicos"},
    "synaptopathy": {"label": "Sinaptopatías", "description": "Alteraciones de proteínas sinápticas y PSD"},
    "ciliopathy": {"label": "Ciliopatías", "description": "Trastornos de la función ciliar"},
    "xlid": {"label": "DI ligada al X", "description": "Discapacidad intelectual ligada al cromosoma X (MECP2, FMR1, ARX…)"},
    "id_syndromic": {"label": "DI sindrómica", "description": "Discapacidad intelectual asociada a rasgos dismórficos, malformaciones o afectación multisistémica"},
    "id_nonsyndromic": {"label": "DI no sindrómica", "description": "Discapacidad intelectual sin dismorfias ni afectación sistémica mayor (autosómica)"},
    "microcephaly": {"label": "Microcefalia", "description": "Microcefalia primaria y secundaria (MCPH, CENPJ, CDK5RAP2…)"},
    "autism_specific": {"label": "Autismo (genética)", "description": "Genes de alta penetrancia para TEA (SHANK3, SYNGAP1, ADNP…)"},
    "neuromuscular": {"label": "Neuromuscular (otros)", "description": "Miopatías, neuropatías y enfermedades de motoneurona de inicio pediátrico"},
    "muscular_dystrophy": {"label": "Distrofias Musculares", "description": "Duchenne, Becker, LGMD, miotonía de Steinert, EDMD"},
    "congenital_md": {"label": "Distrofias Musculares Congénitas", "description": "MDC merosin-deficiente, Ullrich, Fukuyama, Walker-Warburg, alfa-distroglicanopías"},
    "metabolic_myopathy": {"label": "Miopatías Metabólicas", "description": "Pompe (GSD II), McArdle (GSD V), CPT2, VLCAD, MCAD, glucogenosis musculares"},
    "congenital_myopathy": {"label": "Miopatías Congénitas", "description": "Core disease (RYR1), miotubular (MTM1), nemalínica (NEB, ACTA1, TPM), centronuclear"},
    "genetic_neuropathy": {"label": "Neuropatías Genéticas", "description": "Charcot-Marie-Tooth (CMT1A/B, CMT2A, CMTX) y neuropatías hereditarias relacionadas"},
    "other_ndd": {"label": "Otro TND", "description": "Trastornos neurológicos del desarrollo sin clasificación principal"},
    # ── Por fenotipo clínico (cross-cutting) ──────────────────────────────────
    "dee": {"label": "Encefalopatías Epilépticas del Desarrollo (DEE)", "description": "DEE de base genética — cross-cutting"},
    "dystonia": {"label": "Distonía", "description": "Distonías primarias y combinadas de base genética (DYT, KMT2B, ATP1A3…)"},
    "parkinsonism_early": {"label": "Parkinsonismo precoz", "description": "Parkinsonismo de inicio en edad pediátrica o juvenil (PARK genes, PLA2G6…)"},
    "ataxia": {"label": "Ataxia", "description": "Ataxias hereditarias (ATXN, SETX, APTX, POLG, SCA…)"},
    "spastic_paraplegia": {"label": "Paraparesia Espástica Hereditaria", "description": "PEH pura y complicada (SPG genes, ATL1, REEP1, SPAST…)"},
    # ── Inmunoneurología ──────────────────────────────────────────────────────
    "interferonopathy": {"label": "Interferonopías", "description": "Síndrome Aicardi-Goutières y trastornos IFN-I (RNASEH2, TREX1, STING1…)"},
    "autoinflammatory_cns": {"label": "Autoinflamatorio SNC", "description": "Enfermedades autoinflamatorias con manifestación neurológica (DADA2, CAPS, FMF…)"},
    "complement_neuro": {"label": "Complemento Neuro", "description": "Trastornos del complemento con manifestación neurológica"},
    # ── Inestabilidad genómica ────────────────────────────────────────────────
    "dna_repair": {"label": "Reparación de DNA", "description": "Síndromes de inestabilidad genómica (AT, XP, NBS, CS…)"},
    # ── Mecanismos genómicos especiales ──────────────────────────────────────
    "repeat_expansion": {"label": "Expansión de repeticiones (STR)", "description": "Enfermedades causadas por expansión de tripletes u otras repeticiones: FragileX, ataxias SCA, Friedreich, DM1, SCA6/CACNA1A…"},
    "imprinting_epigenetic": {"label": "Imprinting y Epigenética", "description": "Trastornos por imprinting genómico, UPD o alteración epigenética: Prader-Willi, Angelman, Beckwith-Wiedemann, Temple…"},
    "genomic_cnv": {"label": "Síndromes por CNV/deleción", "description": "Síndromes por deleciones/duplicaciones recurrentes: 22q11 DiGeorge, Williams, Smith-Magenis, Phelan-McDermid, Koolen-de Vries…"},
}


def build_sqlite_db(panel_path: Path, db_path: Path) -> sqlite3.Connection:
    """Carga el YAML curado y genera una BD SQLite en memoria/disco."""
    with open(panel_path) as f:
        panel = yaml.safe_load(f)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.executescript("""
        DROP TABLE IF EXISTS gene_groups;
        DROP TABLE IF EXISTS groups;
        DROP TABLE IF EXISTS genes;

        CREATE TABLE genes (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            hgnc_id TEXT,
            uniprot TEXT,
            omim_code TEXT,
            genereviews_id TEXT,
            mechanism_groups TEXT,   -- JSON array
            clinical_labels TEXT,    -- JSON array
            mechanism TEXT,          -- JSON array
            inheritance TEXT,        -- JSON array
            phenotypes TEXT,         -- JSON array
            symptoms TEXT,           -- JSON array
            key_domains TEXT,        -- JSON array of objects
            hotspots TEXT,           -- JSON array of objects
            interpretation_notes TEXT, -- JSON array
            acmg_guidance TEXT,      -- JSON array of objects
            clingen TEXT,            -- JSON object
            sources TEXT             -- JSON array
        );

        CREATE TABLE groups (
            id TEXT PRIMARY KEY,
            label TEXT,
            description TEXT,
            color TEXT,
            pathway_svg TEXT,
            key_interpretation_notes TEXT  -- JSON array
        );

        CREATE TABLE gene_groups (
            gene_symbol TEXT,
            group_id TEXT,
            PRIMARY KEY (gene_symbol, group_id)
        );
    """)

    genes = panel.get("genes", {})
    for symbol, data in genes.items():
        cur.execute("""
            INSERT OR REPLACE INTO genes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            symbol,
            data.get("name", ""),
            str(data.get("hgnc_id", "")),
            data.get("uniprot", ""),
            data.get("omim_code", ""),
            data.get("genereviews_id", ""),
            json.dumps(data.get("mechanism_groups", [])),
            json.dumps(data.get("clinical_labels", [])),
            json.dumps(data.get("mechanism", [])),
            json.dumps(data.get("inheritance", [])),
            json.dumps(data.get("phenotypes", [])),
            json.dumps(data.get("symptoms", [])),
            json.dumps(data.get("key_domains", [])),
            json.dumps(data.get("hotspots", [])),
            json.dumps(data.get("interpretation_notes", [])),
            json.dumps(data.get("acmg_guidance", [])),
            json.dumps(data.get("clingen", {})),
            json.dumps(data.get("sources", [])),
        ))
        for grp in data.get("mechanism_groups", []):
            cur.execute("INSERT OR IGNORE INTO gene_groups VALUES (?,?)", (symbol, grp))
    
    # Mapeo automático de genes a subcategorías de canalopatías y transportopatías
    _map_subcategories(cur, genes)

    _populate_groups(cur, panel.get("groups") or None)
    conn.commit()
    logger.info(f"✅ Gene panel DB built: {len(genes)} genes")
    return conn




def _map_subcategories(cur: sqlite3.Cursor, genes: dict[str, Any]):
    """Mapea genes a subcategorías de canalopatías y transportopatías."""
    # Canalopatías por tipo de canal iónico
    channelopathy_subcat = {
        "channelopathy_sodium": ["SCN1A", "SCN1B", "SCN2A", "SCN8A", "SCN9A"],
        "channelopathy_potassium": ["KCNQ2", "KCNQ3", "KCNA1", "KCNB1", "KCNC1", "KCND2", "KCNF1", "KCNH1"],
        "channelopathy_calcium": ["CACNA1A", "CACNA1D", "CACNA1E", "CACNB4", "CACNB2"],
        "channelopathy_chloride": ["GABRG2", "GABRA1", "GABRD", "SLC6A5"],
        "channelopathy_glutamate": ["GRIN1", "GRIN2A", "GRIN2B", "GRM1"],
        "channelopathy_gaba": ["GABRB2", "GABRB3", "GABRG2", "GABRA1"],
        "channelopathy_glycine": ["GLRA1", "SLC6A5"],
    }
    
    # Transportopatías por tipo
    transportopathy_subcat = {
        "transportopathy_nt_reuptake": ["SLC6A2", "SLC6A3", "SLC6A4", "SLC6A1"],
        "transportopathy_vesicular": ["SLC18A2", "SLC18A3"],
        "transportopathy_amino_acid": ["SLC7A5", "SLC1A1", "SLC25A12"],
        "transportopathy_ion_pumps": ["ATP1A3", "ATP1B2", "ATP2A2"],
        "transportopathy_solute_carriers": ["SLC25A1", "SLC30A10", "SLC9A6", "ABCC8"],
    }
    
    for subcat, gene_list in {**channelopathy_subcat, **transportopathy_subcat}.items():
        for gene_symbol in gene_list:
            if gene_symbol in genes:
                cur.execute("INSERT OR IGNORE INTO gene_groups VALUES (?,?)", (gene_symbol, subcat))


def _populate_groups(cur: sqlite3.Cursor, panel_groups: list[Any]):
    if not panel_groups:
        configured_groups = list(DEFAULT_GROUP_METADATA.keys())
    else:
        configured_groups = panel_groups
    seen: set[str] = set()

    for entry in configured_groups:
        if isinstance(entry, str):
            gid = entry
            metadata = {"id": gid, **DEFAULT_GROUP_METADATA.get(gid, {})}
        else:
            gid = entry.get("id", "")
            metadata = {**DEFAULT_GROUP_METADATA.get(gid, {}), **entry}

        if not gid or gid in seen:
            continue

        seen.add(gid)
        label = metadata.get("label") or gid.replace("_", " ").title()
        description = metadata.get("description", "")
        color = metadata.get("color")
        cur.execute(
            "INSERT OR IGNORE INTO groups VALUES (?,?,?,?,?,?)",
            (gid, label, description, color, None, json.dumps([])),
        )


# Global DB connection (set in lifespan)
_db: sqlite3.Connection | None = None

def get_db() -> sqlite3.Connection:
    if _db is None:
        raise RuntimeError("DB not initialized")
    return _db


# ─────────────────────────────────────────────────────────────
#  Pydantic models
# ─────────────────────────────────────────────────────────────

class GeneInfo(BaseModel):
    symbol: str
    name: str
    hgnc_id: str
    uniprot: str | None
    omim_code: str | None = None
    genereviews_id: str | None = None
    mechanism_groups: list[str]
    clinical_labels: list[str]
    mechanism: list[str]
    inheritance: list[str]
    phenotypes: list[str]
    symptoms: list[str] = Field(default_factory=list)
    key_domains: list[dict]
    hotspots: list[dict]
    interpretation_notes: list[str]
    acmg_guidance: list[dict]
    clingen: dict
    sources: list[dict]
    links: dict = Field(default_factory=dict)


class GroupInfo(BaseModel):
    id: str
    label: str
    description: str
    color: str | None = None
    gene_count: int


class VariantQuery(BaseModel):
    gene: str
    genome_build: str = "GRCh38"
    chrom: str | None = None
    pos: int | None = None
    ref: str | None = None
    alt: str | None = None
    hgvs_c: str | None = None
    hgvs_p: str | None = None
    transcript: str | None = None
    hpo_terms: list[str] | None = None


class VariantReport(BaseModel):
    gene: GeneInfo
    variant: dict
    mechanism_flags: list[str]
    interpretation_guidance: list[str]
    acmg_criteria_hints: list[dict]
    hotspot_match: dict | None
    reev_url: str | None
    protein_viewer_url: str | None
    in_silico: dict | None = None
    disclaimer: str


# ─────────────────────────────────────────────────────────────
#  App lifespan
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db
    settings = get_settings()
    _db = build_sqlite_db(settings.gene_panel_path, settings.db_path)
    yield
    if _db:
        _db.close()


app = FastAPI(
    title="knowledgeDB.neuropediaLAB",
    description=(
        "Panel genético neuropediátrico multi-grupo: canalopatías, rasopatías, "
        "mTORopatías, cohesinopías, microtubulopatías y más. "
        "Capa de recomendación clínica sobre REEV/auto-ACMG. "
        "Vías KEGG integradas para cada categoría."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
#  Helper: parse gene row
# ─────────────────────────────────────────────────────────────

def _row_to_gene(row: sqlite3.Row, settings: Settings) -> GeneInfo:
    uniprot = row["uniprot"] or ""
    omim_code = row["omim_code"] or ""
    genereviews_id = row["genereviews_id"] or ""
    links = {}
    if uniprot:
        links["uniprot"] = f"https://www.uniprot.org/uniprot/{uniprot}"
        links["alphafold"] = f"https://alphafold.ebi.ac.uk/entry/{uniprot}"
        links["protein_viewer"] = f"{settings.protein_viewer_external_url}/?gene={row['symbol']}"
    
    # OMIM: solo si existe omim_code
    if omim_code:
        links["omim"] = f"https://www.omim.org/entry/{omim_code}"
    
    # GeneReviews: solo si existe genereviews_id
    if genereviews_id:
        links["genereviews"] = f"https://www.ncbi.nlm.nih.gov/books/{genereviews_id}"
    
    links["clinvar"] = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={row['symbol']}[gene]"
    links["gnomad"] = f"https://gnomad.broadinstitute.org/gene/{row['symbol']}"
    links["reev"] = f"{settings.reev_external_url}/gene/{row['symbol']}"

    return GeneInfo(
        symbol=row["symbol"],
        name=row["name"],
        hgnc_id=row["hgnc_id"],
        uniprot=uniprot or None,
        omim_code=omim_code or None,
        genereviews_id=genereviews_id or None,
        mechanism_groups=json.loads(row["mechanism_groups"]),
        clinical_labels=json.loads(row["clinical_labels"]),
        mechanism=json.loads(row["mechanism"]),
        inheritance=json.loads(row["inheritance"]),
        phenotypes=json.loads(row["phenotypes"]),
        symptoms=json.loads(row["symptoms"]),
        key_domains=json.loads(row["key_domains"]),
        hotspots=json.loads(row["hotspots"]),
        interpretation_notes=json.loads(row["interpretation_notes"]),
        acmg_guidance=json.loads(row["acmg_guidance"]),
        clingen=json.loads(row["clingen"]),
        sources=json.loads(row["sources"]),
        links=links,
    )


# ─────────────────────────────────────────────────────────────
#  Routes — Gene Panel
# ─────────────────────────────────────────────────────────────

@app.get("/api/genes", response_model=list[GeneInfo], tags=["Genes"])
def list_genes(
    group: str | None = Query(None, description="Filtrar por grupo (e.g. channelopathy)"),
    label: str | None = Query(None, description="Filtrar por etiqueta clínica (e.g. dee)"),
    q: str | None = Query(None, description="Búsqueda por símbolo o nombre"),
):
    """Lista todos los genes del panel, con filtros opcionales."""
    settings = get_settings()
    db = get_db()

    if group:
        rows = db.execute(
            "SELECT g.* FROM genes g JOIN gene_groups gg ON g.symbol=gg.gene_symbol WHERE gg.group_id=?",
            (group,)
        ).fetchall()
    elif label:
        rows = db.execute(
            "SELECT * FROM genes WHERE json_each.value=? "
            "AND clinical_labels = json_each.value",
            (label,)
        ).fetchall()
        # Fallback: LIKE search
        if not rows:
            rows = db.execute(
                "SELECT * FROM genes WHERE clinical_labels LIKE ?",
                (f'%"{label}"%',)
            ).fetchall()
    elif q:
        q_like = f"%{q.upper()}%"
        rows = db.execute(
            "SELECT * FROM genes WHERE upper(symbol) LIKE ? OR upper(name) LIKE ?",
            (q_like, q_like)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM genes ORDER BY symbol").fetchall()

    return [_row_to_gene(r, settings) for r in rows]


@app.get("/api/genes/{symbol}", response_model=GeneInfo, tags=["Genes"])
def get_gene(symbol: str):
    """Información completa de un gen: grupos, mecanismo, dominios, notas de interpretación."""
    settings = get_settings()
    db = get_db()
    row = db.execute("SELECT * FROM genes WHERE upper(symbol)=upper(?)", (symbol,)).fetchone()
    if not row:
        raise HTTPException(404, f"Gen '{symbol}' no encontrado en el panel neuropediátrico")
    return _row_to_gene(row, settings)


# ─────────────────────────────────────────────────────────────
#  Routes — Groups
# ─────────────────────────────────────────────────────────────

@app.get("/api/groups", response_model=list[GroupInfo], tags=["Groups"])
def list_groups():
    """Lista todos los grupos de enfermedad con número de genes."""
    db = get_db()
    rows = db.execute("""
        SELECT g.id, g.label, g.description, g.color,
               COUNT(gg.gene_symbol) as gene_count
        FROM groups g
        LEFT JOIN gene_groups gg ON g.id = gg.group_id
        GROUP BY g.id, g.label, g.description, g.color
        ORDER BY gene_count DESC
    """).fetchall()
    return [GroupInfo(**dict(r)) for r in rows]


@app.get("/api/groups/{group_id}", tags=["Groups"])
def get_group(group_id: str):
    """Información del grupo + lista de genes."""
    settings = get_settings()
    db = get_db()
    grp = db.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()
    if not grp:
        raise HTTPException(404, f"Grupo '{group_id}' no encontrado")
    genes = db.execute(
        "SELECT g.* FROM genes g JOIN gene_groups gg ON g.symbol=gg.gene_symbol WHERE gg.group_id=?",
        (group_id,)
    ).fetchall()
    return {
        "id": grp["id"],
        "label": grp["label"],
        "description": grp["description"],
        "color": grp["color"],
        "gene_count": len(genes),
        "genes": [_row_to_gene(r, settings) for r in genes],
    }


# ─────────────────────────────────────────────────────────────
#  Routes — Variant Classification
# ─────────────────────────────────────────────────────────────

@app.post("/api/variant/classify", response_model=VariantReport, tags=["Variant"])
def classify_variant(query: VariantQuery):
    """
    Clasifica una variante en su grupo neuropediátrico y devuelve:
    - Notas de interpretación específicas del gen
    - Guía de criterios ACMG aplicables
    - Flags de mecanismo (GoF/LoF, mosaicismo, herencia)
    - URLs directas a REEV y protein-viewer
    - Coincidencia con hotspots conocidos

    NOTA: Este endpoint es una capa de RECOMENDACIÓN — no sustituye
    la clasificación final ACMG generada por REEV/auto-ACMG.
    """
    settings = get_settings()
    db = get_db()

    row = db.execute("SELECT * FROM genes WHERE upper(symbol)=upper(?)", (query.gene,)).fetchone()
    if not row:
        raise HTTPException(
            404,
            f"Gen '{query.gene}' no está en el panel neuropediátrico. "
            "Consulta /api/genes para ver los genes disponibles."
        )

    gene = _row_to_gene(row, settings)
    mechanisms = gene.mechanism
    inheritance = gene.inheritance

    # ── Mechanism flags ──────────────────────────────────────
    flags = []
    if "gain_of_function" in mechanisms and "loss_of_function" in mechanisms:
        flags.append(
            "⚠️ MECANISMO DUAL: Este gen puede causar GoF Y LoF — "
            "el mecanismo determina el fenotipo y el tratamiento. "
            "Evaluar onset age, estudios funcionales (PS3) y contexto clínico."
        )
    elif "gain_of_function" in mechanisms:
        flags.append("↑ Mecanismo predominante: Ganancia de función (GoF)")
    elif "loss_of_function" in mechanisms or "haploinsufficiency" in mechanisms:
        flags.append("↓ Mecanismo predominante: Pérdida de función (LoF) / Haploinsuficiencia")

    if "mtoropathy" in gene.mechanism_groups:
        flags.append(
            "🔬 mTORopatía: Considerar MOSAICISMO somático. "
            "Si WES en sangre es negativo, evaluar secuenciación profunda (>500x) "
            "o análisis de tejido cerebral."
        )
    if "XLD" in inheritance or "XLR" in inheritance:
        flags.append(
            "🧬 Gen X-linked: El fenotipo difiere entre sexos. "
            "Evaluar lionización/inactivación X en portadoras."
        )
    if "de_novo" in inheritance:
        flags.append("✓ De novo esperado — confirmar parentesco (PS2/PM6)")

    # ── Hotspot match ────────────────────────────────────────
    hotspot_match = None
    if query.hgvs_p:
        for hs in gene.hotspots:
            if hs.get("hgvs_p", "").lower() == query.hgvs_p.lower():
                hotspot_match = hs
                flags.append(
                    f"🎯 HOTSPOT conocido: {hs['hgvs_p']} — "
                    f"{hs.get('significance', '')} para {hs.get('phenotype', '')}"
                )
                break

    # ── ACMG criteria hints ───────────────────────────────────
    acmg_hints = list(gene.acmg_guidance)
    if gene.clingen.get("gene_validity") == "Definitive":
        acmg_hints.insert(0, {
            "criterion": "PS4/PP4",
            "note": f"ClinGen Gene-Disease Definitive — aplicar criterios PP4 si fenotipo específico"
        })
    if "haploinsufficiency" in mechanisms:
        acmg_hints.insert(0, {
            "criterion": "PVS1",
            "note": "Haploinsuficiencia establecida — variantes truncantes P/LP salvo evidencia contraria"
        })

    # ── URLs ─────────────────────────────────────────────────
    reev_url = None
    if query.chrom and query.pos and query.ref and query.alt:
        reev_url = (
            f"{settings.reev_external_url}"
            f"/seqvar/grch38-{query.chrom}-{query.pos}-{query.ref}-{query.alt}"
        )

    protein_viewer_url = gene.links.get("protein_viewer")
    if query.hgvs_p and gene.uniprot:
        protein_viewer_url = (
            f"{settings.protein_viewer_url}/"
            f"?uniprot={gene.uniprot}&variant={query.hgvs_p}"
        )

    # ── In Silico queries (SpliceAI, AlphaMissense, AMELIE) ──
    in_silico_results = {}
    if query.chrom and query.pos and query.ref and query.alt:
        payload = {
            "chrom": query.chrom,
            "pos": query.pos,
            "ref": query.ref,
            "alt": query.alt,
            "assembly": query.genome_build
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                # 1. AlphaMissense
                am_resp = client.post(f"{settings.in_silico_api_url}/api/alphamissense", json=payload)
                if am_resp.status_code == 200:
                    in_silico_results["alphamissense"] = am_resp.json()
                
                # 2. SpliceAI
                sa_resp = client.post(f"{settings.in_silico_api_url}/api/spliceai", json=payload)
                if sa_resp.status_code == 200:
                    in_silico_results["spliceai"] = sa_resp.json()
        except Exception as e:
            logger.warning(f"Error querying in-silico-api databases: {str(e)}")

    if query.hpo_terms and len(query.hpo_terms) > 0:
        try:
            with httpx.Client(timeout=10.0) as client:
                amelie_resp = client.post(
                    f"{settings.in_silico_api_url}/api/amelie",
                    json={"gene": query.gene, "hpo_terms": query.hpo_terms}
                )
                if amelie_resp.status_code == 200:
                    in_silico_results["amelie"] = amelie_resp.json()
        except Exception as e:
            logger.warning(f"Error querying AMELIE via in-silico-api: {str(e)}")

    return VariantReport(
        gene=gene,
        variant=query.model_dump(exclude_none=True),
        mechanism_flags=flags,
        interpretation_guidance=gene.interpretation_notes,
        acmg_criteria_hints=acmg_hints,
        hotspot_match=hotspot_match,
        reev_url=reev_url,
        protein_viewer_url=protein_viewer_url,
        in_silico=in_silico_results if in_silico_results else None,
        disclaimer=(
            "⚠️ AVISO LEGAL: Este informe es una capa de RECOMENDACIÓN INFORMATIVA "
            "basada en el panel curado NeuropedGx. NO sustituye la clasificación ACMG "
            "generada por REEV/auto-ACMG ni el criterio clínico del genetista responsable. "
            "Toda clasificación final debe ser revisada por un profesional cualificado."
        ),
    )


# ─────────────────────────────────────────────────────────────
#  Routes — Panel metadata
# ─────────────────────────────────────────────────────────────

@app.get("/api/stats", tags=["Panel"])
def get_stats():
    """Estadísticas del panel."""
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM genes").fetchone()[0]
    by_group = db.execute("""
        SELECT g.label, COUNT(gg.gene_symbol) as n
        FROM groups g LEFT JOIN gene_groups gg ON g.id=gg.group_id
        GROUP BY g.id ORDER BY n DESC
    """).fetchall()
    return {
        "total_genes": total,
        "panel_version": "2026.06",
        "by_group": [{"group": r[0], "genes": r[1]} for r in by_group],
    }


@app.get("/api/panel/version", tags=["Panel"])
def get_panel_version():
    return {"version": "2026.06", "source": "ClinGen/GenCC/OMIM/PMID curation — Neuropediatrics Lab"}



# ─────────────────────────────────────────────────────────────
#  Static frontend
# ─────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent.parent
_PUBLIC = Path(os.environ.get("PUBLIC_DIR", str(_HERE / "public")))
_STATIC = _PUBLIC / "static"
_DIAGRAMS = _PUBLIC / "diagrams"

if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

if _DIAGRAMS.exists():
    app.mount("/diagrams", StaticFiles(directory=str(_DIAGRAMS)), name="diagrams")

@app.get("/", include_in_schema=False)
def root():
    index = _PUBLIC / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"service": "NeuropedGx Hub", "docs": "/docs", "api": "/api/stats"}

@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    index = _PUBLIC / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(404)
