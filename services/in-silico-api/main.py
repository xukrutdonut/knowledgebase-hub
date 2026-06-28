import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
import pysam

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("in-silico-api")

app = FastAPI(
    title="In Silico Functional Predictor API",
    description="Microservicio para la consulta local de SpliceAI, AlphaMissense (vía archivos Tabix) e integración con AMELIE API.",
    version="1.0.0"
)

# Paths to databases mounted from NAS/local storage
DATA_DIR = os.environ.get("IN_SILICO_DATA_DIR", "/data/download/in-silico")
ALPHAMISSENSE_HG38 = os.path.join(DATA_DIR, "AlphaMissense_hg38.tsv.gz")
ALPHAMISSENSE_HG37 = os.path.join(DATA_DIR, "AlphaMissense_hg37.tsv.gz")
SPLICEAI_HG38 = os.path.join(DATA_DIR, "spliceai_scores.raw.snv.hg38.vcf.gz")
SPLICEAI_HG37 = os.path.join(DATA_DIR, "spliceai_scores.raw.snv.hg37.vcf.gz")

# Model definitions
class VariantQuery(BaseModel):
    chrom: str
    pos: int
    ref: str
    alt: str
    assembly: str = "GRCh38"  # "GRCh37" or "GRCh38"

class AmelieQuery(BaseModel):
    gene: str
    hpo_terms: List[str]
    patient_id: Optional[str] = "patient_1"

# Helper for Tabix queries
def query_tabix(filename: str, chrom: str, pos: int, ref: str, alt: str) -> Optional[List[str]]:
    if not os.path.exists(filename):
        logger.warning(f"Database file not found: {filename}")
        return None
    
    # Standardize chromosome representation
    chrom_clean = chrom.lower().replace("chr", "")
    variants_found = []
    
    try:
        # Check both chrX and X formats
        tabix_file = pysam.TabixFile(filename)
        chromosomes_in_file = tabix_file.contigs
        
        target_chrom = None
        for c in [chrom_clean, f"chr{chrom_clean}", chrom.upper()]:
            if c in chromosomes_in_file:
                target_chrom = c
                break
                
        if not target_chrom:
            logger.warning(f"Chromosome {chrom} not found in {filename}")
            return []
            
        # Query 1-based single coordinate
        # Tabix fetch takes 0-based start, 1-based end or standard coordinates
        for row in tabix_file.fetch(target_chrom, pos - 1, pos):
            variants_found.append(row)
            
        return variants_found
    except Exception as e:
        logger.error(f"Error querying tabix file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying local database: {str(e)}")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "databases": {
            "alphamissense_hg38": os.path.exists(ALPHAMISSENSE_HG38),
            "alphamissense_hg37": os.path.exists(ALPHAMISSENSE_HG37),
            "spliceai_hg38": os.path.exists(SPLICEAI_HG38),
            "spliceai_hg37": os.path.exists(SPLICEAI_HG37)
        }
    }

@app.post("/api/alphamissense")
def get_alphamissense(query: VariantQuery):
    db_file = ALPHAMISSENSE_HG38 if query.assembly.lower() == "grch38" else ALPHAMISSENSE_HG37
    
    if not os.path.exists(db_file):
        raise HTTPException(
            status_code=503,
            detail=f"Base de datos de AlphaMissense para {query.assembly} no está descargada en el host. Ruta esperada: {db_file}"
        )
        
    rows = query_tabix(db_file, query.chrom, query.pos, query.ref, query.alt)
    if not rows:
        return {"found": False, "message": "No annotations found for this coordinate"}
        
    # AlphaMissense columns: #CHROM, POS, REF, ALT, genome, uniprot_id, transcript_id, protein_variant, am_pathogenicity, am_class
    # Note: structure could vary slightly. We parse the columns matching the ref/alt alleles.
    for row in rows:
        fields = row.split("\t")
        if len(fields) >= 9:
            # check ref and alt match
            row_ref, row_alt = fields[2], fields[3]
            if row_ref == query.ref and row_alt == query.alt:
                return {
                    "found": True,
                    "chrom": fields[0],
                    "pos": int(fields[1]),
                    "ref": fields[2],
                    "alt": fields[3],
                    "uniprot_id": fields[5],
                    "protein_variant": fields[7],
                    "pathogenicity_score": float(fields[8]),
                    "classification": fields[9].strip()
                }
                
    return {"found": False, "message": "Coordinate found but allele mismatch"}

