#!/bin/bash
# Download and import gnomAD v4.1 chrX/Y for GRCh38
set -euo pipefail

DATA=/media/arkantu/Storage1TB/reev/volumes/reev-static/data
DL_DIR="$DATA/download/annonars"
VCF_DIR="$DATA/download/gnomad-vcf-grch38"
mkdir -p "$VCF_DIR"

echo "=== gnomAD v4.1 GRCh38 chrX/Y import ==="
echo "Started: $(date)"

# ── [1/5] Download exomes chrX VCF (5.4 GB) ──────────────────────────────────
echo ""
echo "=== [1/5] Downloading gnomAD exomes chrX GRCh38 (5.4 GB) ==="
if [ -f "$VCF_DIR/gnomad.exomes.v4.1.sites.chrX.vcf.bgz" ]; then
  echo "  ✓ Already downloaded"
else
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/exomes/gnomad.exomes.v4.1.sites.chrX.vcf.bgz" \
    -o "$VCF_DIR/gnomad.exomes.v4.1.sites.chrX.vcf.bgz"
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/exomes/gnomad.exomes.v4.1.sites.chrX.vcf.bgz.tbi" \
    -o "$VCF_DIR/gnomad.exomes.v4.1.sites.chrX.vcf.bgz.tbi"
  echo "  ✅ Downloaded"
fi

# ── [2/5] Import exomes chrX → RocksDB ───────────────────────────────────────
echo ""
echo "=== [2/5] Building gnomAD exomes chrX GRCh38 RocksDB ==="
EXOMES_CHRX_HOST="$DL_DIR/gnomad-exomes-chrX-grch38-4.1+0.39.0"
EXOMES_CHRX_CONT="/data/download/annonars/gnomad-exomes-chrX-grch38-4.1+0.39.0"
mkdir -p "$EXOMES_CHRX_HOST"
if [ -f "$EXOMES_CHRX_HOST/rocksdb/CURRENT" ]; then
  echo "  ✓ RocksDB already exists"
else
  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.exomes.v4.1.sites.chrX.vcf.bgz" \
      --path-out-rocksdb "$EXOMES_CHRX_CONT/rocksdb" \
      --gnomad-kind exomes \
      --gnomad-version "4.1" \
      --genome-release grch38
  echo "  ✅ RocksDB built"
fi

# ── [3/5] Download genomes chrX VCF (21.3 GB) ────────────────────────────────
echo ""
echo "=== [3/5] Downloading gnomAD genomes chrX GRCh38 (21.3 GB) ==="
if [ -f "$VCF_DIR/gnomad.genomes.v4.1.sites.chrX.vcf.bgz" ]; then
  echo "  ✓ Already downloaded"
else
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/gnomad.genomes.v4.1.sites.chrX.vcf.bgz" \
    -o "$VCF_DIR/gnomad.genomes.v4.1.sites.chrX.vcf.bgz"
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/gnomad.genomes.v4.1.sites.chrX.vcf.bgz.tbi" \
    -o "$VCF_DIR/gnomad.genomes.v4.1.sites.chrX.vcf.bgz.tbi"
  echo "  ✅ Downloaded"
fi

# ── [4/5] Import genomes chrX → RocksDB ──────────────────────────────────────
echo ""
echo "=== [4/5] Building gnomAD genomes chrX GRCh38 RocksDB ==="
GENOMES_CHRX_HOST="$DL_DIR/gnomad-genomes-chrX-grch38-4.1+0.39.0"
GENOMES_CHRX_CONT="/data/download/annonars/gnomad-genomes-chrX-grch38-4.1+0.39.0"
mkdir -p "$GENOMES_CHRX_HOST"
if [ -f "$GENOMES_CHRX_HOST/rocksdb/CURRENT" ]; then
  echo "  ✓ RocksDB already exists"
else
  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.genomes.v4.1.sites.chrX.vcf.bgz" \
      --path-out-rocksdb "$GENOMES_CHRX_CONT/rocksdb" \
      --gnomad-kind genomes \
      --gnomad-version "4.1" \
      --genome-release grch38
  echo "  ✅ RocksDB built"
fi

# ── [5/5] Download + import genomes chrY VCF (0.6 GB) ────────────────────────
echo ""
echo "=== [5/5] Downloading + building gnomAD genomes chrY GRCh38 (0.6 GB) ==="
if [ ! -f "$VCF_DIR/gnomad.genomes.v4.1.sites.chrY.vcf.bgz" ]; then
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/gnomad.genomes.v4.1.sites.chrY.vcf.bgz" \
    -o "$VCF_DIR/gnomad.genomes.v4.1.sites.chrY.vcf.bgz"
  curl -L --progress-bar \
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/genomes/gnomad.genomes.v4.1.sites.chrY.vcf.bgz.tbi" \
    -o "$VCF_DIR/gnomad.genomes.v4.1.sites.chrY.vcf.bgz.tbi"
fi
GENOMES_CHRY_HOST="$DL_DIR/gnomad-genomes-chrY-grch38-4.1+0.39.0"
GENOMES_CHRY_CONT="/data/download/annonars/gnomad-genomes-chrY-grch38-4.1+0.39.0"
mkdir -p "$GENOMES_CHRY_HOST"
if [ -f "$GENOMES_CHRY_HOST/rocksdb/CURRENT" ]; then
  echo "  ✓ RocksDB already exists"
else
  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.genomes.v4.1.sites.chrY.vcf.bgz" \
      --path-out-rocksdb "$GENOMES_CHRY_CONT/rocksdb" \
      --gnomad-kind genomes \
      --gnomad-version "4.1" \
      --genome-release grch38
  echo "  ✅ RocksDB built"
fi

# ── Crear symlinks ────────────────────────────────────────────────────────────
echo ""
echo "=== Creating symlinks in annonars/grch38/ ==="
ANNONARS38="$DATA/annonars/grch38"

[ -L "$ANNONARS38/gnomad-exomes-chrX" ] || \
  ln -s ../../download/annonars/gnomad-exomes-chrX-grch38-4.1+0.39.0 "$ANNONARS38/gnomad-exomes-chrX"

[ -L "$ANNONARS38/gnomad-genomes-chrX" ] || \
  ln -s ../../download/annonars/gnomad-genomes-chrX-grch38-4.1+0.39.0 "$ANNONARS38/gnomad-genomes-chrX"

[ -L "$ANNONARS38/gnomad-genomes-chrY" ] || \
  ln -s ../../download/annonars/gnomad-genomes-chrY-grch38-4.1+0.39.0 "$ANNONARS38/gnomad-genomes-chrY"

echo "  ✅ Symlinks done"
echo ""
echo "=== All done $(date) ==="
