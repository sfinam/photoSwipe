"""Optional image format registration.

HEIF/HEIC support comes from pillow-heif on platforms where its wheel is
available. The app still starts without it; unsupported files simply show a
preview error instead of breaking the whole session.
"""

from __future__ import annotations

try:  # pragma: no cover - depends on the installed wheel
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass
