#!/usr/bin/env bash
# Build a self-contained AppImage for Steam Deck / desktop Linux.
# Run from the repository root: ./packaging/build_appimage.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$PWD"
APPDIR="$ROOT/build/appimage/PhotoSwipe.AppDir"
OUT="$ROOT/dist/PhotoSwipe-x86_64.AppImage"
TOOL="$(command -v appimagetool || true)"

if [[ ! -x "$ROOT/.venv/bin/pyinstaller" ]]; then
  echo "PyInstaller is missing. Run ./packaging/build_linux.sh first." >&2
  exit 1
fi

if [[ -z "$TOOL" ]]; then
  TOOL="$ROOT/build/tools/appimagetool-x86_64.AppImage"
  mkdir -p "$(dirname "$TOOL")"
  if [[ ! -f "$TOOL" ]]; then
    echo "Downloading appimagetool…"
    curl -fL --retry 3 -o "$TOOL" \
      "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  fi
  chmod +x "$TOOL"
fi

echo "Building the PyInstaller onedir bundle…"
"$ROOT/.venv/bin/pyinstaller" --noconfirm --clean "$ROOT/PhotoSwipe-onedir.spec"
if [[ ! -x "$ROOT/dist/PhotoSwipeApp/PhotoSwipe" ]]; then
  echo "Expected dist/PhotoSwipeApp/PhotoSwipe, but it was not produced." >&2
  exit 1
fi

rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/lib/photoswipe" \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/dist/PhotoSwipeApp/." "$APPDIR/usr/lib/photoswipe/"
ln -s ../lib/photoswipe/PhotoSwipe "$APPDIR/usr/bin/photoswipe"
cp "$ROOT/assets/icon-512.png" "$APPDIR/photoswipe.png"
cp "$ROOT/assets/icon-512.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/photoswipe.png"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/photoswipe/PhotoSwipe" "$@"
APPRUN

cat > "$APPDIR/photoswipe.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=PhotoSwipe
GenericName=Photo Culling
Comment=Fast local photo culling with RAW and comparison
Exec=photoswipe %f
Icon=photoswipe
Terminal=false
Categories=Graphics;Photography;
Keywords=photo;raw;culling;sort;
MimeType=inode/directory;
StartupWMClass=PhotoSwipe
DESKTOP

chmod +x "$APPDIR/AppRun"
mkdir -p "$ROOT/dist"
rm -f "$OUT"

# The appimagetool release is itself an AppImage. Extract-and-run works even on
# systems without FUSE/libfuse2, including a default SteamOS installation.
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "$OUT"
chmod +x "$OUT"
echo "Готово: $OUT"
echo "Steam Deck: copy to ~/Applications, chmod +x, then add it as a non-Steam game."
