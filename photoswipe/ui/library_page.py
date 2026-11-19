from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..config import Config, Source
from ..i18n import LANGUAGES, current_language, tr
from . import theme
from .icons import brand_pixmap, icon
from .widgets import BrandWidget, Card, IconButton, StatPill

FEATURES = (
    ("layers", "RAW + JPEG together", "The format pair is treated as one photo"),
    ("keyboard", "Swipes, keys, gamepad", "Make decisions in one motion"),
    ("compare", "One-on-one comparison", "Pick the better shot from a pair"),
    ("rotate", "Zoom and rotate", "Inspect the details before deciding"),
)


def _relative_time(value: str | None) -> str:
    if not value:
        return tr("Not opened yet")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return ""
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    now = datetime.now(moment.tzinfo) if moment.tzinfo else datetime.now()
    delta = now - moment
    seconds = delta.total_seconds()
    if seconds < 60:
        return tr("Just now")
    if seconds < 3600:
        return tr("{minutes} min ago", minutes=int(seconds // 60))
    if seconds < 86400 and moment.date() == now.date():
        return tr("Today, {time}", time=f"{moment:%H:%M}")
    if seconds < 172800:
        return tr("Yesterday, {time}", time=f"{moment:%H:%M}")
    return moment.strftime("%d.%m.%Y")


class HeroArt(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(390, 250)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        def card(rect: QRectF, angle: float, top: str, bottom: str, alpha: int) -> None:
            painter.save()
            painter.translate(rect.center())
            painter.rotate(angle)
            painter.translate(-rect.center())
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            c1 = QColor(top)
            c2 = QColor(bottom)
            c1.setAlpha(alpha)
            c2.setAlpha(alpha)
            gradient.setColorAt(0, c1)
            gradient.setColorAt(1, c2)
            painter.setBrush(gradient)
            painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
            painter.drawRoundedRect(rect, 18, 18)
            # Photo-ish horizon and sun.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 22))
            painter.drawRoundedRect(
                rect.adjusted(22, rect.height() * 0.55, -22, -24), 10, 10
            )
            painter.setBrush(QColor(theme.ACCENT))
            painter.drawEllipse(QPointF(rect.right() - 74, rect.top() + 62), 18, 18)
            painter.restore()

        card(QRectF(42, 58, 190, 135), -10, "#5c735f", "#2a3b33", 255)
        card(QRectF(132, 44, 196, 140), 4, "#8b7046", "#45351f", 255)
        card(QRectF(185, 80, 176, 126), 11, "#4b5a73", "#232c3c", 255)

        # Brand mark on the top card.
        painter.save()
        painter.translate(286, 108)
        painter.rotate(11)
        logo = brand_pixmap(44)
        painter.drawPixmap(-22, -22, logo)
        painter.restore()

        # Decision chips floating around the stack.
        for x, y, name, color, angle in (
            (34, 26, "heart", theme.GREEN, -8),
            (320, 34, "trash", theme.RED, 9),
            (46, 204, "clock", theme.AMBER, 5),
            (304, 210, "compare", theme.BLUE, -6),
        ):
            painter.save()
            painter.translate(x, y)
            painter.rotate(angle)
            painter.setBrush(QColor(theme.PANEL_RAISED))
            painter.setPen(QPen(QColor(theme.BORDER_LIGHT), 1))
            painter.drawRoundedRect(QRectF(0, 0, 40, 40), 12, 12)
            painter.drawPixmap(8, 8, icon(name, color, 24).pixmap(24, 24))
            painter.restore()
        painter.end()


class FeatureRow(QWidget):
    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)
        badge = QLabel()
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {theme.PANEL_RAISED}; border: 1px solid {theme.BORDER}; border-radius: 10px;"
        )
        badge.setPixmap(icon(icon_name, theme.ACCENT, 17).pixmap(17, 17))
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 10pt; font-weight: 600;"
        )
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        desc_label.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(desc_label)
        layout.addLayout(text, 1)


