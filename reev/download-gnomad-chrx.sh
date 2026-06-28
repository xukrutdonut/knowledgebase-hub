#!/usr/bin/env bash
set -euo pipefail

DATA="/media/arkantu/Storage1TB/reev/volumes/reev-static/data"
VCF_DIR="$DATA/download/gnomad-vcf-grch37"
DL_DIR="$DATA/download/annonars"
GRCH37="$DATA/annonars/grch37"
LOG="/home/arkantu/workspace/reev/download-gnomad-chrx.log"
GCS_BASE="https://storage.googleapis.com/gcp-public-data--gnomad/release/2.1.1/vcf"

exec > >(tee -a "$LOG") 2>&1
echo "=== Start $(date) ==="

mkdir -p "$VCF_DIR"

download_file() {
  local url="$1" dest="$2"
  if [ -f "$dest" ]; then
    echo "  ✓ Already exists: $(basename $dest)"
    return
  fi
  echo "  ↓ Downloading $(basename $dest)..."
  curl -L --progress-bar -C - -o "$dest" "$url"
  echo "  ✅ Done: $(basename $dest) ($(du -sh $dest | cut -f1))"
}

# --- Download chrX VCFs ---
echo "=== [1/4] Downloading gnomAD v2.1.1 chrX exomes VCF ==="
download_file \
  "$GCS_BASE/exomes/gnomad.exomes.r2.1.1.sites.X.vcf.bgz" \
  "$VCF_DIR/gnomad.exomes.r2.1.1.sites.X.vcf.bgz"
download_file \
  "$GCS_BASE/exomes/gnomad.exomes.r2.1.1.sites.X.vcf.bgz.tbi" \
  "$VCF_DIR/gnomad.exomes.r2.1.1.sites.X.vcf.bgz.tbi"

echo "=== [2/4] Building gnomAD exomes chrX RocksDB ==="
EXOMES_CHRX="$DL_DIR/gnomad-exomes-chrX-grch37-2.1.1"
EXOMES_CHRX_CONT="/data/download/annonars/gnomad-exomes-chrX-grch37-2.1.1"
mkdir -p "$EXOMES_CHRX"
if [ -f "$EXOMES_CHRX/rocksdb/CURRENT" ]; then
  echo "  ✓ gnomad-exomes chrX RocksDB already exists"
else
  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.exomes.r2.1.1.sites.X.vcf.bgz" \
      --path-out-rocksdb "$EXOMES_CHRX_CONT/rocksdb" \
      --gnomad-kind exomes \
      --gnomad-version "2.1.1" \
      --genome-release grch37
  echo "  ✅ gnomad-exomes chrX RocksDB built"
fi

echo "=== [3/4] Downloading gnomAD v2.1.1 chrX genomes VCF (19GB) ==="
download_file \
  "$GCS_BASE/genomes/gnomad.genomes.r2.1.1.sites.X.vcf.bgz" \
  "$VCF_DIR/gnomad.genomes.r2.1.1.sites.X.vcf.bgz"
download_file \
  "$GCS_BASE/genomes/gnomad.genomes.r2.1.1.sites.X.vcf.bgz.tbi" \
  "$VCF_DIR/gnomad.genomes.r2.1.1.sites.X.vcf.bgz.tbi"

echo "=== [4/4] Building gnomAD genomes chrX RocksDB ==="
GENOMES_CHRX="$DL_DIR/gnomad-genomes-chrX-grch37-2.1.1"
GENOMES_CHRX_CONT="/data/download/annonars/gnomad-genomes-chrX-grch37-2.1.1"
mkdir -p "$GENOMES_CHRX"
if [ -f "$GENOMES_CHRX/rocksdb/CURRENT" ]; then
  echo "  ✓ gnomad-genomes chrX RocksDB already exists"
else
  docker run --rm \
    -v "$DATA:/data" \
    -v "$VCF_DIR:/vcf" \
    --entrypoint annonars \
    ghcr.io/varfish-org/annonars:0.39.0 \
    gnomad-nuclear import \
      --path-in-vcf "/vcf/gnomad.genomes.r2.1.1.sites.X.vcf.bgz" \
      --path-out-rocksdb "$GENOMES_CHRX_CONT/rocksdb" \
      --gnomad-kind genomes \
      --gnomad-version "2.1.1" \
      --genome-release grch37
  echo "  ✅ gnomad-genomes chrX RocksDB built"
fi

echo "=== All done $(date) ==="