@app.post("/api/spliceai")
def get_spliceai(query: VariantQuery):
    db_file = SPLICEAI_HG38 if query.assembly.lower() == "grch38" else SPLICEAI_HG37
    
    if not os.path.exists(db_file):
        raise HTTPException(
            status_code=503,
            detail=f"Base de datos de SpliceAI para {query.assembly} no está descargada en el host. Ruta esperada: {db_file}"
        )
        
    rows = query_tabix(db_file, query.chrom, query.pos, query.ref, query.alt)
    if not rows:
        return {"found": False, "message": "No SpliceAI predictions found for this coordinate"}
        
    # SpliceAI raw VCF format:
    # INFO column contains SpliceAI=ALLELE|SYMBOL|DS_AG|DS_AL|DS_DG|DS_DL|DP_AG|DP_AL|DP_DG|DP_DL
    for row in rows:
        fields = row.split("\t")
        # VCF format: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO
        if len(fields) >= 8:
            row_ref, row_alt = fields[3], fields[4]
            if row_ref == query.ref and row_alt == query.alt:
                info = fields[7]
                if "SpliceAI=" in info:
                    # Extract SpliceAI values
                    # Example: SpliceAI=T|SCN1A|0.00|0.01|0.98|0.00|3|-22|15|-12
                    splice_data = info.split("SpliceAI=")[1].split(";")[0]
                    parts = splice_data.split("|")
                    if len(parts) >= 10:
                        scores = {
                            "symbol": parts[1],
                            "ds_ag": float(parts[2]), # Acceptor Gain
                            "ds_al": float(parts[3]), # Acceptor Loss
                            "ds_dg": float(parts[4]), # Donor Gain
                            "ds_dl": float(parts[5]), # Donor Loss
                            "dp_ag": int(parts[6]),   # Position Delta Acceptor Gain
                            "dp_al": int(parts[7]),
                            "dp_dg": int(parts[8]),
                            "dp_dl": int(parts[9]),
                        }
                        
                        # Max delta score (interpretable value)
                        max_ds = max(scores["ds_ag"], scores["ds_al"], scores["ds_dg"], scores["ds_dl"])
                        
                        return {
                            "found": True,
                            "chrom": fields[0],
                            "pos": int(fields[1]),
                            "ref": fields[3],
                            "alt": fields[4],
                            "gene": scores["symbol"],
                            "max_delta_score": max_ds,
                            "scores": scores,
                            "interpretation": (
                                "Alta probabilidad de alteración del splicing (Patogénico)" if max_ds >= 0.8 else
                                "Moderada probabilidad de alteración del splicing" if max_ds >= 0.5 else
                                "Baja probabilidad / impacto no detectado" if max_ds >= 0.2 else
                                "Normal / Sin impacto en splicing"
                            )
                        }
                        
    return {"found": False, "message": "Coordinate found but allele mismatch"}

@app.post("/api/amelie")
async def solve_amelie(query: AmelieQuery):
    """
    Realiza una consulta a la API pública de AMELIE (Stanford University)
    para priorizar la relación del gen analizado con los fenotipos HPO del paciente.
    """
    url = "https://amelie.stanford.edu/api/solve"
    
    # Formatear el payload esperado por AMELIE API
    # AMELIE espera un JSON con la lista de variantes y una lista de fenotipos (HPO ids)
    payload = {
        "patientId": query.patient_id,
        "hpoIds": query.hpo_terms,
        "genes": [query.gene]
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"AMELIE API error: {response.status_code} - {response.text}")
                raise HTTPException(status_code=502, detail=f"AMELIE API returned error code {response.status_code}")
                
            data = response.json()
            return {
                "success": True,
                "gene": query.gene,
                "hpo_terms": query.hpo_terms,
                "amelie_score": data.get("geneScores", {}).get(query.gene, 0.0),
                "matching_publications": data.get("matchingPublications", {}).get(query.gene, [])[:5]  # Top 5 articles
            }
    except httpx.RequestError as e:
        logger.error(f"HTTP error connecting to AMELIE API: {str(e)}")
        raise HTTPException(status_code=503, detail=f"No se pudo conectar con AMELIE API: {str(e)}")
