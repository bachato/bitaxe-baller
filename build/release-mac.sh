#!/usr/bin/env bash
#
# Mac-side release helper. Run AFTER `bash build/build-mac.sh` has produced
# dist/Bitaxe-Baller-Mac.dmg and dist/appcast.xml.
#
# What this does:
#   1. Downloads the existing appcast.xml from the GitHub release tag
#      (which the Windows CI populated with the Windows .exe entry on tag
#      push).
#   2. Re-runs build/build-appcast.py with the downloaded file as --out, so
#      the Mac entry MERGES into the Windows entry instead of replacing it.
#   3. Uploads the merged appcast + the Mac DMG to the release with
#      --clobber, so both platforms appear in /latest/download/appcast.xml.
#
# Without this step, uploading the local dist/appcast.xml directly would
# wipe the Windows entry — Windows users on auto-update would either see
# nothing new or fail to find the Windows download.
#
# Usage:
#   bash build/release-mac.sh v1.13.0

set -euo pipefail

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  echo "Usage: bash build/release-mac.sh <tag>   (e.g. v1.13.0)"
  exit 1
fi

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT"

DMG="dist/Bitaxe-Baller-Mac.dmg"
LOCAL_APPCAST="dist/appcast.xml"
MERGED_APPCAST="dist/appcast-merged.xml"

if [[ ! -f "$DMG" ]]; then
  echo "[!] No DMG at $DMG — run 'bash build/build-mac.sh' first."
  exit 1
fi
if [[ ! -f "$LOCAL_APPCAST" ]]; then
  echo "[!] No appcast at $LOCAL_APPCAST — run 'bash build/build-mac.sh' first."
  exit 1
fi

APP_VERSION="${TAG#v}"

echo "==> downloading existing $TAG appcast (Windows entry) → $MERGED_APPCAST"
rm -f "$MERGED_APPCAST"
if ! gh release download "$TAG" -p appcast.xml -O "$MERGED_APPCAST"; then
  echo "[!] No appcast.xml on release $TAG yet. Starting fresh with Mac-only entry."
  cp "$LOCAL_APPCAST" "$MERGED_APPCAST"
else
  echo "==> re-running build-appcast.py to merge Mac entry into existing"
  python build/build-appcast.py \
    --version "$APP_VERSION" \
    --mac-dmg "$DMG" \
    --release-notes-url "https://github.com/465media/bitaxe-baller/releases/tag/$TAG" \
    --out "$MERGED_APPCAST"
fi

echo "==> merged appcast contents:"
echo "----"
cat "$MERGED_APPCAST"
echo "----"
echo
read -r -p "Upload $DMG + merged appcast to release $TAG? (y/N) " ok
if [[ "$ok" != "y" && "$ok" != "Y" ]]; then
  echo "Aborted. Merged appcast left at $MERGED_APPCAST for inspection."
  exit 1
fi

echo "==> uploading to release $TAG"
gh release upload "$TAG" "$DMG" "$MERGED_APPCAST"#appcast.xml --clobber

echo
echo "✓ Release $TAG updated. Verify at:"
echo "    https://github.com/465media/bitaxe-baller/releases/tag/$TAG"
echo "    https://github.com/465media/bitaxe-baller/releases/latest/download/appcast.xml"
