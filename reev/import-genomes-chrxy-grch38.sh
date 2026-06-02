#!/bin/bash
# Continues the gnomAD GRCh38 genomes chrX/Y import after VCF filtering
set -euo pipefail

DATA=/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/reev-static/data
DL_DIR="$DATA/download/annonars"
VCF_DIR="$DATA/download/gnomad-vcf-grch38"
LOG=/home/arkantu/workspace/reev/import-genomes-chrxy-grch38.log

exec > >(tee -a "$LOG") 2>&1
echo ""
echo "=== Import gnomAD genomes chrX/Y GRCh38 === $(date)"

# ── Esperar a que termine el filtrado del VCF ─────────────────────────────────
FILTER_PID=2180741
if kill -0 "$FILTER_PID" 2>/dev/null; then
  echo "[1/4] Esperando a que termine el filtrado del VCF chrX (PID $FILTER_PID)..."
  while kill -0 "$FILTER_PID" 2>/dev/null; do
    FSIZE=$(stat -c%s "$VCF_DIR/gnomad.genomes.v4.1.sites.chrX.vep.vcf.bgz" 2>/dev/null || echo 0)
    echo "      ... $(( FSIZE / 1024 / 1024 )) MB escritos — $(date +%H:%M:%S)"
    sleep 60
  done
  echo "  ✅ Filtrado completado"
else
  echo "[1/4] Filtrado ya completado (PID $FILTER_PID no existe)"
fi

# Verificar que el archivo filtrado existe
FILT_VCF="$VCF_DIR/gnomad.genomes.v4.1.sites.chrX.vep.vcf.bgz"
if [ ! -f "$FILT_VCF" ]; then
  echo "ERROR: No existe $FILT_VCF"
  exit 1
fi
echo "  Tamaño VCF filtrado: $(du -sh "$FILT_VCF" | cut -f1)"

# ── [2/4] Indexar el VCF filtrado ────────────────────────────────────────────
echo ""
echo "[2/4] Indexando VCF filtrado con tabix..."
if [ -f "${FILT_VCF}.tbi" ]; then
  echo "  ✓ Ya indexado"
else
  docker run --rm \
    -v "$VCF_DIR:/vcf" \
    biocontainers/bcftools:v1.9-1-deb_cv1 \
    bcftools index -t /vcf/gnomad.genomes.v4.1.sites.chrX.vep.vcf.bgz
  echo "  ✅ Indexado"
fi

# ── [3/4] Importar genomes chrX filtrado → RocksDB ───────────────────────────
echo ""
echo "[3/4] Importando gnomAD genomes chrX GRCh38 (VCF filtrado) → RocksDB..."
GENOMES_CHRX_HOST="$DL_DIR/gnomad-genomes-chrX-grch38-4.1+0.39.0"
GENOMES_CHRX_CONT="/data/download/annonars/gnomad-genomes-chrX-grch38-4.1+0.39.0"
mkdir -p "$GENOMES_CHRX_HOST"
if [ -f "$GENOMES_CHRX_HOST/rocksdb/CURRENT" ]; then
  echo "  ✓ RocksDB ya existe"
else
  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.genomes.v4.1.sites.chrX.vep.vcf.bgz" \
      --path-out-rocksdb "$GENOMES_CHRX_CONT/rocksdb" \
      --gnomad-kind genomes \
      --gnomad-version "4.1" \
      --genome-release grch38
  echo "  ✅ RocksDB genomes chrX construido"
fi

# ── [4/4] Descargar + importar genomes chrY (0.6 GB) ─────────────────────────
echo ""
echo "[4/4] gnomAD genomes chrY GRCh38..."
CHRY_VCF="$VCF_DIR/gnomad.genomes.v4.1.sites.chrY.vcf.bgz"
if [ ! -f "$CHRY_VCF" ]; then
  echo "  Descargando chrY VCF (0.6 GB)..."
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/gnomad.genomes.v4.1.sites.chrY.vcf.bgz" \
    -o "$CHRY_VCF"
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/gnomad.genomes.v4.1.sites.chrY.vcf.bgz.tbi" \
    -o "${CHRY_VCF}.tbi"
  echo "  ✅ Descargado"
else
  echo "  ✓ Ya descargado"
fi

GENOMES_CHRY_HOST="$DL_DIR/gnomad-genomes-chrY-grch38-4.1+0.39.0"
GENOMES_CHRY_CONT="/data/download/annonars/gnomad-genomes-chrY-grch38-4.1+0.39.0"
mkdir -p "$GENOMES_CHRY_HOST"
if [ -f "$GENOMES_CHRY_HOST/rocksdb/CURRENT" ]; then
  echo "  ✓ RocksDB chrY ya existe"
else
  # chrY también puede tener registros sin VEP (PAR2), filtramos igual
  echo "  Filtrando + importando chrY..."
  docker run --rm \
    -v "$VCF_DIR:/vcf" \
    biocontainers/bcftools:v1.9-1-deb_cv1 \
    bcftools view -i 'INFO/vep!="."' \
    /vcf/gnomad.genomes.v4.1.sites.chrY.vcf.bgz \
    -O z -o /vcf/gnomad.genomes.v4.1.sites.chrY.vep.vcf.bgz

  docker run --rm \
    -v "$VCF_DIR:/vcf" \
    biocontainers/bcftools:v1.9-1-deb_cv1 \
    bcftools index -t /vcf/gnomad.genomes.v4.1.sites.chrY.vep.vcf.bgz

  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.genomes.v4.1.sites.chrY.vep.vcf.bgz" \
      --path-out-rocksdb "$GENOMES_CHRY_CONT/rocksdb" \
      --gnomad-kind genomes \
      --gnomad-version "4.1" \
      --genome-release grch38
  echo "  ✅ RocksDB genomes chrY construido"
fi

# ── Crear symlinks ────────────────────────────────────────────────────────────
echo ""
echo "Creando symlinks en annonars/grch38/..."
ANNONARS38="$DATA/annonars/grch38"

[ -L "$ANNONARS38/gnomad-genomes-chrX" ] || \
  ln -s ../../download/annonars/gnomad-genomes-chrX-grch38-4.1+0.39.0 "$ANNONARS38/gnomad-genomes-chrX"

[ -L "$ANNONARS38/gnomad-genomes-chrY" ] || \
  ln -s ../../download/annonars/gnomad-genomes-chrY-grch38-4.1+0.39.0 "$ANNONARS38/gnomad-genomes-chrY"

echo "  ✅ Symlinks OK"

# ── Reiniciar annonars ────────────────────────────────────────────────────────
echo ""
echo "Reiniciando annonars para cargar nuevas DBs..."
cd /home/arkantu/workspace/reev
docker compose restart annonars
echo "  ✅ annonars reiniciado"

echo ""
echo "=== TODO COMPLETADO === $(date)"
