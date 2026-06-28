#!/bin/bash
# Script de ayuda para descargar e indexar los archivos precalculados de AlphaMissense y SpliceAI.
# Se deben guardar en el directorio que se monta en el contenedor (e.g. /mnt/pi-nas/raid-hdd/swarm-storage/reev-data/reev-static/data/download/in-silico/)

set -e

DATA_DIR=${1:-"/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/reev-static/data/download/in-silico"}
mkdir -p "$DATA_DIR"

echo "📥 Descargando bases de datos de predicción funcional in silico en: $DATA_DIR"
echo "=========================================================================="

# --- 1. AlphaMissense (Google DeepMind) ---
echo "🧬 Descargando AlphaMissense (GRCh38)..."
if [ ! -f "$DATA_DIR/AlphaMissense_hg38.tsv.gz" ]; then
    wget -c https://storage.googleapis.com/dm_alphamissense/AlphaMissense_hg38.tsv.gz -O "$DATA_DIR/AlphaMissense_hg38.tsv.gz"
    echo "Indexando AlphaMissense (GRCh38) con tabix..."
    tabix -s 1 -b 2 -e 2 -f "$DATA_DIR/AlphaMissense_hg38.tsv.gz"
else
    echo "✅ AlphaMissense (GRCh38) ya existe."
fi

echo "🧬 Descargando AlphaMissense (GRCh37)..."
if [ ! -f "$DATA_DIR/AlphaMissense_hg37.tsv.gz" ]; then
    wget -c https://storage.googleapis.com/dm_alphamissense/AlphaMissense_hg37.tsv.gz -O "$DATA_DIR/AlphaMissense_hg37.tsv.gz"
    echo "Indexando AlphaMissense (GRCh37) con tabix..."
    tabix -s 1 -b 2 -e 2 -f "$DATA_DIR/AlphaMissense_hg37.tsv.gz"
else
    echo "✅ AlphaMissense (GRCh37) ya existe."
fi

# --- 2. SpliceAI (Illumina) ---
# Los archivos de SpliceAI son grandes y requieren autenticación en Illumina para los archivos completos,
# pero existen mirrors y conjuntos de datos precalculados públicos de libre descarga para uso de investigación académica.
echo "🧬 Descargando precalculados de SpliceAI (GRCh38)..."
if [ ! -f "$DATA_DIR/spliceai_scores.raw.snv.hg38.vcf.gz" ]; then
    # Mirror de uso libre
    wget -c https://hugheylab.s3.us-east-2.amazonaws.com/spliceai_scores.raw.snv.hg38.vcf.gz -O "$DATA_DIR/spliceai_scores.raw.snv.hg38.vcf.gz"
    echo "Indexando SpliceAI (GRCh38)..."
    tabix -p vcf -f "$DATA_DIR/spliceai_scores.raw.snv.hg38.vcf.gz"
else
    echo "✅ SpliceAI (GRCh38) ya existe."
fi

echo "🧬 Descargando precalculados de SpliceAI (GRCh37)..."
if [ ! -f "$DATA_DIR/spliceai_scores.raw.snv.hg37.vcf.gz" ]; then
    wget -c https://hugheylab.s3.us-east-2.amazonaws.com/spliceai_scores.raw.snv.hg37.vcf.gz -O "$DATA_DIR/spliceai_scores.raw.snv.hg37.vcf.gz"
    echo "Indexando SpliceAI (GRCh37)..."
    tabix -p vcf -f "$DATA_DIR/spliceai_scores.raw.snv.hg37.vcf.gz"
else
    echo "✅ SpliceAI (GRCh37) ya existe."
fi

echo "🎉 Descargas completadas. Los archivos están listos para ser montados en el contenedor in-silico-api."
