from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

_PATHS: dict[str, str] = {
    "aperture": '<circle cx="12" cy="12" r="9"/><path d="M12 3v9l7.8 4.5"/><path d="M20.8 12.5l-4.5-7.8"/><path d="M16.3 20.3L12 12"/><path d="M7.7 20.3L12 12"/><path d="M3.2 12.5l4.5 7.8"/><path d="M3.2 11.5l4.5-7.8"/>',
    "heart": '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0 0-7.8Z"/>',
    "trash": '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.3 9a2.8 2.8 0 1 1 4.4 2.4c-.9.6-1.7 1.1-1.7 2.6"/><path d="M12 17.5h.01"/>',
    "settings": '<path d="M4 7h10"/><path d="M18 7h2"/><circle cx="16" cy="7" r="2"/><path d="M4 17h2"/><path d="M10 17h10"/><circle cx="8" cy="17" r="2"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h9a7 7 0 0 1 0 14h-1"/>',
    "compare": '<rect x="3" y="4" width="7.5" height="16" rx="1.5"/><rect x="13.5" y="4" width="7.5" height="16" rx="1.5"/>',
    "zoom-in": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/><path d="M11 8v6"/><path d="M8 11h6"/>',
    "zoom-out": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/><path d="M8 11h6"/>',
    "rotate-cw": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 2.6-6.4"/><path d="M3 3v6h6"/>',
    "maximize": '<path d="M8 3H3v5"/><path d="M16 3h5v5"/><path d="M21 16v5h-5"/><path d="M3 16v5h5"/>',
    "minimize": '<path d="M8 3v5H3"/><path d="M16 3v5h5"/><path d="M21 16h-5v5"/><path d="M3 16h5v5"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    "folder-plus": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M12 11v5"/><path d="M9.5 13.5h5"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "check": '<path d="m4 12 5 5L20 6"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="m21 16-4.5-4.5L7 21"/>',
    "alert": '<path d="M10.3 3.7 2.4 17.5A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.5L13.7 3.7a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "sparkles": '<path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5Z"/><path d="M19 15l.7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7Z"/><path d="M5 3l.6 1.8L7.5 5l-1.9.6L5 7.5l-.6-1.9L2.5 5l1.9-.2Z"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18"/><path d="M12 3a14 14 0 0 0 0 18"/>',
    "gamepad": '<path d="M7.5 7h9a5.5 5.5 0 0 1 5.4 6.6l-.6 3A3 3 0 0 1 16 18.4L14.5 17h-5L8 18.4a3 3 0 0 1-5.3-1.8l-.6-3A5.5 5.5 0 0 1 7.5 7Z"/><path d="M8 11v4"/><path d="M6 13h4"/><path d="M16.5 12h.01"/><path d="M18.5 14h.01"/>',
    "keyboard": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01"/><path d="M10 10h.01"/><path d="M14 10h.01"/><path d="M18 10h.01"/><path d="M7 14h10"/>',
    "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
    "more": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    "arrow-up": '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
    "arrow-down": '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
    "arrow-left": '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13" r="3.5"/>',
    "skip": '<path d="m5 4 10 8-10 8V4Z"/><path d="M19 5v14"/>',
    "star": '<path d="m12 3 2.7 5.5 6 .9-4.3 4.2 1 6-5.4-2.9-5.4 2.9 1-6L3.3 9.4l6-.9L12 3Z"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "sliders": '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="7" cy="18" r="2"/>',
    "rotate": '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>',
    "corner-up-left": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "filter": '<path d="M3 5h18l-7 8v6l-4-2v-4L3 5Z"/>',
    "eye": '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "hard-drive": '<path d="M4 15h16"/><path d="M5 5h14l2 6v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6l2-6Z"/><path d="M7 18h.01"/><path d="M11 18h.01"/>',
}


def svg_markup(name: str, color: str = theme.TEXT) -> str:
    inner = _PATHS.get(name, _PATHS["image"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{inner}</svg>"
    )


@lru_cache(maxsize=512)
def _pixmap(name: str, color: str, size: int, ratio: int = 2) -> QPixmap:
    markup = svg_markup(name, color)
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    pixel_size = max(1, size * ratio)
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, pixel_size, pixel_size))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon(name: str, color: str = theme.TEXT, size: int = 20) -> QIcon:
    return QIcon(_pixmap(name, color, size))


@lru_cache(maxsize=16)
def brand_pixmap(size: int = 44) -> QPixmap:
    ratio = 2
    pixmap = QPixmap(size * ratio, size * ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    from PySide6.QtGui import QLinearGradient

    gradient = QLinearGradient(0, 0, size * ratio, size * ratio)
    gradient.setColorAt(0.0, QColor("#f8d47d"))
    gradient.setColorAt(0.55, QColor("#eeb34e"))
    gradient.setColorAt(1.0, QColor("#c8872f"))
    painter.setBrush(gradient)
    radius = size * ratio * 0.28
    painter.drawRoundedRect(0, 0, size * ratio, size * ratio, radius, radius)
    mark = QSvgRenderer(
        QByteArray(
            (
                '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
                'fill="none" stroke="#241b0b" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">'
                '<rect x="3.8" y="4.6" width="12.4" height="12.4" rx="2.4"/>'
                '<circle cx="7.8" cy="8.7" r="1.05" fill="#241b0b" stroke="none"/>'
                '<path d="m5.2 14.6 3.2-3.2 2.4 2.4 1.7-1.7 2.2 2.2"/>'
                '<path d="M8.2 20.2h8.1a3 3 0 0 0 3-3V9.1"/>'
                "</svg>"
            ).encode("utf-8")
        )
    )
    margin = size * ratio * 0.17
    mark.render(
        painter,
        QRectF(margin, margin, size * ratio - 2 * margin, size * ratio - 2 * margin),
    )
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