class SourceCard(Card):
    open_requested = Signal(str)
    menu_requested = Signal(str, str)

    def __init__(
        self, source: Source, summary: dict[str, Any], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.summary = summary
        self.setMinimumHeight(252)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 17)
        root.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(12)
        folder = QLabel()
        folder.setFixedSize(44, 44)
        folder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hue = sum(ord(c) for c in source.name) % 4
        accents = (theme.ACCENT, theme.BLUE, theme.GREEN, theme.VIOLET)
        tinted = QColor(accents[hue])
        folder.setStyleSheet(
            f"background: rgba({tinted.red()}, {tinted.green()}, {tinted.blue()}, 22);"
            f"border: 1px solid rgba({tinted.red()}, {tinted.green()}, {tinted.blue()}, 57);"
            "border-radius: 13px;"
        )
        folder.setPixmap(icon("folder", accents[hue], 22).pixmap(22, 22))
        top.addWidget(folder, 0, Qt.AlignmentFlag.AlignTop)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 1, 0, 0)
        title_box.setSpacing(2)
        name = QLabel(source.name)
        name.setStyleSheet(f"color: {theme.TEXT}; font-size: 13pt; font-weight: 650;")
        name.setWordWrap(False)
        path = QLabel(source.path)
        path.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.8pt;")
        path.setToolTip(source.path)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Elide manually because QLabel does not track the card width for us.
        metrics = path.fontMetrics()
        path.setText(metrics.elidedText(source.path, Qt.TextElideMode.ElideMiddle, 250))
        title_box.addWidget(name)
        title_box.addWidget(path)
        top.addLayout(title_box, 1)

        menu_button = IconButton("more", tr("Folder actions"), button_size=32, size=18)
        menu_button.clicked.connect(self._show_menu)
        top.addWidget(menu_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        stats = QHBoxLayout()
        stats.setSpacing(6)
        counts = summary.get("stats", {})
        self.favorite_pill = StatPill(
            "heart", theme.GREEN, counts.get("favorite", 0), tr("Favorites")
        )
        self.trash_pill = StatPill(
            "trash", theme.RED, counts.get("trash", 0), tr("Trash")
        )
        self.maybe_pill = StatPill(
            "clock", theme.AMBER, counts.get("maybe", 0), tr("Maybe")
        )
        self.deferred_pill = StatPill(
            "clock",
            theme.BLUE,
            counts.get("round2", summary.get("deferred", 0)),
            tr("Second round"),
        )
        stats.addWidget(self.favorite_pill)
        stats.addWidget(self.trash_pill)
        stats.addWidget(self.maybe_pill)
        if summary.get("deferred", 0):
            stats.addWidget(self.deferred_pill)
        stats.addStretch(1)
        root.addLayout(stats)

        progress_box = QVBoxLayout()
        progress_box.setSpacing(5)
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        total = int(summary.get("total") or 0)
        processed = int(summary.get("processed") or 0)
        remaining = int(summary.get("remaining") or 0)
        deferred = int(summary.get("deferred") or 0)
        if summary.get("has_session"):
            if total > 0 and processed >= total:
                status_text = tr("Complete")
            elif summary.get("mode") == "second":
                status_text = tr("Round 2 · remaining {count}", count=remaining)
            else:
                status_text = tr("Remaining {count}", count=remaining + deferred)
        else:
            status_text = tr("Ready to sort")
        status = QLabel(status_text)
        status.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.8pt;")
        counter = QLabel(f"{processed} / {total}" if total else "")
        counter.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.8pt;")
        progress_row.addWidget(status)
        progress_row.addStretch(1)
        progress_row.addWidget(counter)
        progress_box.addLayout(progress_row)
        bar = QProgressBar()
        bar.setRange(0, max(1, total))
        bar.setValue(min(processed, total) if total else 0)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        if total and processed >= total:
            bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {theme.GREEN}; border-radius: 3px; }}"
            )
        progress_box.addWidget(bar)
        root.addLayout(progress_box)

        root.addStretch(1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        when = QLabel(
            _relative_time(summary.get("updated_at"))
            if summary.get("has_session")
            else tr("Not opened yet")
        )
        when.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.6pt;")
        footer.addWidget(when)
        footer.addStretch(1)
        if not source.exists:
            missing = QLabel(tr("Folder unavailable"))
            missing.setProperty("role", "warning")
            footer.addWidget(missing)
        start = QPushButton(
            tr("Continue") if summary.get("has_session") else tr("Sort")
        )
        start.setProperty("role", "primary")
        start.setCursor(Qt.CursorShape.PointingHandCursor)
        start.setEnabled(source.exists)
        start.setIcon(icon("arrow-right", "#1b1507", 15))
        start.setIconSize(QSize(15, 15))
        start.clicked.connect(lambda: self.open_requested.emit(self.source.id))
        footer.addWidget(start)
        root.addLayout(footer)
        self._start_button = start

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if self.source.exists:
            self.open_requested.emit(self.source.id)
        super().mouseDoubleClickEvent(event)

    def _show_menu(self) -> None:
        menu = QMenu(self)
        open_action = menu.addAction(
            icon("folder", theme.TEXT_MUTED, 16), tr("Open folder")
        )
        open_action.triggered.connect(
            lambda: self.menu_requested.emit(self.source.id, "reveal")
        )
        rename_action = menu.addAction(
            icon("settings", theme.TEXT_MUTED, 16), tr("Rename")
        )
        rename_action.triggered.connect(
            lambda: self.menu_requested.emit(self.source.id, "rename")
        )
        recursive_action = menu.addAction(tr("Scan subfolders"))
        recursive_action.setCheckable(True)
        recursive_action.setChecked(self.source.recursive)
        recursive_action.triggered.connect(
            lambda checked: self.menu_requested.emit(
                self.source.id, "recursive" if checked else "flat"
            )
        )
        menu.addSeparator()
        reset_action = menu.addAction(
            icon("refresh", theme.AMBER, 16), tr("Reset progress")
        )
        reset_action.triggered.connect(
            lambda: self.menu_requested.emit(self.source.id, "reset")
        )
        remove_action = menu.addAction(
            icon("trash", theme.RED, 16), tr("Remove from library")
        )
        remove_action.triggered.connect(
            lambda: self.menu_requested.emit(self.source.id, "remove")
        )
        menu.exec(QCursor.pos())


class AddFolderCard(QFrame):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(252)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame {{ background: transparent; border: 1px dashed {theme.BORDER_LIGHT}; border-radius: 16px; }}"
            "QFrame:hover { border-color: #6a5a35; background: #17150f; }"
            "QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        circle = QLabel()
        circle.setFixedSize(54, 54)
        circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle.setStyleSheet(
            f"background: {theme.PANEL_RAISED}; border: 1px solid {theme.BORDER}; border-radius: 27px;"
        )
        circle.setPixmap(icon("plus", theme.ACCENT, 24).pixmap(24, 24))
        layout.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)
        title = QLabel(tr("Add folder"))
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 11pt; font-weight: 600;")
        subtitle = QLabel(tr("Choose any folder on disk"))
        subtitle.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignHCenter)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class LibraryPage(QWidget):
    add_requested = Signal()
    open_requested = Signal(str)
    settings_requested = Signal()
    help_requested = Signal()
    source_action = Signal(str, str)
    language_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageRoot")
        self._config: Config | None = None
        self._summaries: dict[str, dict] = {}
        self._cards: list[QWidget] = []
        self._columns = 0
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.timeout.connect(self._relayout_cards)

        root = QVBoxLayout(self)
        root.setContentsMargins(38, 26, 38, 20)
        root.setSpacing(20)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(BrandWidget())
        header.addStretch(1)
        self.language_button = IconButton(
            "globe",
            tr(
                "Language: {language}",
                language=LANGUAGES.get(current_language(), current_language()),
            ),
            button_size=38,
            size=19,
        )
        self.language_button.clicked.connect(self._show_language_menu)
        self.controller_button = IconButton(
            "gamepad",
            tr("Gamepad not connected"),
            color=theme.GREEN,
            button_size=38,
            size=20,
        )
        self.controller_button.hide()
        self.help_button = IconButton(
            "help", tr("Help and shortcuts"), button_size=38, size=19
        )
        self.help_button.clicked.connect(self.help_requested)
        self.settings_button = IconButton(
            "settings", tr("Settings"), button_size=38, size=19
        )
        self.settings_button.clicked.connect(self.settings_requested)
        self.add_button = QPushButton(tr("Add folder"))
        self.add_button.setProperty("role", "primary")
        self.add_button.setIcon(icon("plus", "#1b1507", 16))
        self.add_button.setIconSize(QSize(16, 16))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.add_requested)
        header.addWidget(self.language_button)
        header.addWidget(self.controller_button)
        header.addWidget(self.help_button)
        header.addWidget(self.settings_button)
        header.addWidget(self.add_button)
        root.addLayout(header)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title = QLabel(tr("Library"))
        self.title.setProperty("role", "title")
        self.subtitle = QLabel("")
        self.subtitle.setProperty("role", "muted")
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        title_row.addLayout(title_box)
        title_row.addStretch(1)
        self.summary_label = QLabel("")
        self.summary_label.setProperty("role", "badge")
        title_row.addWidget(self.summary_label, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(title_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("PageRoot")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 8)
        self.content_layout.setSpacing(16)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)

        self.empty_panel = self._build_empty_panel()
        self.content_layout.addWidget(self.empty_panel)
        self.cards_host = QWidget()
        self.cards_host.setObjectName("PageRoot")
        self.cards_grid = QGridLayout(self.cards_host)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setHorizontalSpacing(16)
        self.cards_grid.setVerticalSpacing(16)
        self.cards_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_layout.addWidget(self.cards_host)
        self.tips_panel = self._build_tips_panel()
        self.content_layout.addWidget(self.tips_panel)
        self.content_layout.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        local = QLabel(tr("Local · no cloud · RAW + JPEG"))
        local.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.6pt;")
        footer.addWidget(local)
        footer.addStretch(1)
        self.footer_link = QPushButton(tr("Shortcuts"))
        self.footer_link.setProperty("role", "link")
        self.footer_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.footer_link.clicked.connect(self.help_requested)
        footer.addWidget(self.footer_link)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    def _build_empty_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "panel")
        panel.setStyleSheet(
            f'QFrame[role="panel"] {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1,'
            f" stop:0 #191b1f, stop:0.55 #15171b, stop:1 #1e1a12);"
            f" border: 1px solid {theme.BORDER}; border-radius: 18px; }}"
        )
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(34, 30, 30, 30)
        layout.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(14)
        eyebrow = QLabel(tr("PHOTO CULLING WITHOUT EXTRA CLICKS"))
        eyebrow.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 8.5pt; font-weight: 800; letter-spacing: 1.4px;"
        )
        left.addWidget(eyebrow)
        heading = QLabel(tr("Pick the best\nshots in one evening"))
        heading.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 27pt; font-weight: 750; line-height: 1.05;"
        )
        left.addWidget(heading)
        description = QLabel(
            tr(
                "Add a folder with photos. Swipe, press the arrow keys or use a gamepad — "
                "the files will be sorted into the Favorites, Trash and Maybe folders."
            )
        )
        description.setWordWrap(True)
        description.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10.5pt; line-height: 1.45;"
        )
        description.setMaximumWidth(600)
        left.addWidget(description)

        features = QGridLayout()
        features.setHorizontalSpacing(24)
        features.setVerticalSpacing(14)
        for index, (icon_name, title, desc) in enumerate(FEATURES):
            features.addWidget(
                FeatureRow(icon_name, tr(title), tr(desc)), index // 2, index % 2
            )
        left.addLayout(features)
        left.addSpacing(2)
        actions = QHBoxLayout()
        add = QPushButton(tr("Add your first folder"))
        add.setProperty("role", "primary")
        add.setIcon(icon("folder-plus", "#1b1507", 17))
        add.setIconSize(QSize(17, 17))
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_requested)
        add.setMinimumHeight(38)
        actions.addWidget(add)
        hint = QLabel(tr("Your photos stay on your computer"))
        hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.8pt;")
        actions.addWidget(hint)
        actions.addStretch(1)
        left.addLayout(actions)
        layout.addLayout(left, 1)
        layout.addWidget(HeroArt(), 0, Qt.AlignmentFlag.AlignVCenter)
        return panel

    def _build_tips_panel(self) -> QFrame:
        panel = QFrame()
        panel.setProperty("role", "subtle")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 17)
        layout.setSpacing(12)
        heading = QLabel(tr("How it works"))
        heading.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 11pt; font-weight: 650;"
        )
        layout.addWidget(heading)
        steps = QHBoxLayout()
        steps.setSpacing(18)
        for number, icon_name, title, text in (
            (
                "01",
                "folder-plus",
                tr("Add a folder"),
                tr(
                    "Photos stay where they are. RAW and JPEG files with the same name are merged into one card."
                ),
            ),
            (
                "02",
                "keyboard",
                tr("Make decisions"),
                tr(
                    "Arrow keys, mouse swipes, shortcuts or a gamepad. Z undoes the last action."
                ),
            ),
            (
                "03",
                "heart",
                tr("Collect the results"),
                tr(
                    "Favorites and trash are sorted into folders automatically. Uncertain shots go to the second round."
                ),
            ),
        ):
            step = QHBoxLayout()
            step.setSpacing(10)
            marker = QLabel(number)
            marker.setFixedSize(34, 34)
            marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
            marker.setStyleSheet(
                f"background: {theme.BG_DEEP}; border: 1px solid {theme.BORDER}; border-radius: 10px;"
                f" color: {theme.ACCENT}; font-size: 9pt; font-weight: 800;"
            )
            step.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
            text_box = QVBoxLayout()
            text_box.setSpacing(1)
            title_label = QLabel(title)
            title_label.setStyleSheet(
                f"color: {theme.TEXT}; font-size: 9.6pt; font-weight: 600;"
            )
            description = QLabel(text)
            description.setWordWrap(True)
            description.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.5pt;")
            text_box.addWidget(title_label)
            text_box.addWidget(description)
            step.addLayout(text_box, 1)
            steps.addLayout(step, 1)
        layout.addLayout(steps)
        return panel

    def _show_language_menu(self) -> None:
        menu = QMenu(self)
        current = current_language()
        for code, label in LANGUAGES.items():
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(code == current)
            action.triggered.connect(
                lambda _=False, value=code: self.language_requested.emit(value)
            )
        menu.exec(QCursor.pos())

    # ------------------------------------------------------------------
    def set_controller(self, name: str) -> None:
        if name:
            self.controller_button.setToolTip(
                tr("Gamepad connected: {name}", name=name)
            )
            self.controller_button.show()
        else:
            self.controller_button.hide()

    def set_data(self, config: Config, summaries: dict[str, dict]) -> None:
        self._config = config
        self._summaries = summaries
        total_processed = sum(
            int(item.get("processed", 0)) for item in summaries.values()
        )
        if config.sources:
            self.subtitle.setText(
                tr(
                    "Folders: {folders} · Photos sorted: {photos}",
                    folders=len(config.sources),
                    photos=total_processed,
                )
            )
            self.summary_label.setText(
                tr("Photos sorted: {count}", count=total_processed)
            )
            self.summary_label.show()
        else:
            self.subtitle.setText(tr("Add a folder to get started"))
            self.summary_label.hide()
        self.empty_panel.setVisible(not config.sources)
        self.cards_host.setVisible(bool(config.sources))
        self.tips_panel.setVisible(bool(config.sources))
        self._rebuild_cards()
        self._relayout_timer.start(0)

    def _rebuild_cards(self) -> None:
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for card in self._cards:
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        if not self._config:
            return
        for source in self._config.sources:
            summary = self._summaries.get(source.id, {})
            card = SourceCard(source, summary)
            card.open_requested.connect(self.open_requested)
            card.menu_requested.connect(self.source_action)
            self._cards.append(card)
        add_card = AddFolderCard()
        add_card.clicked.connect(self.add_requested)
        self._cards.append(add_card)
        self._columns = 0
        self._relayout_cards()

    def _relayout_cards(self) -> None:
        if self._config is None:
            return
        width = self.scroll.viewport().width()
        columns = 3 if width >= 1120 else 2 if width >= 760 else 1
        if columns == self._columns:
            return
        self._columns = columns
        for card in self._cards:
            self.cards_grid.removeWidget(card)
        for index, card in enumerate(self._cards):
            self.cards_grid.addWidget(card, index // columns, index % columns)
        for column in range(3):
            self.cards_grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._relayout_timer.start(40)
