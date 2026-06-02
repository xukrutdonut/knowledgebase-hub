#!/usr/bin/env python3
import os
import re
from pathlib import Path

DIAGRAMS_DIR = "/home/arkantu/workspace/docker/genomic-stack/services/knowledgebase-hub/public/diagrams"

def enhance_svg_for_responsiveness(content):
    """Enhance SVG for responsiveness and modern best practices"""
    
    # Add preserveAspectRatio and make viewBox responsive-friendly
    content = re.sub(
        r'<svg\s+xmlns="[^"]*"\s+viewBox="([^"]*)"',
        lambda m: f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{m.group(1)}" preserveAspectRatio="xMidYMid meet" width="100%" height="auto"',
        content,
        count=1
    )
    
    # Add style for better rendering
    style_injection = '''
  <style>
    svg { max-width: 100%; height: auto; display: block; }
    @media (prefers-reduced-motion: reduce) {
      * { animation: none !important; transition: none !important; }
    }
  </style>'''
    
    # Insert style after <defs> if not present
    if '<style>' not in content or 'max-width: 100%' not in content:
        defs_end = content.find('</defs>')
        if defs_end > 0:
            content = content[:defs_end+7] + style_injection + content[defs_end+7:]
    
    # Remove unnecessary whitespace between tags
    content = re.sub(r'>\s+<', '><', content)
    
    # Ensure proper meta-viewport info via comments
    meta_comment = '''<!-- NeuropedGx Hub Biomedical Diagram | Responsive SVG | Optimized for accessibility -->
'''
    if 'NeuropedGx Hub' not in content:
        content = meta_comment + content
    
    return content

def process_files():
    """Process all SVG files"""
    svg_files = sorted(Path(DIAGRAMS_DIR).glob('*.svg'))
    
    for svg_file in svg_files:
        try:
            with open(svg_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            enhanced = enhance_svg_for_responsiveness(content)
            
            with open(svg_file, 'w', encoding='utf-8') as f:
                f.write(enhanced)
            
            # Get size reduction
            orig_size = len(content)
            new_size = len(enhanced)
            reduction = ((orig_size - new_size) / orig_size * 100) if orig_size > 0 else 0
            
            print(f"✓ {svg_file.name:25} → Responsive + Optimized ({reduction:+.1f}%)")
        except Exception as e:
            print(f"✗ {svg_file.name:25} → Error: {e}")

process_files()
