#!/usr/bin/env bash
set -euo pipefail

S3_BASE="https://ceph-s3-public.cubi.bihealth.org/varfish-public/full"
TARGET_BASE="/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/reev-static/data/download/annonars"
ANNONARS_DIR="/mnt/pi-nas/raid-hdd/swarm-storage/reev-data/reev-static/data/annonars/grch37"

download_db() {
    local db_name="$1"
    local db_path="${TARGET_BASE}/${db_name}"
    local s3_path="${S3_BASE}/annonars/${db_name}"
    
    echo "=== Downloading ${db_name} ==="
    
    # Get file list from S3
    encoded_prefix=$(python3 -c "import urllib.parse; print(urllib.parse.quote('full/annonars/${db_name}/'))")
    files=$(curl -s --max-time 30 "https://ceph-s3-public.cubi.bihealth.org/varfish-public?prefix=${encoded_prefix}&max-keys=200" | \
        python3 -c "
import sys, xml.etree.ElementTree as ET
data = sys.stdin.read()
root = ET.fromstring(data)
ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
prefix = 'full/annonars/${db_name}/'
for k in root.findall('s3:Contents', ns):
    key = k.find('s3:Key', ns).text
    size = int(k.find('s3:Size', ns).text)
    relpath = key[len(prefix):]
    print(relpath)
")

    # Generate aria2c input file
    local aria_input="/tmp/aria_input_${db_name//\//_}.txt"
    rm -f "$aria_input"
    
    while IFS= read -r relpath; do
        local url="${s3_path}/${relpath}"
        local destdir="${db_path}/$(dirname "$relpath")"
        local filename=$(basename "$relpath")
        mkdir -p "$destdir"
        
        if [ -f "${db_path}/${relpath}" ]; then
            echo "  SKIP (exists): ${relpath}"
            continue
        fi
        
        # aria2c format: URL\n  dir=...\n  out=...
        echo "$url" >> "$aria_input"
        echo "  dir=$destdir" >> "$aria_input"
        echo "  out=$filename" >> "$aria_input"
    done <<< "$files"
    
    if [ ! -f "$aria_input" ] || [ ! -s "$aria_input" ]; then
        echo "  All files already downloaded."
        return 0
    fi
    
    local num_files=$(grep -c "^https" "$aria_input" 2>/dev/null || echo "?")
    echo "  Downloading ${num_files} files with aria2c (8 parallel)..."
    
    aria2c \
        --input-file="$aria_input" \
        --max-concurrent-downloads=8 \
        --split=4 \
        --max-connection-per-server=4 \
        --check-certificate=false \
        --file-allocation=trunc \
        --continue=true \
        --auto-file-renaming=false
    
    echo "  Done downloading ${db_name}"
}

# Download dbnsfp-grch37
download_db "dbnsfp-grch37-4.5a+0.39.0"

# Download dbscsnv-grch37
download_db "dbscsnv-grch37-1.1+0.39.0"

echo ""
echo "=== Creating symlinks in annonars/grch37/ ==="

# dbnsfp symlink
if [ ! -L "${ANNONARS_DIR}/dbnsfp" ]; then
    ln -sr "${TARGET_BASE}/dbnsfp-grch37-4.5a+0.39.0" "${ANNONARS_DIR}/dbnsfp"
    echo "Created symlink: dbnsfp -> dbnsfp-grch37-4.5a+0.39.0"
else
    echo "Symlink dbnsfp already exists: $(readlink ${ANNONARS_DIR}/dbnsfp)"
fi

# dbscsnv symlink
if [ ! -L "${ANNONARS_DIR}/dbscsnv" ]; then
    ln -sr "${TARGET_BASE}/dbscsnv-grch37-1.1+0.39.0" "${ANNONARS_DIR}/dbscsnv"
    echo "Created symlink: dbscsnv -> dbscsnv-grch37-1.1+0.39.0"
else
    echo "Symlink dbscsnv already exists: $(readlink ${ANNONARS_DIR}/dbscsnv)"
fi

echo ""
echo "=== Restarting reev-annonars ==="
cd /home/arkantu/workspace/reev
docker compose restart reev-annonars

echo ""
echo "=== All done! ==="
