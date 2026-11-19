from __future__ import annotations

from pathlib import Path

import PIL
import PySide6
import rawpy
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import (
    CONTROLLER_ACTIONS,
    DEFAULT_CONTROLLER_MAPPINGS,
    DEFAULT_SHORTCUTS,
    SHORTCUT_ACTIONS,
    Config,
    Destinations,
    Source,
    canonical_combo,
)
from ..controller import ControllerManager, button_choices, button_label
from ..paths import config_file, data_dir
from ..shortcuts import ACTION_HINTS, ACTION_LABELS, display_combo, event_to_combo
from ..utils import format_bytes, reveal_in_file_manager
from . import theme
from .widgets import HLine


def _title(text: str, subtitle: str = "") -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    label = QLabel(text)
    label.setProperty("role", "h3")
    layout.addWidget(label)
    if subtitle:
        hint = QLabel(subtitle)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        layout.addWidget(hint)
    return widget


def _panel() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("role", "subtle")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    return frame, layout


class KeyCaptureDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новая комбинация")
        self.setModal(True)
        self.setMinimumWidth(430)
        self.combo: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(11)
        title = QLabel("Нажмите комбинацию клавиш")
        title.setProperty("role", "h2")
        layout.addWidget(title)
        hint = QLabel("Например, →, D, Shift + R или Ctrl + 1. Esc — отмена.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9.2pt;")
        layout.addWidget(hint)
        self.preview = QLabel("…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(62)
        self.preview.setStyleSheet(
            f"background: {theme.BG_DEEP}; border: 1px dashed {theme.BORDER_LIGHT};"
            f"border-radius: 11px; color: {theme.ACCENT}; font-size: 18pt; font-weight: 700;"
        )
        layout.addWidget(self.preview)
        cancel = QPushButton("Отмена")
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        layout.addLayout(row)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        if event.isAutoRepeat():
            return
        combo = event_to_combo(event)
        if not combo:
            return
        try:
            combo = canonical_combo(combo)
        except ValueError:
            return
        self.combo = combo
        self.preview.setText(display_combo(combo))
        self.accept()


class ShortcutRow(QWidget):
    def __init__(
        self,
        action: str,
        config: Config,
        conflict_check,
        changed,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.action = action
        self.config = config
        self.conflict_check = conflict_check
        self.changed = changed
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(9)
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        label = QLabel(ACTION_LABELS[action])
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt; font-weight: 600;")
        hint = QLabel(ACTION_HINTS.get(action, ""))
        hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.2pt;")
        text.addWidget(label)
        text.addWidget(hint)
        layout.addLayout(text, 1)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(5)
        layout.addLayout(self.chips)
        self.add_button = QPushButton("＋")
        self.add_button.setProperty("role", "chip")
        self.add_button.setFixedWidth(30)
        self.add_button.setToolTip("Добавить комбинацию")
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self._add)
        layout.addWidget(self.add_button)
        self._rebuild()

    def _rebuild(self) -> None:
        while self.chips.count():
            item = self.chips.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)
                item.widget().deleteLater()
        bindings = self.config.shortcuts.get(self.action, [])
        if not bindings:
            empty = QLabel("не назначено")
            empty.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.6pt; font-style: italic;"
            )
            self.chips.addWidget(empty)
        for combo in bindings:
            chip = QPushButton(f"{display_combo(combo)}  ×")
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip("Удалить комбинацию")
            chip.clicked.connect(lambda _=False, c=combo: self._remove(c))
            self.chips.addWidget(chip)
        self.add_button.setEnabled(len(bindings) < 4)

    def _add(self) -> None:
        dialog = KeyCaptureDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.combo:
            return
        combo = dialog.combo
        owner = self.conflict_check(combo, self.action)
        if owner is not None:
            QMessageBox.warning(
                self,
                "Комбинация уже занята",
                f"{display_combo(combo)} уже используется для действия «{ACTION_LABELS[owner]}».",
            )
            return
        self.config.shortcuts.setdefault(self.action, []).append(combo)
        self._rebuild()
        self.changed()

    def _remove(self, combo: str) -> None:
        bindings = self.config.shortcuts.get(self.action, [])
        if combo in bindings:
            bindings.remove(combo)
        self._rebuild()
        self.changed()


