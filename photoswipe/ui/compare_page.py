from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..i18n import tr
from ..models import PhotoGroup, resolve_view
from ..session import SortSession
from ..shortcuts import display_combo
from . import theme
from .icons import icon
from .photo_view import PhotoView
from .widgets import Badge, ElidedLabel, HLine, IconButton
from .workers import PreviewWorker


class ComparePane(QFrame):
    choose = Signal()
    skip = Signal()

    def __init__(self, letter: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.letter = letter
        self.color = color
        self.group: PhotoGroup | None = None
        self.variant_index = 0
        self.full_raw = False
        self.setProperty("role", "panel")
        self.setStyleSheet(
            f'QFrame[role="panel"] {{ background: {theme.PANEL}; border: 1px solid {theme.BORDER};'
            " border-radius: 15px; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 11, 11, 10)
        header_layout.setSpacing(9)
        self.letter_badge = QLabel(letter)
        self.letter_badge.setFixedSize(28, 28)
        self.letter_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = QColor(color)
        self.letter_badge.setStyleSheet(
            f"background: rgba({c.red()}, {c.green()}, {c.blue()}, 30);"
            f"border: 1px solid rgba({c.red()}, {c.green()}, {c.blue()}, 80);"
            f"border-radius: 9px; color: {color}; font-weight: 800; font-size: 11pt;"
        )
        header_layout.addWidget(self.letter_badge)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        self.name_label = QLabel("")
        self.name_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 11.5pt; font-weight: 650;"
        )
        self.meta_label = ElidedLabel("")
        self.meta_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.4pt;")
        text.addWidget(self.name_label)
        text.addWidget(self.meta_label)
        header_layout.addLayout(text, 1)
        self.format_badge = Badge("")
        header_layout.addWidget(self.format_badge)

        tool_row = QHBoxLayout()
        tool_row.setSpacing(0)
        self.zoom_out = IconButton("zoom-out", tr("Zoom out"), button_size=28, size=15)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(40)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8pt;")
        self.zoom_in = IconButton("zoom-in", tr("Zoom in"), button_size=28, size=15)
        self.fit = IconButton("minimize", tr("Fit"), button_size=28, size=15)
        self.rot_ccw = IconButton(
            "rotate-ccw", tr("Rotate left"), button_size=28, size=15
        )
        self.rot_cw = IconButton(
            "rotate-cw", tr("Rotate right"), button_size=28, size=15
        )
        tool_row.addWidget(self.zoom_out)
        tool_row.addWidget(self.zoom_label)
        tool_row.addWidget(self.zoom_in)
        tool_row.addWidget(self.fit)
        tool_row.addWidget(self.rot_ccw)
        tool_row.addWidget(self.rot_cw)
        header_layout.addLayout(tool_row)
        root.addWidget(header)
        root.addWidget(HLine())

        self.view = PhotoView(allow_swipe=False)
        self.view.zoom_changed.connect(
            lambda value: self.zoom_label.setText(f"{value}%")
        )
        root.addWidget(self.view, 1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 10, 12, 12)
        footer_layout.setSpacing(10)
        hint = QLabel(tr("Winner → Favorites, the other → Trash"))
        hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.3pt;")
        footer_layout.addWidget(hint, 1)
        self.skip_button = QPushButton(tr("Skip"))
        self.skip_button.setProperty("role", "ghost")
        self.skip_button.setMinimumHeight(34)
        self.skip_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_button.setToolTip(
            tr(
                "Skip {letter} and replace it with the next photo (Shift+←/→)",
                letter=letter,
            )
        )
        self.skip_button.clicked.connect(self.skip)
        footer_layout.addWidget(self.skip_button)
        self.choose_button = QPushButton(tr("Choose {letter}", letter=letter))
        self.choose_button.setProperty("role", "primary")
        self.choose_button.setMinimumHeight(34)
        self.choose_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_button.setIcon(icon("check", "#1b1507", 15))
        self.choose_button.setIconSize(QSize(15, 15))
        self.choose_button.clicked.connect(self.choose)
        footer_layout.addWidget(self.choose_button)
        root.addWidget(footer)

        self.zoom_out.clicked.connect(self.view.zoom_out)
        self.zoom_in.clicked.connect(self.view.zoom_in)
        self.fit.clicked.connect(self.view.fit_to_window)
        self.rot_ccw.clicked.connect(self.view.rotate_ccw)
        self.rot_cw.clicked.connect(self.view.rotate_cw)

    def set_group(
        self,
        group: PhotoGroup,
        shortcut_hint: str = "",
        variant_index: int | None = None,
        full_raw: bool = False,
    ) -> None:
        self.group = group
        self.variant_index = (
            group.primary_index if variant_index is None else variant_index
        )
        self.full_raw = full_raw
        self.name_label.setText(group.display_name)
        meta = group.meta
        bits = []
        if meta.camera:
            bits.append(meta.camera)
        if meta.date_label:
            bits.append(meta.date_label)
        if meta.dimensions:
            bits.append(meta.dimensions)
        self.meta_label.setText(" · ".join(bits) or group.primary.name)
        self.meta_label.setToolTip(group.primary.path)
        self.format_badge.setText(group.format_summary)
        self.choose_button.setText(tr("Choose {letter}", letter=self.letter))
        if shortcut_hint:
            self.choose_button.setToolTip(
                tr("Choose {letter} ({hint})", letter=self.letter, hint=shortcut_hint)
            )

    def set_busy(self, busy: bool, can_skip: bool = True) -> None:
        self.choose_button.setEnabled(not busy and self.group is not None)
        self.skip_button.setEnabled(not busy and self.group is not None and can_skip)


class ComparePage(QWidget):
    exit_requested = Signal()
    choose_requested = Signal(str)  # left / right / both / skip
    skip_side_requested = Signal(str)
    view_mode_cycle_requested = Signal()
    undo_requested = Signal()
    settings_requested = Signal()
    help_requested = Signal()
    error_occurred = Signal(str)

    def __init__(
        self, preview_service, config: Config, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PageRoot")
        self.preview_service = preview_service
        self.config = config
        self.session: SortSession | None = None
        self.pair: tuple[PhotoGroup, PhotoGroup] | None = None
        self.pair_number = 1
        self._busy = False
        self._workers: set[PreviewWorker] = set()
        self._pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._loaded_pair_ids: tuple[str, str] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        back = IconButton(
            "chevron-left",
            tr("Back to review (Esc)"),
            button_size=38,
            size=21,
        )
        back.clicked.connect(self.exit_requested)
        header.addWidget(back)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_row = QHBoxLayout()
        title_row.setSpacing(9)
        title = QLabel(tr("Compare"))
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 15pt; font-weight: 750;")
        self.pair_badge = Badge("")
        self.pair_badge.setStyleSheet(
            f"color: {theme.BLUE}; background: {theme.BLUE_DARK}; border: 1px solid #2c405e;"
            "border-radius: 8px; padding: 2px 8px; font-size: 8.2pt;"
        )
        title_row.addWidget(title)
        title_row.addWidget(self.pair_badge)
        title_row.addStretch(1)
        subtitle = QLabel(
            tr(
                "Two shots side by side. Choose the better one — the other goes to trash."
            )
        )
        subtitle.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.8pt;")
        title_box.addLayout(title_row)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        self.view_mode_button = QPushButton("")
        self.view_mode_button.setProperty("role", "chip")
        self.view_mode_button.setIcon(icon("layers", theme.TEXT_MUTED, 14))
        self.view_mode_button.setIconSize(QSize(14, 14))
        self.view_mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_mode_button.clicked.connect(self.view_mode_cycle_requested)
        header.addWidget(self.view_mode_button)
        self.undo_button = QPushButton(tr("Undo"))
        self.undo_button.setProperty("role", "subtle")
        self.undo_button.setIcon(icon("undo", theme.TEXT_MUTED, 16))
        self.undo_button.setIconSize(QSize(16, 16))
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self.undo_requested)
        header.addWidget(self.undo_button)
        help_button = IconButton("help", tr("Help"), button_size=36, size=18)
        help_button.clicked.connect(self.help_requested)
        settings_button = IconButton(
            "settings", tr("Settings"), button_size=36, size=18
        )
        settings_button.clicked.connect(self.settings_requested)
        exit_button = QPushButton(tr("Exit"))
        exit_button.setProperty("role", "ghost")
        exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_button.clicked.connect(self.exit_requested)
        header.addWidget(help_button)
        header.addWidget(settings_button)
        header.addWidget(exit_button)
        root.addLayout(header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        pairs_widget = QWidget()
        pairs_layout = QVBoxLayout(pairs_widget)
        pairs_layout.setContentsMargins(0, 0, 0, 0)
        pairs_layout.setSpacing(10)
        panes = QHBoxLayout()
        panes.setSpacing(10)
        self.left = ComparePane("A", theme.BLUE)
        self.right = ComparePane("B", theme.VIOLET)
        self.left.choose.connect(lambda: self._choose("left"))
        self.right.choose.connect(lambda: self._choose("right"))
        self.left.skip.connect(lambda: self._skip_side("left"))
        self.right.skip.connect(lambda: self._skip_side("right"))
        panes.addWidget(self.left, 1)
        panes.addWidget(self.right, 1)
        pairs_layout.addLayout(panes, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(9)
        hint = QLabel(
            tr(
                "← A — left   ·   → D — right   ·   Shift+←/→ — skip one   ·   Space — both   ·   S — skip pair   ·   Esc — exit"
            )
        )
        hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.4pt;")
        bottom.addWidget(hint)
        bottom.addStretch(1)
        self.both_button = QPushButton(tr("Keep both as favorites"))
        self.both_button.setProperty("role", "ghost")
        self.both_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.both_button.clicked.connect(lambda: self._choose("both"))
        self.skip_button = QPushButton(tr("Skip this pair"))
        self.skip_button.setProperty("role", "subtle")
        self.skip_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_button.clicked.connect(lambda: self._choose("skip"))
        bottom.addWidget(self.both_button)
        bottom.addWidget(self.skip_button)
        pairs_layout.addLayout(bottom)
        self.stack.addWidget(pairs_widget)
        self.pairs_widget = pairs_widget

        self.done_widget = QWidget()
        done_layout = QVBoxLayout(self.done_widget)
        done_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        done_card = QFrame()
        done_card.setProperty("role", "panel")
        done_card.setMaximumWidth(560)
        done_card.setStyleSheet(
            f'QFrame[role="panel"] {{ background: {theme.PANEL}; border: 1px solid {theme.BORDER};'
            "border-radius: 18px; }"
        )
        card_layout = QVBoxLayout(done_card)
        card_layout.setContentsMargins(38, 34, 38, 30)
        card_layout.setSpacing(10)
        done_icon = QLabel()
        done_icon.setFixedSize(64, 64)
        done_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        done_icon.setStyleSheet(
            f"background: {theme.ACCENT_DARK}; border: 1px solid #5a4821; border-radius: 32px;"
        )
        done_icon.setPixmap(icon("compare", theme.ACCENT, 28).pixmap(28, 28))
        card_layout.addWidget(done_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        self.done_title = QLabel(tr("Comparison complete"))
        self.done_title.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 20pt; font-weight: 750;"
        )
        self.done_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.done_title)
        self.done_text = QLabel("")
        self.done_text.setWordWrap(True)
        self.done_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_text.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10pt;")
        card_layout.addWidget(self.done_text)
        done_button = QPushButton(tr("Back to review"))
        done_button.setProperty("role", "primary")
        done_button.setCursor(Qt.CursorShape.PointingHandCursor)
        done_button.setIcon(icon("chevron-left", "#1b1507", 16))
        done_button.setIconSize(QSize(16, 16))
        done_button.clicked.connect(self.exit_requested)
        card_layout.addWidget(done_button, 0, Qt.AlignmentFlag.AlignHCenter)
        done_layout.addWidget(done_card)
        self.stack.addWidget(self.done_widget)

    # ------------------------------------------------------------------
    def set_config(self, config: Config) -> None:
        self.config = config
        self._update_view_mode_button()

    def set_session(self, session: SortSession) -> None:
        self.session = session
        self.pair_number = 1
        self._loaded_pair_ids = None
        self._pixmap_cache.clear()
        self.reload()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        can_skip = bool(self.session and self.session.mode == "first")
        self.left.set_busy(busy, can_skip)
        self.right.set_busy(busy, can_skip)
        self.both_button.setEnabled(not busy)
        self.skip_button.setEnabled(not busy and can_skip)
        self.view_mode_button.setEnabled(not busy)
        self.undo_button.setEnabled(
            not busy and bool(self.session and self.session.can_undo)
        )
        self.setCursor(
            Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor
        )

    def reload(self, force: bool = False) -> None:
        session = self.session
        if not session:
            return
        self._update_view_mode_button()
        if force:
            self._loaded_pair_ids = None
        self.undo_button.setEnabled(session.can_undo and not self._busy)
        if len(session.queue) < 2:
            self.stack.setCurrentWidget(self.done_widget)
            self.pair = None
            self._update_view_mode_button()
            if session.queue:
                self.done_title.setText(tr("One photo left"))
                self.done_text.setText(
                    tr(
                        "Comparison needs two shots. Return to review to decide on the last photo."
                    )
                )
            elif session.deferred_count:
                self.done_title.setText(tr("No more pairs"))
                self.done_text.setText(
                    tr(
                        "Deferred: {count}. You can review them in the second round.",
                        count=session.deferred_count,
                    )
                )
            else:
                self.done_title.setText(tr("Comparison complete"))
                self.done_text.setText(
                    tr("All pairs in this queue have been reviewed.")
                )
            return
        self.stack.setCurrentWidget(self.pairs_widget)
        self.pair = (session.queue[0], session.queue[1])
        self.pair_badge.setText(tr("Pair {number}", number=self.pair_number))
        self._update_view_mode_button()
        for pane, group, side, hint in (
            (self.left, self.pair[0], 0, "← / A"),
            (self.right, self.pair[1], 1, "→ / D"),
        ):
            index, full_raw, _ = self._resolve(group)
            pane.set_group(group, hint, index, full_raw)
        pair_ids = (self.pair[0].id, self.pair[1].id)
        if pair_ids != self._loaded_pair_ids:
            self._loaded_pair_ids = pair_ids
            self.left.view.clear()
            self.right.view.clear()
            self.left.view.set_loading(tr("Loading…"))
            self.right.view.set_loading(tr("Loading…"))
            self._load_pane(self.left, self.pair[0], 0)
            self._load_pane(self.right, self.pair[1], 1)
        self.set_busy(self._busy)

    def _resolve(self, group: PhotoGroup) -> tuple[int, bool, str]:
        return resolve_view(group, self.config.behavior.raw_view_mode)

    def _load_pane(self, pane: ComparePane, group: PhotoGroup, side: int) -> None:
        variant_index, full_raw, _ = self._resolve(group)
        key = f"{group.id}:{variant_index}:{int(full_raw)}"
        cached = self._pixmap_cache.get(key)
        if cached is not None and not cached.isNull():
            pane.view.set_pixmap(cached)
            pane.view.set_allow_swipe(False)
            self._pixmap_cache.move_to_end(key)
            return
        worker = PreviewWorker(
            self.preview_service,
            group,
            variant_index,
            max_side=1800,
            full_raw=full_raw,
        )
        self._workers.add(worker)
        worker.signals.finished.connect(
            lambda gid, vi, path, error, width, height, full, w=worker, p=pane, s=side: (
                self._pane_ready(w, p, s, gid, vi, path, error, full)
            )
        )
        QThreadPool.globalInstance().start(worker)

    def _pane_ready(
        self,
        worker: PreviewWorker,
        pane: ComparePane,
        side: int,
        group_id: str,
        variant_index: int,
        path: str,
        error: str,
        full_raw: bool,
    ) -> None:
        self._workers.discard(worker)
        if not self.pair:
            return
        expected = self.pair[side]
        pane_expected = self.left if side == 0 else self.right
        if (
            expected.id != group_id
            or pane_expected.variant_index != variant_index
            or pane_expected.full_raw != full_raw
        ):
            return
        if error or not path:
            pane.view.set_error(tr("Could not open the photo"))
            self.error_occurred.emit(f"{expected.primary.name}: {error}")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            pane.view.set_error(tr("Could not load preview"))
            return
        key = f"{group_id}:{variant_index}:{int(full_raw)}"
        self._pixmap_cache[key] = pixmap
        self._pixmap_cache.move_to_end(key)
        while len(self._pixmap_cache) > 6:
            self._pixmap_cache.popitem(last=False)
        pane.view.set_pixmap(pixmap)
        pane.view.set_allow_swipe(False)

    # ------------------------------------------------------------------
    def _choose(self, choice: str) -> None:
        if self._busy or not self.pair:
            return
        self.choose_requested.emit(choice)

    def _skip_side(self, side: str) -> None:
        if self._busy or not self.pair:
            return
        if not self.session or self.session.mode != "first":
            return
        self.skip_side_requested.emit(side)

    def replace_side(self, side: str, new_group: PhotoGroup) -> None:
        if not self.pair:
            return
        left, right = self.pair
        if side == "left":
            self.pair = (new_group, right)
            pane = self.left
            hint = "← / A"
        else:
            self.pair = (left, new_group)
            pane = self.right
            hint = "→ / D"
        index, full_raw, _ = self._resolve(new_group)
        pane.set_group(new_group, hint, index, full_raw)
        self._update_view_mode_button()
        pane.view.clear()
        pane.view.set_loading(tr("Loading…"))
        self._loaded_pair_ids = (self.pair[0].id, self.pair[1].id)
        self._load_pane(pane, new_group, 0 if side == "left" else 1)
        self.set_busy(self._busy)

    def _update_view_mode_button(self) -> None:
        if not hasattr(self, "view_mode_button"):
            return
        if not self.pair or not any(group.has_raw for group in self.pair):
            self.view_mode_button.hide()
            return
        self.view_mode_button.show()
        mode = getattr(self.config.behavior, "raw_view_mode", "jpeg")
        labels = {
            "jpeg": tr("JPEG"),
            "thumbnail": tr("RAW thumbnail"),
            "full": tr("RAW full"),
        }
        self.view_mode_button.setText(labels.get(mode, mode))
        bindings = self.config.shortcuts.get("toggleRaw", [])
        tip = tr(
            "Display mode: {mode}. Click to cycle between JPEG, RAW thumbnail and full RAW.",
            mode=labels.get(mode, mode),
        )
        if bindings:
            tip += f" ({display_combo(bindings[0])})"
        self.view_mode_button.setToolTip(tip)

    def pair_groups(self) -> tuple[PhotoGroup, PhotoGroup] | None:
        return self.pair

    def advance(self) -> None:
        self.pair_number += 1
        self._loaded_pair_ids = None
        self.reload()
