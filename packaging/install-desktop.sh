#!/usr/bin/env bash
set -euo pipefail
# Install a launcher for the current user. Adjust PHOTOSWIPE_BIN to the path of
# the packaged binary or the `photoswipe` console script.
APP_DIR="${HOME}/.local/share/photoswipe"
BIN="${PHOTOSWIPE_BIN:-$(command -v photoswipe || true)}"
if [[ -z "${BIN}" ]]; then
  echo "Сначала установите PhotoSwipe: pipx install . или pip install ." >&2
  exit 1
fi
mkdir -p "${APP_DIR}" "${HOME}/.local/share/applications" "${HOME}/.local/share/icons/hicolor/512x512/apps"
cp assets/icon-512.png "${HOME}/.local/share/icons/hicolor/512x512/apps/photoswipe.png"
sed "s|^Exec=.*|Exec=${BIN}|" packaging/photoswipe.desktop > "${HOME}/.local/share/applications/photoswipe.desktop"
update-desktop-database "${HOME}/.local/share/applications" 2>/dev/null || true
echo "Установлено в ${HOME}/.local/share/applications/photoswipe.desktop"
