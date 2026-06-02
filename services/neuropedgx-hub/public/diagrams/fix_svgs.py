#!/usr/bin/env python3
import re
from pathlib import Path

DIAGRAMS_DIR = "/home/arkantu/workspace/docker/genomic-stack/services/neuropedgx-hub/public/diagrams"

TITLE_MAP = {
    'mtor.svg': 'mTORopatías — Vía PI3K/AKT/mTOR',
    'channelopathy.svg': 'Canalopatías — Disfunción del Canal Iónico',
    'nt_synthesis.svg': 'Síntesis de Neurotransmisores',
    'lysosomal.svg': 'Enfermedades Lisosomales de Depósito',
    'interferonopathy.svg': 'Interferonopías',
    'mitochondrial.svg': 'Enfermedades Mitocondriales',
    'rasopathy.svg': 'RASopatías',
    'dystrophin.svg': 'Distrofias Musculares - Complejo de Distroglucano',
    'peroxisomal.svg': 'Enfermedades Peroxisomales',
    'cmt.svg': 'Neuropatía Motora y Sensitiva Hereditaria'
}

def restore_svg(filepath):
    """Restore SVG file with proper structure"""
    filename = Path(filepath).name
    
    # Get file backup from git or read it properly
    import subprocess
    try:
        # Read raw from git to get original
        result = subprocess.run(['git', 'show', f'HEAD:{filepath}'], 
                              capture_output=True, text=True, cwd='/home/arkantu/workspace/docker/genomic-stack')
        if result.returncode == 0:
            original = result.stdout
        else:
            return False
    except:
        return False
    
    # Find and add enhancements
    title = TITLE_MAP.get(filename, 'Diagrama Biomédico')
    
    # Extract just SVG opening tag to re-write properly
    svg_match = re.search(r'<svg[^>]*viewBox="[^"]*"', original)
    if not svg_match:
        return False
    
    svg_tag = svg_match.group(0)
    
    # Enhanced SVG tag
    new_svg_tag = svg_tag.replace(
        'viewBox',
        'role="img" aria-label="' + title + '" preserveAspectRatio="xMidYMid meet" width="100%" height="auto" viewBox'
    )
    
    enhanced = original.replace(svg_tag, new_svg_tag)
    
    # Add title/desc after <defs>
    if '<title>' not in enhanced:
        defs_match = re.search(r'</defs>', enhanced)
        if defs_match:
            pos = defs_match.end()
            insert = f'<title>{title}</title><desc>Diagrama interactivo - NeuropedGx Hub</desc>'
            enhanced = enhanced[:pos] + insert + enhanced[pos:]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(enhanced)
    
    return True

# Check git status
import subprocess
result = subprocess.run(['git', 'status', '--porcelain'], 
                       capture_output=True, text=True, 
                       cwd='/home/arkantu/workspace/docker/genomic-stack')
print("Git status:")
print(result.stdout if result.stdout else "All clean")

