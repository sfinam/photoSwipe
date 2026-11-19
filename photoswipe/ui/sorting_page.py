from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..models import PhotoGroup
from ..session import SortSession
from ..shortcuts import display_combo
from ..utils import format_bytes, format_count
from . import theme
from .icons import icon
from .photo_view import PhotoView
from .widgets import (
    Badge,
    DecisionButton,
    ElidedLabel,
    HLine,
    IconButton,
    StatPill,
)
from .workers import PreviewWorker


def _clear_layout(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


class CompletionStat(QFrame):
    def __init__(
        self,
        icon_name: str,
        color: str,
        value: int,
        label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {theme.BG_DEEP}; border: 1px solid {theme.BORDER}; border-radius: 12px; }}"
            "QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(7)
        badge = QLabel()
        badge.setPixmap(icon(icon_name, color, 15).pixmap(15, 15))
        top.addWidget(badge)
        value_label = QLabel(str(value))
        value_label.setStyleSheet(f"color: {color}; font-size: 16pt; font-weight: 750;")
        top.addWidget(value_label)
        top.addStretch(1)
        layout.addLayout(top)
        text = QLabel(label)
        text.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.8pt;")
        layout.addWidget(text)


class SortingPage(QWidget):
    back_requested = Signal()
    settings_requested = Signal()
    help_requested = Signal()
    compare_requested = Signal()
    decision_requested = Signal(str)
    undo_requested = Signal()
    next_round_requested = Signal()
    first_round_requested = Signal()
    reveal_requested = Signal(str)
    fullscreen_requested = Signal()
    error_occurred = Signal(str)

    def __init__(
        self, preview_service, config: Config, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PageRoot")
        self.preview_service = preview_service
        self.config = config
        self.session: SortSession | None = None
        self.current_id: str | None = None
        self.variant_index = 0
        self.variant_choices: dict[str, int] = {}
        self.rotations: dict[str, int] = {}
        self._pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._workers: set[PreviewWorker] = set()
        self._prefetch_workers: set[PreviewWorker] = set()
        self._busy = False
        self._completion_signature: tuple | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 16)
        root.setSpacing(12)

        # ---- top header ---------------------------------------------------
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(7)
        top_row = QHBoxLayout()
        top_row.setSpacing(11)

        self.back_button = IconButton(
            "chevron-left", "К библиотеке (Esc)", button_size=38, size=21
        )
        self.back_button.clicked.connect(self.back_requested)
        top_row.addWidget(self.back_button)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        self.folder_name = QLabel("")
        self.folder_name.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 14.5pt; font-weight: 700;"
        )
        self.round_badge = Badge("")
        self.round_badge.setStyleSheet(
            f"color: {theme.ACCENT}; background: {theme.ACCENT_DARK}; border: 1px solid #55451f;"
            "border-radius: 8px; padding: 2px 7px; font-size: 8.2pt; font-weight: 600;"
        )
        self.round_badge.hide()
        name_row.addWidget(self.folder_name)
        name_row.addWidget(self.round_badge)
        name_row.addStretch(1)
        self.folder_path = ElidedLabel("")
        self.folder_path.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.8pt;")
        title_box.addLayout(name_row)
        title_box.addWidget(self.folder_path)
        top_row.addLayout(title_box, 1)

        self.favorite_pill = StatPill("heart", theme.GREEN, 0, "Избранное")
        self.trash_pill = StatPill("trash", theme.RED, 0, "Корзина")
        self.maybe_pill = StatPill("clock", theme.AMBER, 0, "Может быть")
        self.deferred_pill = StatPill("clock", theme.BLUE, 0, "Второй раунд")
        top_row.addWidget(self.favorite_pill)
        top_row.addWidget(self.trash_pill)
        top_row.addWidget(self.maybe_pill)
        top_row.addWidget(self.deferred_pill)

        self.undo_button = QPushButton("Отменить")
        self.undo_button.setProperty("role", "subtle")
        self.undo_button.setIcon(icon("undo", theme.TEXT_MUTED, 16))
        self.undo_button.setIconSize(QSize(16, 16))
        self.undo_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_button.clicked.connect(self.undo_requested)
        top_row.addWidget(self.undo_button)

        self.compare_button = QPushButton("Сравнить")
        self.compare_button.setProperty("role", "subtle")
        self.compare_button.setIcon(icon("compare", theme.BLUE, 16))
        self.compare_button.setIconSize(QSize(16, 16))
        self.compare_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compare_button.clicked.connect(self.compare_requested)
        top_row.addWidget(self.compare_button)

        self.help_button = IconButton("help", "Справка", button_size=36, size=18)
        self.help_button.clicked.connect(self.help_requested)
        self.settings_button = IconButton(
            "settings", "Настройки", button_size=36, size=18
        )
        self.settings_button.clicked.connect(self.settings_requested)
        self.fullscreen_button = IconButton(
            "maximize", "Полный экран (F)", button_size=36, size=18
        )
        self.fullscreen_button.clicked.connect(self.fullscreen_requested)
        top_row.addWidget(self.help_button)
        top_row.addWidget(self.settings_button)
        top_row.addWidget(self.fullscreen_button)
        header_layout.addLayout(top_row)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(50, 0, 0, 0)
        progress_row.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setFixedWidth(300)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        progress_row.addWidget(self.progress)
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.7pt;")
        progress_row.addWidget(self.progress_label)
        self.deferred_label = QLabel("")
        self.deferred_label.setStyleSheet(f"color: {theme.BLUE}; font-size: 8.7pt;")
        progress_row.addWidget(self.deferred_label)
        progress_row.addStretch(1)
        self.controller_label = QLabel("")
        self.controller_label.setStyleSheet(
            f"color: {theme.GREEN}; font-size: 8.7pt; background: {theme.GREEN_DARK};"
            "border: 1px solid #2f4d3c; border-radius: 7px; padding: 2px 8px;"
        )
        self.controller_label.setToolTip("")
        self.controller_label.hide()
        progress_row.addWidget(self.controller_label)
        header_layout.addLayout(progress_row)
        root.addWidget(header)

        # ---- stack: photo stage / completion -----------------------------
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.stage = QFrame()
        self.stage.setProperty("role", "panel")
        self.stage.setStyleSheet(
            f'QFrame[role="panel"] {{ background: {theme.PANEL}; border: 1px solid {theme.BORDER};'
            " border-radius: 16px; }"
        )
        stage_layout = QVBoxLayout(self.stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(0)

        stage_header = QWidget()
        stage_header.setStyleSheet("background: transparent;")
        stage_header_layout = QHBoxLayout(stage_header)
        stage_header_layout.setContentsMargins(20, 13, 14, 11)
        stage_header_layout.setSpacing(12)
        info_box = QVBoxLayout()
        info_box.setContentsMargins(0, 0, 0, 0)
        info_box.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(9)
        self.photo_name = QLabel("")
        self.photo_name.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 15pt; font-weight: 700;"
        )
        self.format_badge = Badge("")
        self.loading_badge = Badge("Загрузка…")
        self.loading_badge.setStyleSheet(
            f"color: {theme.BLUE}; background: {theme.BLUE_DARK}; border: 1px solid #2b405e;"
            "border-radius: 8px; padding: 2px 8px; font-size: 8.2pt;"
        )
        self.loading_badge.hide()
        title_row.addWidget(self.photo_name)
        title_row.addWidget(self.format_badge)
        title_row.addWidget(self.loading_badge)
        title_row.addStretch(1)
        info_box.addLayout(title_row)
        self.photo_meta = ElidedLabel("")
        self.photo_meta.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        info_box.addWidget(self.photo_meta)
        self.variant_row = QHBoxLayout()
        self.variant_row.setContentsMargins(0, 2, 0, 0)
        self.variant_row.setSpacing(5)
        info_box.addLayout(self.variant_row)
        stage_header_layout.addLayout(info_box, 1)

        tools = QHBoxLayout()
        tools.setSpacing(2)
        self.zoom_out_button = IconButton(
            "zoom-out", "Уменьшить", button_size=32, size=17
        )
        self.zoom_out_button.clicked.connect(lambda: self.view.zoom_out())
        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(46)
        self.zoom_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.8pt;")
        self.zoom_in_button = IconButton(
            "zoom-in", "Увеличить", button_size=32, size=17
        )
        self.zoom_in_button.clicked.connect(lambda: self.view.zoom_in())
        self.fit_button = IconButton(
            "minimize", "Вписать в окно (0)", button_size=32, size=17
        )
        self.fit_button.clicked.connect(lambda: self.view.fit_to_window())
        self.rotate_ccw_button = IconButton(
            "rotate-ccw", "Повернуть влево", button_size=32, size=17
        )
        self.rotate_ccw_button.clicked.connect(lambda: self.view.rotate_ccw())
        self.rotate_cw_button = IconButton(
            "rotate-cw", "Повернуть вправо", button_size=32, size=17
        )
        self.rotate_cw_button.clicked.connect(lambda: self.view.rotate_cw())
        tools.addWidget(self.zoom_out_button)
        tools.addWidget(self.zoom_label)
        tools.addWidget(self.zoom_in_button)
        tools.addWidget(self.fit_button)
        tools.addSpacing(4)
        tools.addWidget(self.rotate_ccw_button)
        tools.addWidget(self.rotate_cw_button)
        stage_header_layout.addLayout(tools)
        stage_layout.addWidget(stage_header)
        stage_layout.addWidget(HLine())

        self.view = PhotoView(allow_swipe=True)
        self.view.swipe.connect(self._on_swipe)
        self.view.zoom_changed.connect(
            lambda value: self.zoom_label.setText(f"{value}%")
        )
        self.view.rotation_changed.connect(self._remember_rotation)
        stage_layout.addWidget(self.view, 1)
        self.stack.addWidget(self.stage)

        self.completion_scroll = QScrollArea()
        self.completion_scroll.setWidgetResizable(True)
        self.completion_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.completion_host = QWidget()
        self.completion_host.setObjectName("PageRoot")
        self.completion_layout = QVBoxLayout(self.completion_host)
        self.completion_layout.setContentsMargins(24, 24, 24, 24)
        self.completion_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.completion_scroll.setWidget(self.completion_host)
        self.stack.addWidget(self.completion_scroll)

        # ---- decision bar -------------------------------------------------
        self.action_bar = QWidget()
        bar = QHBoxLayout(self.action_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(10)
        self.trash_button = DecisionButton("trash", "В корзину", "trash", theme.RED)
        self.maybe_button = DecisionButton("maybe", "Может быть", "clock", theme.AMBER)
        self.round2_button = DecisionButton(
            "round2", "Второй раунд", "clock", theme.BLUE
        )
        self.favorite_button = DecisionButton(
            "favorite", "В избранное", "heart", theme.GREEN
        )
        for button in (
            self.trash_button,
            self.maybe_button,
            self.round2_button,
            self.favorite_button,
        ):
            button.clicked.connect(
                lambda _=False, b=button: self._request_decision(b.verdict)
            )
            bar.addWidget(button, 1)
        root.addWidget(self.action_bar)
        self._update_shortcut_badges()

    # ------------------------------------------------------------------
    def set_config(self, config: Config) -> None:
        self.config = config
        self._update_shortcut_badges()

    def set_controller(self, name: str) -> None:
        if name:
            short = name if len(name) <= 32 else name[:30] + "…"
            self.controller_label.setText(f"Геймпад · {short}")
            self.controller_label.setToolTip(name)
            self.controller_label.show()
        else:
            self.controller_label.hide()

    def _update_shortcut_badges(self) -> None:
        for verdict, button in (
            ("trash", self.trash_button),
            ("maybe", self.maybe_button),
            ("round2", self.round2_button),
            ("favorite", self.favorite_button),
        ):
            bindings = self.config.shortcuts.get(verdict, [])
            button.set_shortcut(display_combo(bindings[0]) if bindings else "")
            button.setToolTip(" / ".join(display_combo(b) for b in bindings))
        undo = self.config.shortcuts.get("undo", [])
        self.undo_button.setToolTip(
            "Отменить последнее решение"
            + (f" ({display_combo(undo[0])})" if undo else "")
        )
        compare = self.config.shortcuts.get("compare", [])
        self.compare_button.setToolTip(
            "Сравнить две фотографии"
            + (f" ({display_combo(compare[0])})" if compare else "")
        )
        full = self.config.shortcuts.get("fullscreen", [])
        self.fullscreen_button.setToolTip(
            "Полный экран" + (f" ({display_combo(full[0])})" if full else "")
        )

    # ------------------------------------------------------------------
    def set_session(self, session: SortSession) -> None:
        self.session = session
        self.current_id = None
        self.variant_choices = {}
        self.rotations = {}
        self._completion_signature = None
        self.folder_name.setText(session.source.name)
        self.folder_path.setText(session.source.path)
        self.folder_path.setToolTip(session.source.path)
        self.round_badge.setVisible(session.mode == "second")
        if session.mode == "second":
            self.round_badge.setText(f"РАУНД {session.round_number}")
        self.refresh(force=True)

    def clear(self) -> None:
        self.session = None
        self.current_id = None
        self.view.clear()
        self.stack.setCurrentWidget(self.stage)
        self.action_bar.show()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        can_decide = not busy and self._current_group() is not None
        for button in (self.trash_button, self.maybe_button, self.favorite_button):
            button.setEnabled(can_decide)
        self.round2_button.setEnabled(
            can_decide and bool(self.session and self.session.mode == "first")
        )
        if self.session and self.session.mode == "second":
            self.round2_button.set_hint("Второй раунд уже идёт")
        else:
            self.round2_button.set_hint("нажмите или свайпните")
        self.undo_button.setEnabled(
            not busy and bool(self.session and self.session.can_undo)
        )
        self.compare_button.setEnabled(
            not busy and bool(self.session and len(self.session.queue) >= 2)
        )
        for widget in self.findChildren(QPushButton):
            if widget.property("role") == "chip":
                widget.setEnabled(not busy)
        self.view.set_allow_swipe(not busy)
        self.setCursor(
            Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor
        )
        if not busy:
            self.view.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    def refresh(self, force: bool = False) -> None:
        session = self.session
        if session is None:
            return
        self._update_header()
        current = session.queue[0] if session.queue else None
        if current is None:
            self.show_completion()
            return
        self.stack.setCurrentWidget(self.stage)
        self.action_bar.setVisible(True)
        choice = self.variant_choices.get(current.id, current.primary_index)
        choice = max(0, min(choice, len(current.variants) - 1))
        group_changed = current.id != self.current_id
        variant_changed = choice != self.variant_index
        if group_changed:
            self.current_id = current.id
            self.variant_index = choice
            self._build_variant_chips(current)
            self._update_photo_info(current)
            self.view.clear()
            self.view.set_loading(f"Открываю {current.variants[choice].label}…")
            self._load_preview(current, choice)
        elif variant_changed or force:
            self.variant_index = choice
            self._build_variant_chips(current)
            self._update_photo_info(current)
            if variant_changed or not self.view.has_image:
                self._load_preview(current, choice)
        self.set_busy(self._busy)

    def _update_header(self) -> None:
        session = self.session
        if not session:
            return
        self.folder_name.setText(session.source.name)
        self.folder_path.setText(session.source.path)
        stats = session.stats
        self.favorite_pill.set_count(stats.get("favorite", 0))
        self.trash_pill.set_count(stats.get("trash", 0))
        self.maybe_pill.set_count(stats.get("maybe", 0))
        self.deferred_pill.set_count(session.deferred_count)
        self.deferred_pill.setVisible(session.deferred_count > 0)
        self.undo_button.setEnabled(session.can_undo and not self._busy)
        self.compare_button.setEnabled(len(session.queue) >= 2 and not self._busy)
        total = session.total
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(min(session.processed, total) if total else 0)
        self.progress_label.setText(f"{session.processed} из {total}" if total else "")
        if session.mode == "second":
            self.round_badge.setVisible(True)
            self.round_badge.setText(f"РАУНД {session.round_number}")
            self.deferred_label.setText(
                f"Осталось в раунде: {len(session.queue)}" if session.queue else ""
            )
        else:
            self.round_badge.hide()
            self.deferred_label.setText(
                f"На второй раунд: {session.deferred_count}"
                if session.deferred_count
                else ""
            )

    def _build_variant_chips(self, group: PhotoGroup) -> None:
        _clear_layout(self.variant_row)
        for index, variant in enumerate(group.variants):
            label = f"{variant.label} · {format_bytes(variant.size)}"
            chip = QPushButton(label)
            chip.setProperty("role", "chip")
            chip.setCheckable(True)
            chip.setChecked(index == self.variant_index)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(variant.name)
            chip.clicked.connect(lambda _=False, i=index: self._select_variant(i))
            self.variant_row.addWidget(chip)
        self.variant_row.addStretch(1)
        self.format_badge.setText(group.format_summary)

    def _update_photo_info(self, group: PhotoGroup) -> None:
        self.photo_name.setText(group.display_name)
        meta = group.meta
        bits = []
        if meta.camera:
            bits.append(meta.camera)
        if meta.date_label:
            bits.append(meta.date_label)
        if meta.dimensions:
            bits.append(meta.dimensions)
        if meta.subtitle and meta.camera:
            extra = [part for part in meta.subtitle.split(" · ") if part != meta.camera]
            bits.extend(extra)
        if not bits:
            bits.append(group.primary.name)
        self.photo_meta.setText(" · ".join(bits))
        self.photo_meta.setToolTip(group.primary.path)

    def _select_variant(self, index: int) -> None:
        group = self._current_group()
        if not group or self._busy:
            return
        if index == self.variant_index:
            return
        self.variant_choices[group.id] = index
        self.variant_index = index
        self._build_variant_chips(group)
        self._update_photo_info(group)
        self._load_preview(group, index)
        self.refresh()

    # ------------------------------------------------------------------
    def _current_group(self) -> PhotoGroup | None:
        if not self.session or not self.session.queue:
            return None
        return self.session.queue[0]

    def _load_preview(self, group: PhotoGroup, variant_index: int) -> None:
        cache_key = f"{group.id}:{variant_index}"
        cached = self._pixmap_cache.get(cache_key)
        if cached is not None and not cached.isNull():
            self.view.set_pixmap(cached)
            self._apply_rotation(group)
            self._pixmap_cache.move_to_end(cache_key)
            self.loading_badge.hide()
            self.set_busy(self._busy)
            return
        self.loading_badge.show()
        worker = PreviewWorker(
            self.preview_service,
            group,
            variant_index,
            max_side=2400,
            full_raw=self.config.behavior.raw_full_decode,
        )
        self._workers.add(worker)
        worker.signals.finished.connect(self._preview_ready)
        QThreadPool.globalInstance().start(worker)

    def _preview_ready(
        self,
        group_id: str,
        variant_index: int,
        path: str,
        error: str,
        width: int,
        height: int,
    ) -> None:
        sender = self.sender()
        for worker in list(self._workers):
            if worker.signals is sender:
                self._workers.discard(worker)
                break
        group = self._current_group()
        if not group or group.id != group_id or self.variant_index != variant_index:
            return
        self.loading_badge.hide()
        if error or not path:
            self.view.set_error(
                f"Не удалось открыть {group.variants[variant_index].label}"
            )
            self.error_occurred.emit(f"{group.primary.name}: {error}")
            self.set_busy(self._busy)
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.view.set_error("Не удалось загрузить превью")
            self.error_occurred.emit(
                f"Не удалось загрузить превью {group.primary.name}"
            )
            self.set_busy(self._busy)
            return
        key = f"{group.id}:{variant_index}"
        self._pixmap_cache[key] = pixmap
        self._pixmap_cache.move_to_end(key)
        while len(self._pixmap_cache) > 8:
            self._pixmap_cache.popitem(last=False)
        self.view.set_pixmap(pixmap)
        self._apply_rotation(group)
        self.loading_badge.hide()
        self.set_busy(self._busy)
        self._prefetch_next()

    def _apply_rotation(self, group: PhotoGroup) -> None:
        degrees = self.rotations.get(group.id, 0)
        if degrees:
            self.view.set_rotation_degrees(degrees)

    def _remember_rotation(self, degrees: int) -> None:
        group = self._current_group()
        if group:
            self.rotations[group.id] = int(degrees) % 360

    def _prefetch_next(self) -> None:
        if not self.session:
            return
        queue = self.session.queue
        if len(queue) < 2:
            return
        next_group = queue[1]
        next_index = self.variant_choices.get(next_group.id, next_group.primary_index)
        worker = PreviewWorker(
            self.preview_service,
            next_group,
            next_index,
            max_side=2400,
            full_raw=self.config.behavior.raw_full_decode,
        )
        self._prefetch_workers.add(worker)
        worker.signals.finished.connect(
            lambda *args, w=worker: self._prefetch_workers.discard(w)
        )
        QThreadPool.globalInstance().start(worker)

    # ------------------------------------------------------------------
    def _on_swipe(self, direction: str) -> None:
        if self._busy:
            return
        mapping = {
            "left": "trash",
            "right": "favorite",
            "up": "round2",
            "down": "maybe",
        }
        verdict = mapping.get(direction)
        if verdict:
            self.decision_requested.emit(verdict)

    def _request_decision(self, verdict: str) -> None:
        if self._busy or not self._current_group():
            return
        self.decision_requested.emit(verdict)

    def trigger_action(self, action: str) -> None:
        if action in {"favorite", "trash", "maybe", "round2"}:
            self._request_decision(action)
        elif action == "undo":
            self.undo_requested.emit()
        elif action == "compare":
            self.compare_requested.emit()
        elif action == "zoomIn":
            self.view.zoom_in()
        elif action == "zoomOut":
            self.view.zoom_out()
        elif action == "rotateCw":
            self.view.rotate_cw()
        elif action == "rotateCcw":
            self.view.rotate_ccw()
        elif action == "resetView":
            self.view.reset_view()

    # ------------------------------------------------------------------
    def show_completion(self) -> None:
        session = self.session
        if not session:
            return
        signature = (
            session.mode,
            session.processed,
            session.deferred_count,
            session.round_number,
            session.scanned_files,
            len(session.first_round_pending),
            session.can_undo,
        )
        if (
            signature == self._completion_signature
            and self.stack.currentWidget() is self.completion_scroll
        ):
            return
        self._completion_signature = signature
        self.action_bar.hide()
        self.stack.setCurrentWidget(self.completion_scroll)
        _clear_layout(self.completion_layout)

        has_photos = (
            session.scanned_files > 0
            or session.processed > 0
            or session.deferred_count > 0
        )
        if not has_photos:
            title = "В папке нет фотографий"
            subtitle = (
                "PhotoSwipe поддерживает JPEG, PNG, TIFF, WebP и RAW: Sony ARW, DNG, "
                "Canon CR2/CR3, Nikon NEF, Fujifilm RAF и другие форматы LibRaw."
            )
            icon_name = "image"
            accent = theme.TEXT_MUTED
        elif (
            session.mode == "second"
            and not session.queue
            and session.first_round_pending
        ):
            title = "Второй раунд пройден"
            subtitle = (
                f"В папке появились новые фотографии: {len(session.first_round_pending)}. "
                "Можно вернуться к первому раунду и разобрать их."
            )
            icon_name = "refresh"
            accent = theme.BLUE
        elif session.mode == "first" and session.deferred_count:
            title = "Первый раунд пройден"
            subtitle = (
                f"Отложено {format_count(session.deferred_count, 'фотография', 'фотографии', 'фотографий')}. "
                "Второй раунд покажет только их — решение можно принять спокойнее."
            )
            icon_name = "clock"
            accent = theme.BLUE
        else:
            title = "Готово"
            subtitle = (
                "Все фотографии в этой папке разобраны. Файлы уже лежат по папкам."
            )
            icon_name = "check"
            accent = theme.GREEN

        panel = QFrame()
        panel.setProperty("role", "panel")
        panel.setMaximumWidth(780)
        panel.setStyleSheet(
            f'QFrame[role="panel"] {{ background: {theme.PANEL}; border: 1px solid {theme.BORDER};'
            " border-radius: 18px; }"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(34, 28, 34, 26)
        panel_layout.setSpacing(13)
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        badge = QLabel()
        badge.setFixedSize(72, 72)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = QColor(accent)
        badge.setStyleSheet(
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 20);"
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 62);"
            "border-radius: 36px;"
        )
        badge.setPixmap(icon(icon_name, accent, 32).pixmap(32, 32))
        panel_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 22pt; font-weight: 750;"
        )
        panel_layout.addWidget(title_label)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setMaximumWidth(620)
        subtitle_label.setMinimumHeight(44)
        subtitle_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10.2pt;")
        panel_layout.addWidget(subtitle_label, 0, Qt.AlignmentFlag.AlignHCenter)

        if has_photos:
            stats_row = QHBoxLayout()
            stats_row.setSpacing(8)
            stats_row.setContentsMargins(0, 8, 0, 4)
            stats_row.addWidget(
                CompletionStat(
                    "heart", theme.GREEN, session.stats["favorite"], "Избранное"
                )
            )
            stats_row.addWidget(
                CompletionStat("trash", theme.RED, session.stats["trash"], "Корзина")
            )
            stats_row.addWidget(
                CompletionStat(
                    "clock", theme.AMBER, session.stats["maybe"], "Может быть"
                )
            )
            if session.deferred_count or session.first_round_pending:
                stats_row.addWidget(
                    CompletionStat(
                        "clock", theme.BLUE, session.deferred_count, "Второй раунд"
                    )
                )
            panel_layout.addLayout(stats_row)

        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addStretch(1)
        if has_photos and session.mode == "first" and session.deferred_count:
            if session.stats["favorite"]:
                secondary = QPushButton("Открыть «Избранное»")
                secondary.setProperty("role", "ghost")
                secondary.setCursor(Qt.CursorShape.PointingHandCursor)
                secondary.clicked.connect(
                    lambda: self.reveal_requested.emit("favorite")
                )
                actions.addWidget(secondary)
            primary = QPushButton(f"Второй раунд · {session.deferred_count}")
            primary.setProperty("role", "primary")
            primary.setIcon(icon("arrow-right", "#1b1507", 16))
            primary.setIconSize(QSize(16, 16))
            primary.setCursor(Qt.CursorShape.PointingHandCursor)
            primary.clicked.connect(self.next_round_requested)
            actions.addWidget(primary)
        elif has_photos and session.mode == "second" and session.first_round_pending:
            if session.stats["favorite"]:
                secondary = QPushButton("Открыть «Избранное»")
                secondary.setProperty("role", "ghost")
                secondary.setCursor(Qt.CursorShape.PointingHandCursor)
                secondary.clicked.connect(
                    lambda: self.reveal_requested.emit("favorite")
                )
                actions.addWidget(secondary)
            primary = QPushButton(
                f"К первому раунду · {len(session.first_round_pending)}"
            )
            primary.setProperty("role", "primary")
            primary.setIcon(icon("arrow-right", "#1b1507", 16))
            primary.setIconSize(QSize(16, 16))
            primary.setCursor(Qt.CursorShape.PointingHandCursor)
            primary.clicked.connect(self.first_round_requested)
            actions.addWidget(primary)
        else:
            if has_photos and session.stats["favorite"]:
                secondary = QPushButton("Открыть «Избранное»")
                secondary.setProperty("role", "ghost")
                secondary.setCursor(Qt.CursorShape.PointingHandCursor)
                secondary.clicked.connect(
                    lambda: self.reveal_requested.emit("favorite")
                )
                actions.addWidget(secondary)
            primary = QPushButton("К библиотеке")
            primary.setProperty("role", "primary")
            primary.setIcon(icon("chevron-left", "#1b1507", 16))
            primary.setIconSize(QSize(16, 16))
            primary.setCursor(Qt.CursorShape.PointingHandCursor)
            primary.clicked.connect(self.back_requested)
            actions.addWidget(primary)
        actions.addStretch(1)
        panel_layout.addLayout(actions)
        if has_photos:
            destination = session.destinations.get("favorite")
            if destination:
                path_label = QLabel(f"Избранное: {destination}")
                path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                path_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.4pt;")
                path_label.setWordWrap(True)
                panel_layout.addWidget(path_label)
        self.completion_layout.addWidget(panel)
