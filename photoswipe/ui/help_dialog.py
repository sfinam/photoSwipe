from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..controller import button_label
from ..i18n import tr
from ..shortcuts import action_hint, action_label, display_combo
from . import theme
from .icons import icon
from .widgets import HLine, KeyBadge


class HelpDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Help — PhotoSwipe"))
        self.setModal(True)
        self.resize(800, 680)
        self.setMinimumSize(680, 540)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel(tr("How to use PhotoSwipe"))
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 19pt; font-weight: 750;")
        header.addWidget(title)
        header.addStretch(1)
        close = QPushButton(tr("Close"))
        close.setProperty("role", "ghost")
        close.clicked.connect(self.accept)
        header.addWidget(close)
        root.addLayout(header)
        tabs = QTabWidget()
        tabs.addTab(self._shortcuts_tab(config), tr("Keys"))
        tabs.addTab(self._gestures_tab(config), tr("Swipes and controller"))
        tabs.addTab(self._about_tab(), tr("How it works"))
        root.addWidget(tabs, 1)

    def _scroll(self, content: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setWidget(content)
        return area

    def _shortcuts_tab(self, config: Config) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        intro = QLabel(
            tr(
                "Every action can be reassigned in Settings. Arrow keys work in any layout. The on-screen buttons do the same."
            )
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9.4pt;")
        layout.addWidget(intro)
        panel = QFrame()
        panel.setProperty("role", "subtle")
        body = QVBoxLayout(panel)
        body.setContentsMargins(16, 10, 16, 10)
        body.setSpacing(5)
        for index, action in enumerate(config.shortcuts.keys()):
            row = QHBoxLayout()
            row.setSpacing(9)
            text = QVBoxLayout()
            text.setSpacing(0)
            label = QLabel(action_label(action))
            label.setStyleSheet(
                f"color: {theme.TEXT}; font-size: 9.6pt; font-weight: 600;"
            )
            hint = QLabel(action_hint(action))
            hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.2pt;")
            text.addWidget(label)
            text.addWidget(hint)
            row.addLayout(text, 1)
            bindings = config.shortcuts.get(action, [])
            if not bindings:
                empty = QLabel(tr("not assigned"))
                empty.setStyleSheet(
                    f"color: {theme.TEXT_DIM}; font-size: 8.8pt; font-style: italic;"
                )
                row.addWidget(empty)
            for combo in bindings:
                row.addWidget(KeyBadge(display_combo(combo)))
            body.addLayout(row)
            if index < len(config.shortcuts) - 1:
                body.addWidget(HLine())
        layout.addWidget(panel)
        layout.addWidget(
            self._note(
                tr(
                    "In comparison mode: ← / A chooses the left shot, → / D the right one, Space keeps both as favorites, S defers the pair, Esc exits. These keys are fixed and independent of the main shortcut layout."
                )
            )
        )
        layout.addStretch(1)
        return self._scroll(page)

    def _gestures_tab(self, config: Config) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section(tr("Mouse or touch swipes")))
        gestures = QHBoxLayout()
        gestures.setSpacing(8)
        for icon_name, color, title, detail in (
            ("arrow-left", theme.RED, tr("Left"), tr("to trash")),
            ("arrow-right", theme.GREEN, tr("Right"), tr("to favorites")),
            ("arrow-up", theme.BLUE, tr("Up"), tr("to second round")),
            ("arrow-down", theme.AMBER, tr("Down"), tr("to Maybe")),
        ):
            card = QFrame()
            card.setProperty("role", "subtle")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(13, 11, 13, 11)
            card_layout.setSpacing(4)
            icon_label = QLabel()
            icon_label.setPixmap(icon(icon_name, color, 24).pixmap(24, 24))
            card_layout.addWidget(icon_label)
            title_label = QLabel(title)
            title_label.setStyleSheet(
                f"color: {theme.TEXT}; font-size: 10pt; font-weight: 600;"
            )
            detail_label = QLabel(detail)
            detail_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.7pt;")
            card_layout.addWidget(title_label)
            card_layout.addWidget(detail_label)
            gestures.addWidget(card, 1)
        layout.addLayout(gestures)
        layout.addWidget(
            self._note(
                tr(
                    "Swiping works when the photo is fitted to the window. If you zoom in, dragging pans the image. Double-click toggles between fit and 1:1 preview scale. The mouse wheel zooms around the cursor."
                )
            )
        )

        layout.addWidget(self._section(tr("Controller")))
        controller_panel = QFrame()
        controller_panel.setProperty("role", "subtle")
        body = QVBoxLayout(controller_panel)
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(5)
        for action in (
            "favorite",
            "trash",
            "maybe",
            "round2",
            "undo",
            "compare",
            "zoomIn",
            "zoomOut",
            "rotateCw",
            "rotateCcw",
        ):
            values = config.controller.mappings.get(action, [])
            if not values:
                continue
            row = QHBoxLayout()
            label = QLabel(action_label(action))
            label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9.2pt;")
            row.addWidget(label, 1)
            for index in values:
                row.addWidget(KeyBadge(button_label(index)))
            body.addLayout(row)
        layout.addWidget(controller_panel)
        layout.addWidget(
            self._note(
                tr(
                    "In comparison: D-pad ←/→ or LB/RB choose a shot, A keeps both, B exits, Back undoes. Controller connection is detected automatically."
                )
            )
        )
        layout.addStretch(1)
        return self._scroll(page)

    def _about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section(tr("Four decisions")))
        steps = (
            (
                "heart",
                theme.GREEN,
                tr("Favorite"),
                tr("The file (and its RAW pair) is moved to the Favorites folder."),
            ),
            (
                "trash",
                theme.RED,
                tr("Trash"),
                tr(
                    "The file is moved to the configured trash folder. It is not the system recycle bin, so you can undo the action inside the app."
                ),
            ),
            (
                "clock",
                theme.AMBER,
                tr("Maybe"),
                tr("The file goes to a separate folder so you can return to it later."),
            ),
            (
                "clock",
                theme.BLUE,
                tr("Second round"),
                tr(
                    "The file stays in place and goes into a separate queue. The second round shows only deferred shots."
                ),
            ),
        )
        for icon_name, color, title, text in steps:
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = QLabel()
            badge.setFixedSize(34, 34)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {theme.PANEL_RAISED}; border: 1px solid {theme.BORDER}; border-radius: 10px;"
            )
            badge.setPixmap(icon(icon_name, color, 17).pixmap(17, 17))
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            text_box = QVBoxLayout()
            text_box.setSpacing(1)
            head = QLabel(title)
            head.setStyleSheet(
                f"color: {theme.TEXT}; font-size: 10pt; font-weight: 600;"
            )
            desc = QLabel(text)
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.9pt;")
            text_box.addWidget(head)
            text_box.addWidget(desc)
            row.addLayout(text_box, 1)
            layout.addLayout(row)
        layout.addWidget(HLine())
        layout.addWidget(self._section("RAW + JPEG"))
        layout.addWidget(
            self._note(
                tr(
                    "Files with the same name and different extensions are treated as one photo. You can switch between ARW and JPEG for viewing, but a decision applies to the whole pair, including XMP and other sidecar files. RAW is shown via the camera’s embedded preview; full decoding can be enabled in Settings."
                )
            )
        )
        layout.addWidget(self._section(tr("Safety")))
        layout.addWidget(
            self._note(
                tr(
                    "Everything runs locally. Files are moved, not copied, with name-collision checks. The last 120 actions can be undone even after a restart. App data and preview cache live in the system app folder and never inside your photo library."
                )
            )
        )
        layout.addStretch(1)
        return self._scroll(page)

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 12.5pt; font-weight: 700;"
        )
        return label

    def _note(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 9.2pt; background: {theme.BG_DEEP};"
            f"border: 1px solid {theme.BORDER}; border-radius: 9px; padding: 11px 13px;"
        )
        return label