class ControllerRow(QWidget):
    def __init__(
        self, action: str, config: Config, changed, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.action = action
        self.config = config
        self.changed = changed
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(9)
        label = QLabel(ACTION_LABELS[action])
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt; font-weight: 600;")
        layout.addWidget(label, 1)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(5)
        layout.addLayout(self.chips)
        self.add_button = QPushButton("＋")
        self.add_button.setProperty("role", "chip")
        self.add_button.setFixedWidth(30)
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setToolTip("Назначить кнопку")
        self.add_button.clicked.connect(self._menu)
        layout.addWidget(self.add_button)
        self._rebuild()

    def _rebuild(self) -> None:
        while self.chips.count():
            item = self.chips.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)
                item.widget().deleteLater()
        values = self.config.controller.mappings.get(self.action, [])
        if not values:
            empty = QLabel("не назначено")
            empty.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.6pt; font-style: italic;"
            )
            self.chips.addWidget(empty)
        for index in values:
            chip = QPushButton(f"{button_label(index)}  ×")
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip("Удалить кнопку")
            chip.clicked.connect(lambda _=False, i=index: self._remove(i))
            self.chips.addWidget(chip)
        self.add_button.setEnabled(len(values) < 4)

    def _menu(self) -> None:
        menu = QMenu(self)
        used = set(self.config.controller.mappings.get(self.action, []))
        all_used = {
            value
            for action in CONTROLLER_ACTIONS
            for value in self.config.controller.mappings.get(action, [])
        }
        any_added = False
        for index, name in button_choices():
            if index in used:
                continue
            action = menu.addAction(name)
            if index in all_used:
                action.setToolTip("Уже используется другим действием")
            action.triggered.connect(lambda _=False, i=index: self._add(i))
            any_added = True
        if not any_added:
            action = menu.addAction("Все кнопки уже назначены")
            action.setEnabled(False)
        menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft()))

    def _add(self, index: int) -> None:
        for other in CONTROLLER_ACTIONS:
            if other != self.action and index in self.config.controller.mappings.get(
                other, []
            ):
                QMessageBox.warning(
                    self,
                    "Кнопка уже занята",
                    f"{button_label(index)} уже назначена для действия «{ACTION_LABELS[other]}».",
                )
                return
        values = self.config.controller.mappings.setdefault(self.action, [])
        if index not in values:
            values.append(index)
            values.sort()
        self._rebuild()
        self.changed()

    def _remove(self, index: int) -> None:
        values = self.config.controller.mappings.get(self.action, [])
        if index in values:
            values.remove(index)
        self._rebuild()
        self.changed()


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        *,
        preview_service,
        controller: ControllerManager | None,
        current_source: Source | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки — PhotoSwipe")
        self.setModal(True)
        self.resize(880, 700)
        self.setMinimumSize(760, 600)
        self._original = config
        self.config = Config.from_dict(config.to_dict())
        self.preview_service = preview_service
        self.controller = controller
        self.current_source = current_source
        self._saved = False

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(13)
        header = QHBoxLayout()
        title = QLabel("Настройки")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 19pt; font-weight: 750;")
        header.addWidget(title)
        header.addStretch(1)
        version = QLabel(f"PhotoSwipe {__version__}")
        version.setProperty("role", "micro")
        header.addWidget(version)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_folders_tab(), "Папки")
        self.tabs.addTab(self._build_behavior_tab(), "Поведение")
        self.tabs.addTab(self._build_shortcuts_tab(), "Клавиши")
        self.tabs.addTab(self._build_controller_tab(), "Контроллер")
        self.tabs.addTab(self._build_about_tab(), "RAW и кэш")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.setSpacing(9)
        footer.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Сохранить")
        save.setProperty("role", "primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setMinimumWidth(110)
        save.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)

    # ------------------------------------------------------------------
    def _scrollable(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _build_folders_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)
        layout.addWidget(
            _title(
                "Куда перемещать фотографии",
                "Файлы перемещаются сразу после решения. Папки создаются автоматически.",
            )
        )
        panel, body = _panel()
        dest = self.config.destinations
        self.mode_beside = QRadioButton("Рядом с каждой папкой-источником")
        self.mode_custom = QRadioButton("В общую папку")
        self.mode_beside.setChecked(dest.mode == "beside")
        self.mode_custom.setChecked(dest.mode == "custom")
        body.addWidget(self.mode_beside)
        self.beside_fields = QWidget()
        beside_row = QHBoxLayout(self.beside_fields)
        beside_row.setContentsMargins(25, 0, 0, 0)
        beside_label = QLabel("Имя подпапки:")
        beside_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9.2pt;")
        self.beside_edit = QLineEdit(dest.beside_dir_name)
        self.beside_edit.setPlaceholderText("_PhotoSwipe")
        beside_row.addWidget(beside_label)
        beside_row.addWidget(self.beside_edit, 1)
        body.addWidget(self.beside_fields)

        body.addWidget(self.mode_custom)
        self.custom_fields = QWidget()
        custom_layout = QVBoxLayout(self.custom_fields)
        custom_layout.setContentsMargins(25, 0, 0, 0)
        custom_layout.setSpacing(7)
        custom_row = QHBoxLayout()
        self.custom_root_edit = QLineEdit(dest.custom_root)
        self.custom_browse_button = QPushButton("Выбрать…")
        self.custom_browse_button.setProperty("role", "subtle")
        self.custom_browse_button.clicked.connect(self._choose_custom_root)
        custom_row.addWidget(self.custom_root_edit, 1)
        custom_row.addWidget(self.custom_browse_button)
        custom_layout.addLayout(custom_row)
        self.add_source_name = QCheckBox("Добавлять подпапку с именем источника")
        self.add_source_name.setChecked(dest.add_source_name)
        custom_layout.addWidget(self.add_source_name)
        body.addWidget(self.custom_fields)
        self.path_preview = QLabel("")
        self.path_preview.setWordWrap(True)
        self.path_preview.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 8.6pt; background: {theme.BG_DEEP};"
            f"border: 1px solid {theme.BORDER}; border-radius: 7px; padding: 7px 9px;"
        )
        body.addWidget(self.path_preview)
        layout.addWidget(panel)

        layout.addWidget(
            _title("Названия папок", "Можно переименовать под свои задачи.")
        )
        panel2, body2 = _panel()
        grid = QHBoxLayout()
        for label_text, attr in (
            ("Избранное", "favorite"),
            ("Корзина", "trash"),
            ("Может быть", "maybe"),
        ):
            column = QVBoxLayout()
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
            edit = QLineEdit(getattr(dest, attr))
            setattr(self, f"{attr}_edit", edit)
            column.addWidget(label)
            column.addWidget(edit)
            grid.addLayout(column, 1)
        body2.addLayout(grid)
        hint = QLabel(
            "Второй раунд не перемещает файлы: отложенные фотографии остаются на месте, "
            "пока вы не примете окончательное решение."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.7pt;")
        body2.addWidget(hint)
        layout.addWidget(panel2)
        layout.addStretch(1)

        self.mode_beside.toggled.connect(self._sync_destination_state)
        self.mode_custom.toggled.connect(self._sync_destination_state)
        self.add_source_name.toggled.connect(self._sync_destination_state)
        for edit in (
            self.beside_edit,
            self.custom_root_edit,
            self.favorite_edit,
            self.trash_edit,
            self.maybe_edit,
        ):
            edit.textChanged.connect(self._sync_destination_state)
        self._sync_destination_state()
        return self._scrollable(page)

    def _sync_destination_state(self) -> None:
        custom = self.mode_custom.isChecked()
        self.beside_fields.setVisible(not custom)
        self.custom_fields.setVisible(custom)
        source = self.current_source
        source_name = source.name if source else "Фото"
        custom_root = Path(
            self.custom_root_edit.text().strip()
            or Path.home() / "Pictures" / "PhotoSwipe"
        )
        if custom:
            base = (
                custom_root / source_name
                if self.add_source_name.isChecked()
                else custom_root
            )
        else:
            base = (Path(source.path) if source else Path("/фото")) / (
                self.beside_edit.text().strip() or "_PhotoSwipe"
            )
        self.path_preview.setText(
            f"Пример: {base / (self.favorite_edit.text().strip() or 'Избранное')}  ·  "
            f"{base / (self.trash_edit.text().strip() or 'Корзина')}  ·  "
            f"{base / (self.maybe_edit.text().strip() or 'Может быть')}"
        )

    def _choose_custom_root(self) -> None:
        initial = self.custom_root_edit.text().strip() or str(Path.home() / "Pictures")
        folder = QFileDialog.getExistingDirectory(
            self, "Куда складывать результаты", initial
        )
        if folder:
            self.custom_root_edit.setText(folder)

    def _build_behavior_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)
        layout.addWidget(
            _title(
                "Сортировка",
                "Порядок и подпапки применяются при следующем открытии папки.",
            )
        )
        panel, body = _panel()
        row = QHBoxLayout()
        label = QLabel("Порядок фотографий")
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt;")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("По дате съёмки", "date")
        self.sort_combo.addItem("По имени файла", "name")
        self.sort_combo.setCurrentIndex(
            1 if self.config.behavior.sort_by == "name" else 0
        )
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.sort_combo)
        body.addLayout(row)
        body.addWidget(HLine())
        self.recursive_check = QCheckBox("По умолчанию сканировать подпапки")
        self.recursive_check.setChecked(self.config.behavior.recursive_default)
        body.addWidget(self.recursive_check)
        layout.addWidget(panel)

        layout.addWidget(_title("RAW", "На качество и скорость просмотра."))
        panel2, body2 = _panel()
        self.full_raw_check = QCheckBox("Полностью декодировать RAW при просмотре")
        self.full_raw_check.setChecked(self.config.behavior.raw_full_decode)
        body2.addWidget(self.full_raw_check)
        hint = QLabel(
            "По умолчанию PhotoSwipe показывает встроенное JPEG-превью камеры — это быстро и достаточно "
            "для отбора. Полное декодирование через LibRaw даёт больше деталей, но заметно медленнее."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.8pt;")
        body2.addWidget(hint)
        layout.addWidget(panel2)
        layout.addStretch(1)
        return self._scrollable(page)

    def _build_shortcuts_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(
            _title(
                "Горячие клавиши",
                "Нажмите ＋, затем нужную комбинацию. До четырёх вариантов на действие.",
            ),
            1,
        )
        reset = QPushButton("Сбросить все")
        reset.setProperty("role", "subtle")
        reset.clicked.connect(self._reset_shortcuts)
        header.addWidget(reset, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)
        panel, body = _panel()
        self.shortcut_rows: list[ShortcutRow] = []
        for index, action in enumerate(SHORTCUT_ACTIONS):
            row = ShortcutRow(
                action,
                self.config,
                self._shortcut_conflict,
                self._sync_destination_state,
            )
            body.addWidget(row)
            self.shortcut_rows.append(row)
            if index < len(SHORTCUT_ACTIONS) - 1:
                body.addWidget(HLine())
        layout.addWidget(panel)
        note = QLabel(
            "Стрелки работают на любой раскладке, включая русскую. В режиме сравнения ←/→ выбирают "
            "левую или правую фотографию, Пробел оставляет обе, S откладывает пару, Esc выходит."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.7pt;")
        layout.addWidget(note)
        layout.addStretch(1)
        return self._scrollable(page)

    def _shortcut_conflict(self, combo: str, action: str) -> str | None:
        for other, bindings in self.config.shortcuts.items():
            if other != action and combo in bindings:
                return other
        return None

    def _reset_shortcuts(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Сбросить горячие клавиши",
                "Вернуть стандартные комбинации для всех действий?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.config.shortcuts = {
            key: list(value) for key, value in DEFAULT_SHORTCUTS.items()
        }
        for row in self.shortcut_rows:
            row._rebuild()

    def _build_controller_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)
        layout.addWidget(
            _title(
                "Геймпад",
                "Подключите контроллер до запуска. В сравнении также работают D-pad ←/→, A и B.",
            )
        )
        panel, body = _panel()
        top = QHBoxLayout()
        self.controller_enabled = QCheckBox("Включить управление с контроллера")
        self.controller_enabled.setChecked(self.config.controller.enabled)
        top.addWidget(self.controller_enabled)
        top.addStretch(1)
        self.controller_status = QLabel("")
        top.addWidget(self.controller_status)
        body.addLayout(top)
        if self.controller is not None and self.controller.is_connected:
            self.controller_status.setText(f"Подключён: {self.controller.name}")
            self.controller_status.setStyleSheet(
                f"color: {theme.GREEN}; font-size: 8.8pt;"
            )
        elif self.controller is not None and self.controller.available:
            self.controller_status.setText("Контроллер не найден")
            self.controller_status.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.8pt;"
            )
        else:
            self.controller_status.setText("Модуль pygame недоступен")
            self.controller_status.setStyleSheet(
                f"color: {theme.AMBER}; font-size: 8.8pt;"
            )

        dead_row = QHBoxLayout()
        dead_label = QLabel("Мёртвая зона стиков")
        dead_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        self.deadzone_slider = QSlider(Qt.Orientation.Horizontal)
        self.deadzone_slider.setRange(0, 80)
        self.deadzone_slider.setValue(int(self.config.controller.deadzone * 100))
        self.deadzone_value = QLabel(f"{self.deadzone_slider.value()}%")
        self.deadzone_value.setFixedWidth(38)
        self.deadzone_value.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 8.8pt;"
        )
        self.deadzone_slider.valueChanged.connect(
            lambda v: self.deadzone_value.setText(f"{v}%")
        )
        dead_row.addWidget(dead_label)
        dead_row.addWidget(self.deadzone_slider, 1)
        dead_row.addWidget(self.deadzone_value)
        body.addLayout(dead_row)
        self.vibration_check = QCheckBox("Виброотклик при решении")
        self.vibration_check.setChecked(self.config.controller.vibration)
        body.addWidget(self.vibration_check)
        layout.addWidget(panel)

        layout.addWidget(
            _title("Кнопки", "Нажмите ＋, чтобы выбрать кнопку для действия.")
        )
        panel2, body2 = _panel()
        self.controller_rows: list[ControllerRow] = []
        for index, action in enumerate(CONTROLLER_ACTIONS):
            row = ControllerRow(action, self.config, lambda: None)
            body2.addWidget(row)
            self.controller_rows.append(row)
            if index < len(CONTROLLER_ACTIONS) - 1:
                body2.addWidget(HLine())
        layout.addWidget(panel2)
        reset = QPushButton("Сбросить раскладку контроллера")
        reset.setProperty("role", "subtle")
        reset.clicked.connect(self._reset_controller)
        layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        self.controller_enabled.toggled.connect(self._sync_controller_state)
        self._sync_controller_state()
        if self.controller is not None:
            self.controller.status_changed.connect(self._controller_status_changed)
        return self._scrollable(page)

    def _controller_status_changed(self, name: str) -> None:
        if name:
            self.controller_status.setText(f"Подключён: {name}")
            self.controller_status.setStyleSheet(
                f"color: {theme.GREEN}; font-size: 8.8pt;"
            )
        else:
            self.controller_status.setText("Контроллер не найден")
            self.controller_status.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.8pt;"
            )

    def _sync_controller_state(self) -> None:
        enabled = self.controller_enabled.isChecked()
        self.deadzone_slider.setEnabled(enabled)
        self.vibration_check.setEnabled(enabled)
        for row in getattr(self, "controller_rows", []):
            row.setEnabled(enabled)

    def _reset_controller(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Сбросить контроллер",
                "Вернуть стандартную раскладку кнопок?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.config.controller.mappings = {
            key: list(value) for key, value in DEFAULT_CONTROLLER_MAPPINGS.items()
        }
        for row in self.controller_rows:
            row._rebuild()

    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)
        layout.addWidget(
            _title("RAW-движок", "Sony ARW, DNG и другие форматы через LibRaw.")
        )
        panel, body = _panel()
        self.cache_size_label = QLabel("")
        self.cache_size_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 9pt;"
        )
        for text in (
            f"rawpy / LibRaw: {rawpy.__version__}",
            f"Pillow: {PIL.__version__}",
            f"PySide6 / Qt: {PySide6.__version__}",
            f"Данные: {data_dir()}",
            f"Конфиг: {config_file()}",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.9pt;")
            body.addWidget(label)
        body.addWidget(HLine())
        row = QHBoxLayout()
        row.addWidget(self.cache_size_label, 1)
        clear = QPushButton("Очистить кэш превью")
        clear.setProperty("role", "subtle")
        clear.clicked.connect(self._clear_cache)
        open_data = QPushButton("Открыть папку данных")
        open_data.setProperty("role", "subtle")
        open_data.clicked.connect(lambda: reveal_in_file_manager(data_dir()))
        row.addWidget(clear)
        row.addWidget(open_data)
        body.addLayout(row)
        self._update_cache_size()
        layout.addWidget(panel)

        layout.addWidget(_title("Поддерживаемые форматы"))
        panel2, body2 = _panel()
        formats = QLabel(
            "RAW: Sony ARW / SRF / SR2, Adobe DNG, Canon CR2 / CR3, Nikon NEF / NRW, "
            "Fujifilm RAF, Olympus ORF, Panasonic RW2, Pentax PEF, Samsung SRW, "
            "Hasselblad 3FR, Leica RWL и другие форматы LibRaw.\n"
            "Изображения: JPEG, PNG, TIFF, WebP, BMP, GIF, AVIF, HEIC/HEIF."
        )
        formats.setWordWrap(True)
        formats.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
        body2.addWidget(formats)
        layout.addWidget(panel2)
        layout.addStretch(1)
        return self._scrollable(page)

    def _update_cache_size(self) -> None:
        try:
            size = self.preview_service.cache_size()
        except Exception:
            size = 0
        self.cache_size_label.setText(f"Кэш превью: {format_bytes(size)}")

    def _clear_cache(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Очистить кэш",
                "Удалить созданные превью? При следующем просмотре они будут созданы заново.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.preview_service.clear_cache()
        self._update_cache_size()

    # ------------------------------------------------------------------
    def _save(self) -> None:
        dest = Destinations(
            mode="custom" if self.mode_custom.isChecked() else "beside",
            beside_dir_name=self.beside_edit.text().strip() or "_PhotoSwipe",
            custom_root=self.custom_root_edit.text().strip()
            or str(Path.home() / "Pictures" / "PhotoSwipe"),
            add_source_name=self.add_source_name.isChecked(),
            favorite=self.favorite_edit.text().strip(),
            trash=self.trash_edit.text().strip(),
            maybe=self.maybe_edit.text().strip(),
        )
        try:
            for raw_value in (
                dest.favorite,
                dest.trash,
                dest.maybe,
                dest.beside_dir_name,
            ):
                if (
                    not raw_value
                    or raw_value in {".", ".."}
                    or any(ch in raw_value for ch in '<>:"/\\|?*')
                ):
                    raise ValueError(
                        "Имена папок не должны содержать спецсимволы и быть пустыми"
                    )
            if dest.mode == "custom" and not dest.custom_root:
                raise ValueError("Выберите общую папку для результатов")
            dest.validate()
        except ValueError as error:
            QMessageBox.warning(self, "Проверьте настройки", str(error))
            return

        self.config.destinations = Destinations.from_dict(dest.to_dict())
        self.config.behavior.sort_by = (
            "name" if self.sort_combo.currentIndex() == 1 else "date"
        )
        self.config.behavior.recursive_default = self.recursive_check.isChecked()
        self.config.behavior.raw_full_decode = self.full_raw_check.isChecked()
        self.config.controller.enabled = self.controller_enabled.isChecked()
        self.config.controller.deadzone = self.deadzone_slider.value() / 100.0
        self.config.controller.vibration = self.vibration_check.isChecked()
        self._saved = True
        self.accept()

    @property
    def result_config(self) -> Config:
        return self.config
