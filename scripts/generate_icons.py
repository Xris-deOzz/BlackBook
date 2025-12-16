"""
Generate all PWA and favicon icons from the source logo.
Run this script from the project root directory.

Usage:
    python scripts/generate_icons.py path/to/logo.png

Requirements:
    pip install Pillow
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)


def generate_icons(source_path: str, output_dir: str = "app/static/icons"):
    """Generate all icon sizes from source image."""
    
    # Load source image
    img = Image.open(source_path)
    print(f"Loaded: {source_path} ({img.size[0]}x{img.size[1]}, {img.mode})")
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate PWA icons
    sizes = [16, 32, 48, 72, 96, 128, 144, 152, 192, 384, 512]
    for size in sizes:
        resized = img.resize((size, size), Image.LANCZOS)
        icon_path = output_path / f"icon-{size}.png"
        resized.save(icon_path, 'PNG')
        print(f"  Created: {icon_path}")
    
    # Create favicon.ico with multiple sizes
    ico_sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    ico_images = [img.resize(size, Image.LANCZOS) for size in ico_sizes]
    favicon_path = output_path / "favicon.ico"
    ico_images[0].save(favicon_path, format='ICO', sizes=ico_sizes)
    print(f"  Created: {favicon_path}")
    
    # Apple touch icon (180x180)
    apple_icon = img.resize((180, 180), Image.LANCZOS)
    apple_path = output_path / "apple-touch-icon.png"
    apple_icon.save(apple_path, 'PNG')
    print(f"  Created: {apple_path}")
    
    # Create manifest.json
    manifest_content = '''{
  "name": "Perun's BlackBook",
  "short_name": "BlackBook",
  "description": "Personal CRM for managing professional relationships",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#111827",
  "theme_color": "#f97316",
  "orientation": "any",
  "icons": [
    {"src": "/static/icons/icon-72.png", "sizes": "72x72", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-96.png", "sizes": "96x96", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-128.png", "sizes": "128x128", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-144.png", "sizes": "144x144", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-152.png", "sizes": "152x152", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-384.png", "sizes": "384x384", "type": "image/png", "purpose": "any maskable"},
    {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
  ],
  "categories": ["business", "productivity"]
}'''
    
    manifest_path = output_path / "manifest.json"
    manifest_path.write_text(manifest_content)
    print(f"  Created: {manifest_path}")
    
    print(f"\n✓ All icons generated in: {output_path}")
    print("\nNext steps:")
    print("1. Add the following to your base.html <head> section:")
    print('''
<link rel="icon" type="image/x-icon" href="/static/icons/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/icon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/static/icons/apple-touch-icon.png">
<link rel="manifest" href="/static/icons/manifest.json">
<meta name="theme-color" content="#f97316">
''')


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_icons.py <path_to_logo.png>")
        print("\nExample:")
        print("  python scripts/generate_icons.py assets/black-perun-logo_Icon_only.png")
        sys.exit(1)
    
    source = sys.argv[1]
    if not os.path.exists(source):
        print(f"Error: File not found: {source}")
        sys.exit(1)
    
    generate_icons(source)
