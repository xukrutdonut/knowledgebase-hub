#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://ceph-s3-public.cubi.bihealth.org/varfish-public/full/annonars"
DL_DIR="/media/arkantu/Storage1TB/reev/volumes/reev-static/data/download/annonars"
GRCH37="/media/arkantu/Storage1TB/reev/volumes/reev-static/data/annonars/grch37"
LOG="/home/arkantu/workspace/reev/download-annonars-grch37-missing.log"

exec > >(tee -a "$LOG") 2>&1

echo "=== Start $(date) ==="

# Packages to download
declare -A PACKAGES=(
  ["alphamissense-grch37-1+0.39.0"]="alphamissense"
  ["functional-grch37-105.20201022+0.39.0"]="functional"
  ["gnomad-sv-exomes-grch37-0.3.1+0.39.0"]="gnomad-sv-exomes"
  ["gnomad-sv-genomes-grch37-2.1.1+0.39.0"]="gnomad-sv-genomes"
  ["regions-grch37-20240711+0.39.0"]="regions"
)

_list_files() {
  local pkg="$1"
  python3 -c "
import urllib.request, urllib.parse, xml.etree.ElementTree as ET
BASE = 'https://ceph-s3-public.cubi.bihealth.org/varfish-public'
NS = 'http://s3.amazonaws.com/doc/2006-03-01/'
prefix = 'full/annonars/${pkg}/'
url = BASE + '?prefix=' + urllib.parse.quote(prefix) + '&max-keys=1000'
resp = urllib.request.urlopen(url, timeout=30)
tree = ET.parse(resp)
for k in tree.getroot().findall(f'{{{NS}}}Contents'):
    key = k.find(f'{{{NS}}}Key').text
    print(key)
"
}

for PKG in "${!PACKAGES[@]}"; do
  SYMNAME="${PACKAGES[$PKG]}"
  TARGET="$DL_DIR/$PKG"
  
  # Skip if symlink already exists
  if [ -L "$GRCH37/$SYMNAME" ]; then
    echo "⏭  $SYMNAME already symlinked, skipping"
    continue
  fi

  echo ""
  echo "▶ Downloading $PKG → $SYMNAME"
  mkdir -p "$TARGET/rocksdb"

  # Download all files
  while IFS= read -r key; do
    filename=$(basename "$key")
    dest="$TARGET/$filename"
    [ -f "$dest" ] && echo "  ✓ already exists: $filename" && continue
    echo "  ↓ $filename"
    curl -fsSL --retry 5 --retry-delay 3 \
      "https://ceph-s3-public.cubi.bihealth.org/varfish-public/$key" \
      -o "$dest"
  done < <(_list_files "$PKG" | grep -v '/$')

  echo "  ✅ $PKG downloaded"

  # Create symlink
  ln -sf "../../download/annonars/$PKG" "$GRCH37/$SYMNAME"
  echo "  🔗 Symlink: grch37/$SYMNAME → $PKG"
done

echo ""
echo "=== All done $(date) ==="
echo "=== Restarting reev-annonars ==="
cd /home/arkantu/workspace/reev
docker compose restart annonars
echo "=== annonars restarted ==="
