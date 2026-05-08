#!/usr/bin/env bash
# Regenerate icon.icns + icon.ico from icon.svg.
# Run after editing build/icons/icon.svg.
#
# Requires:
#   - librsvg (rsvg-convert) — `brew install librsvg`
#   - Pillow in the project venv (added by `pip install -r requirements.txt`)
#   - iconutil — built into macOS
set -euo pipefail

cd "$( dirname "${BASH_SOURCE[0]}" )/icons"

if ! command -v rsvg-convert >/dev/null 2>&1; then
  echo "ERROR: rsvg-convert missing. Install with: brew install librsvg" >&2
  exit 1
fi

ICONSET="bitaxe-baller.iconset"
rm -rf "$ICONSET" win_*.png icon.icns icon.ico
mkdir -p "$ICONSET"

echo "==> rendering iconset PNGs from icon.svg"
for size_pair in "16 16x16" "32 16x16@2x" "32 32x32" "64 32x32@2x" "128 128x128" "256 128x128@2x" "256 256x256" "512 256x256@2x" "512 512x512" "1024 512x512@2x"; do
  read -r px name <<< "$size_pair"
  rsvg-convert -w "$px" -h "$px" icon.svg -o "$ICONSET/icon_${name}.png"
done

echo "==> packing icon.icns"
iconutil -c icns -o icon.icns "$ICONSET"
ls -lh icon.icns

echo "==> rendering Windows ICO sizes from icon.svg"
for size in 16 24 32 48 64 128 256; do
  rsvg-convert -w "$size" -h "$size" icon.svg -o "win_${size}.png"
done

PY=$(cd ../.. && [[ -d venv ]] && echo "venv/bin/python" || echo "python3")
( cd ../.. && "$PY" - <<'PYEOF'
from PIL import Image
sizes_desc = [256, 128, 64, 48, 32, 24, 16]
imgs = [Image.open(f"build/icons/win_{s}.png") for s in sizes_desc]
imgs[0].save(
    "build/icons/icon.ico",
    format="ICO",
    append_images=imgs[1:],
    sizes=[(s, s) for s in sizes_desc],
)
print("icon.ico written")
PYEOF
)
ls -lh icon.ico

rm -f win_*.png
rm -rf "$ICONSET"
echo "==> done. icon.icns + icon.ico are ready."
