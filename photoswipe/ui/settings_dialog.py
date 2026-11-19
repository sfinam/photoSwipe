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
from ..i18n import LANGUAGES, default_folder_names, tr
from ..paths import config_file, data_dir
from ..shortcuts import action_hint, action_label, display_combo, event_to_combo
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
        self.setWindowTitle(tr("New shortcut"))
        self.setModal(True)
        self.setMinimumWidth(430)
        self.combo: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(11)
        title = QLabel(tr("Press a key combination"))
        title.setProperty("role", "h2")
        layout.addWidget(title)
        hint = QLabel(tr("For example, →, D, Shift + R or Ctrl + 1. Esc cancels."))
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
        cancel = QPushButton(tr("Cancel"))
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
        label = QLabel(action_label(action))
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt; font-weight: 600;")
        hint = QLabel(action_hint(action))
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
        self.add_button.setToolTip(tr("Add shortcut"))
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
            empty = QLabel(tr("not assigned"))
            empty.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.6pt; font-style: italic;"
            )
            self.chips.addWidget(empty)
        for combo in bindings:
            chip = QPushButton(f"{display_combo(combo)}  ×")
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(tr("Remove shortcut"))
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
                tr("Shortcut already in use"),
                tr(
                    "{shortcut} is already used for “{action}”.",
                    shortcut=display_combo(combo),
                    action=action_label(owner),
                ),
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
        label = QLabel(action_label(action))
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt; font-weight: 600;")
        layout.addWidget(label, 1)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(5)
        layout.addLayout(self.chips)
        self.add_button = QPushButton("＋")
        self.add_button.setProperty("role", "chip")
        self.add_button.setFixedWidth(30)
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setToolTip(tr("Assign a button"))
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
            empty = QLabel(tr("not assigned"))
            empty.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.6pt; font-style: italic;"
            )
            self.chips.addWidget(empty)
        for index in values:
            chip = QPushButton(f"{button_label(index)}  ×")
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(tr("Remove button"))
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
                action.setToolTip(tr("Already used by another action"))
            action.triggered.connect(lambda _=False, i=index: self._add(i))
            any_added = True
        if not any_added:
            action = menu.addAction(tr("All buttons are already assigned"))
            action.setEnabled(False)
        menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft()))

    def _add(self, index: int) -> None:
        for other in CONTROLLER_ACTIONS:
            if other != self.action and index in self.config.controller.mappings.get(
                other, []
            ):
                QMessageBox.warning(
                    self,
                    tr("Button already in use"),
                    tr(
                        "{button} is already assigned to “{action}”.",
                        button=button_label(index),
                        action=action_label(other),
                    ),
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
        self.setWindowTitle(tr("Settings — PhotoSwipe"))
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
        title = QLabel(tr("Settings"))
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 19pt; font-weight: 750;")
        header.addWidget(title)
        header.addStretch(1)
        version = QLabel(f"PhotoSwipe {__version__}")
        version.setProperty("role", "micro")
        header.addWidget(version)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), tr("General"))
        self.tabs.addTab(self._build_folders_tab(), tr("Folders"))
        self.tabs.addTab(self._build_behavior_tab(), tr("Behavior"))
        self.tabs.addTab(self._build_shortcuts_tab(), tr("Shortcuts"))
        self.tabs.addTab(self._build_controller_tab(), tr("Controller"))
        self.tabs.addTab(self._build_about_tab(), tr("RAW and cache"))
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.setSpacing(9)
        footer.addStretch(1)
        cancel = QPushButton(tr("Cancel"))
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr("Save"))
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

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)
        layout.addWidget(
            _title(
                tr("Language"),
                tr("Choose the interface language. The window reopens after saving."),
            )
        )
        panel, body = _panel()
        row = QHBoxLayout()
        label = QLabel(tr("Interface language"))
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt;")
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        index = self.language_combo.findData(self.config.language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.language_combo)
        body.addLayout(row)
        note = QLabel(
            tr(
                "Folder names are stored as they are. Changing the language does not rename existing destination folders; edit them in the Folders tab."
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 8.8pt;")
        body.addWidget(note)
        layout.addWidget(panel)
        layout.addStretch(1)
        return self._scrollable(page)

    def _build_folders_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(13)
        layout.addWidget(
            _title(
                tr("Where to move photos"),
                tr(
                    "Files are moved immediately after a decision. Folders are created automatically."
                ),
            )
        )
        panel, body = _panel()
        dest = self.config.destinations
        self.mode_beside = QRadioButton(tr("Next to each source folder"))
        self.mode_custom = QRadioButton(tr("Into a shared folder"))
        self.mode_beside.setChecked(dest.mode == "beside")
        self.mode_custom.setChecked(dest.mode == "custom")
        body.addWidget(self.mode_beside)
        self.beside_fields = QWidget()
        beside_row = QHBoxLayout(self.beside_fields)
        beside_row.setContentsMargins(25, 0, 0, 0)
        beside_label = QLabel(tr("Subfolder name:"))
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
        self.custom_browse_button = QPushButton(tr("Choose…"))
        self.custom_browse_button.setProperty("role", "subtle")
        self.custom_browse_button.clicked.connect(self._choose_custom_root)
        custom_row.addWidget(self.custom_root_edit, 1)
        custom_row.addWidget(self.custom_browse_button)
        custom_layout.addLayout(custom_row)
        self.add_source_name = QCheckBox(tr("Add a subfolder with the source name"))
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
            _title(
                tr("Folder names"),
                tr("You can rename them to suit your workflow."),
            )
        )
        panel2, body2 = _panel()
        grid = QHBoxLayout()
        for label_text, attr in (
            (tr("Favorites"), "favorite"),
            (tr("Trash"), "trash"),
            (tr("Maybe"), "maybe"),
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
            tr(
                "The second round does not move files: deferred photos stay in place until you make a final decision."
            )
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
        source_name = source.name if source else tr("Photo")
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
            base = (Path(source.path) if source else Path("/photo")) / (
                self.beside_edit.text().strip() or "_PhotoSwipe"
            )
        defaults = default_folder_names(self.config.language)
        self.path_preview.setText(
            tr(
                "Example: {favorite}  ·  {trash}  ·  {maybe}",
                favorite=base
                / (self.favorite_edit.text().strip() or defaults["favorite"]),
                trash=base / (self.trash_edit.text().strip() or defaults["trash"]),
                maybe=base / (self.maybe_edit.text().strip() or defaults["maybe"]),
            )
        )

    def _choose_custom_root(self) -> None:
        initial = self.custom_root_edit.text().strip() or str(Path.home() / "Pictures")
        folder = QFileDialog.getExistingDirectory(
            self, tr("Choose destination folder"), initial
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
                tr("Sorting"),
                tr(
                    "Order and subfolder scanning are applied the next time a folder is opened."
                ),
            )
        )
        panel, body = _panel()
        row = QHBoxLayout()
        label = QLabel(tr("Photo order"))
        label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt;")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem(tr("By capture date"), "date")
        self.sort_combo.addItem(tr("By file name"), "name")
        self.sort_combo.setCurrentIndex(
            1 if self.config.behavior.sort_by == "name" else 0
        )
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(self.sort_combo)
        body.addLayout(row)
        body.addWidget(HLine())
        self.recursive_check = QCheckBox(tr("Scan subfolders by default"))
        self.recursive_check.setChecked(self.config.behavior.recursive_default)
        body.addWidget(self.recursive_check)
        layout.addWidget(panel)

        layout.addWidget(_title(tr("RAW"), tr("Affects viewing quality and speed.")))
        panel2, body2 = _panel()
        raw_row = QHBoxLayout()
        raw_label = QLabel(tr("RAW display"))
        raw_label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt;")
        self.raw_view_combo = QComboBox()
        self.raw_view_combo.addItem(tr("JPEG from the RAW+JPEG pair"), "jpeg")
        self.raw_view_combo.addItem(tr("RAW preview (embedded thumbnail)"), "thumbnail")
        self.raw_view_combo.addItem(tr("Full RAW decode (LibRaw)"), "full")
        index = self.raw_view_combo.findData(self.config.behavior.raw_view_mode)
        self.raw_view_combo.setCurrentIndex(index if index >= 0 else 0)
        raw_row.addWidget(raw_label)
        raw_row.addStretch(1)
        raw_row.addWidget(self.raw_view_combo)
        body2.addLayout(raw_row)
        hint = QLabel(
            tr(
                "JPEG uses the paired JPEG when available and the embedded RAW preview otherwise. RAW thumbnail always uses the camera preview. Full decode gives more detail but is noticeably slower."
            )
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
                tr("Shortcuts"),
                tr("Press +, then the combination. Up to four variants per action."),
            ),
            1,
        )
        reset = QPushButton(tr("Reset all"))
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
            tr(
                "Arrow keys work in any layout, including Russian. In comparison mode ←/→ choose the left or right photo, Space keeps both, S defers the pair and Esc exits."
            )
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
                tr("Reset shortcuts"),
                tr("Restore the default shortcuts for all actions?"),
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
                tr("Gamepad"),
                tr(
                    "Connect a controller before starting. In comparison mode, D-pad ←/→, A and B also work."
                ),
            )
        )
        panel, body = _panel()
        top = QHBoxLayout()
        self.controller_enabled = QCheckBox(tr("Enable controller input"))
        self.controller_enabled.setChecked(self.config.controller.enabled)
        top.addWidget(self.controller_enabled)
        top.addStretch(1)
        self.controller_status = QLabel("")
        top.addWidget(self.controller_status)
        body.addLayout(top)
        if self.controller is not None and self.controller.is_connected:
            self.controller_status.setText(
                tr("Connected: {name}", name=self.controller.name)
            )
            self.controller_status.setStyleSheet(
                f"color: {theme.GREEN}; font-size: 8.8pt;"
            )
        elif self.controller is not None and self.controller.available:
            self.controller_status.setText(tr("Controller not found"))
            self.controller_status.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 8.8pt;"
            )
        else:
            self.controller_status.setText(tr("pygame module unavailable"))
            self.controller_status.setStyleSheet(
                f"color: {theme.AMBER}; font-size: 8.8pt;"
            )

        dead_row = QHBoxLayout()
        dead_label = QLabel(tr("Stick dead zone"))
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
        self.vibration_check = QCheckBox(tr("Vibration feedback on decisions"))
        self.vibration_check.setChecked(self.config.controller.vibration)
        body.addWidget(self.vibration_check)
        layout.addWidget(panel)

        layout.addWidget(
            _title(
                tr("Buttons"),
                tr("Press + to choose a button for an action."),
            )
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
        reset = QPushButton(tr("Reset controller layout"))
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
            self.controller_status.setText(tr("Connected: {name}", name=name))
            self.controller_status.setStyleSheet(
                f"color: {theme.GREEN}; font-size: 8.8pt;"
            )
        else:
            self.controller_status.setText(tr("Controller not found"))
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
                tr("Reset controller"),
                tr("Restore the default button layout?"),
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
            _title(
                tr("RAW engine"),
                tr("Sony ARW, DNG and other formats via LibRaw."),
            )
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
            tr("Data: {path}", path=data_dir()),
            tr("Config: {path}", path=config_file()),
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.9pt;")
            body.addWidget(label)
        body.addWidget(HLine())
        row = QHBoxLayout()
        row.addWidget(self.cache_size_label, 1)
        clear = QPushButton(tr("Clear preview cache"))
        clear.setProperty("role", "subtle")
        clear.clicked.connect(self._clear_cache)
        open_data = QPushButton(tr("Open data folder"))
        open_data.setProperty("role", "subtle")
        open_data.clicked.connect(lambda: reveal_in_file_manager(data_dir()))
        row.addWidget(clear)
        row.addWidget(open_data)
        body.addLayout(row)
        self._update_cache_size()
        layout.addWidget(panel)

        layout.addWidget(_title(tr("Supported formats")))
        panel2, body2 = _panel()
        formats = QLabel(
            tr(
                "RAW: Sony ARW / SRF / SR2, Adobe DNG, Canon CR2 / CR3, Nikon NEF / NRW, "
                "Fujifilm RAF, Olympus ORF, Panasonic RW2, Pentax PEF, Samsung SRW, "
                "Hasselblad 3FR, Leica RWL and other LibRaw formats.\n"
                "Images: JPEG, PNG, TIFF, WebP, BMP, GIF, AVIF, HEIC/HEIF."
            )
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
        self.cache_size_label.setText(
            tr("Preview cache: {size}", size=format_bytes(size))
        )

    def _clear_cache(self) -> None:
        if (
            QMessageBox.question(
                self,
                tr("Clear cache"),
                tr(
                    "Delete generated previews? They will be recreated the next time you view the photos."
                ),
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
                        tr(
                            "Folder names must not be empty or contain special characters"
                        )
                    )
            if dest.mode == "custom" and not dest.custom_root:
                raise ValueError(tr("Choose a shared folder for results"))
            dest.validate()
        except ValueError as error:
            QMessageBox.warning(self, tr("Check the settings"), str(error))
            return

        self.config.language = str(
            self.language_combo.currentData() or self.config.language
        )
        self.config.destinations = Destinations.from_dict(
            dest.to_dict(), self.config.language
        )
        self.config.behavior.sort_by = (
            "name" if self.sort_combo.currentIndex() == 1 else "date"
        )
        self.config.behavior.recursive_default = self.recursive_check.isChecked()
        self.config.behavior.raw_view_mode = str(
            self.raw_view_combo.currentData() or "jpeg"
        )
        self.config.controller.enabled = self.controller_enabled.isChecked()
        self.config.controller.deadzone = self.deadzone_slider.value() / 100.0
        self.config.controller.vibration = self.vibration_check.isChecked()
        self._saved = True
        self.accept()

    @property
    def result_config(self) -> Config:
        return self.config
