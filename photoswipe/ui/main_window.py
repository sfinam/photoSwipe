from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, QThreadPool, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import Config, ConfigStore, Source, safe_source_name
from ..controller import ControllerManager
from ..i18n import set_language, tr
from ..media import PreviewService
from ..session import SessionError, SessionManager, SortSession
from ..shortcuts import event_to_combo
from ..ui_state import load_ui_state, save_ui_state
from ..utils import reveal_in_file_manager
from . import theme
from .compare_page import ComparePage
from .help_dialog import HelpDialog
from .icons import brand_pixmap, icon
from .library_page import LibraryPage
from .settings_dialog import SettingsDialog
from .sorting_page import SortingPage
from .widgets import Spinner, Toast
from .workers import ScanWorker


class ScanOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setVisible(False)
        self.setStyleSheet("background: rgba(8, 9, 11, 205);")
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setFixedWidth(460)
        card.setStyleSheet(
            f"QFrame {{ background: {theme.PANEL}; border: 1px solid {theme.BORDER_LIGHT};"
            "border-radius: 17px; } QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(11)
        self.spinner = Spinner(card, 30)
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = QLabel(tr("Scanning folder…"))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(self.title)
        self.detail = QLabel("")
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9.3pt;")
        layout.addWidget(self.detail)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.hint = QLabel(tr("This may take a few seconds for a large folder"))
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.4pt;")
        layout.addWidget(self.hint)
        root.addWidget(card)
        self.card = card

    def start(self, source: Source) -> None:
        self.title.setText(tr("Scanning folder…"))
        self.detail.setText(source.path)
        self.progress.setRange(0, 0)
        self.show()
        self.raise_()

    def update_progress(self, stage: str, current: int, total: int) -> None:
        if stage == "scan":
            self.title.setText(tr("Scanning folder…"))
            self.detail.setText(tr("Files found: {count}", count=current))
            self.progress.setRange(0, 0)
        else:
            self.title.setText(tr("Reading metadata…"))
            self.detail.setText(
                tr("{current} of {total}", current=current, total=total)
            )
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(current)

    def stop(self) -> None:
        self.hide()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PhotoSwipe")
        self.setWindowIcon(QIcon(brand_pixmap(64)))
        self.setMinimumSize(1100, 700)
        self._ui_state = load_ui_state()
        self._restore_geometry()

        self.store = ConfigStore()
        self.config: Config = self.store.load()
        set_language(self.config.language)
        theme.set_theme(self.config.behavior.theme)
        theme.apply_theme(QApplication.instance())
        self.manager = SessionManager(self.store)
        self.preview_service = PreviewService()
        self.current_source: Source | None = None
        self.current_session: SortSession | None = None
        self._scan_worker: ScanWorker | None = None
        self._busy = False
        self._in_compare = False
        self._fullscreen = False
        self._immersive = False
        self._summary_cache: dict[str, dict] = {}
        self._closing = False

        QThreadPool.globalInstance().setMaxThreadCount(4)
        self.controller = ControllerManager(self)
        self.controller.set_enabled(self.config.controller.enabled)
        self.controller.set_deadzone(self.config.controller.deadzone)
        self.controller.button_pressed.connect(self._on_controller_button)
        self.controller.stick_moved.connect(self._on_controller_stick)
        self.controller.status_changed.connect(self._on_controller_status)
        self.controller.connected.connect(self._on_controller_connected)
        self.controller.disconnected.connect(self._on_controller_disconnected)

        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack)
        self.setCentralWidget(root)
        self.root = root

        self.library_page = LibraryPage()
        self.sorting_page = SortingPage(self.preview_service, self.config)
        self.compare_page = ComparePage(self.preview_service, self.config)
        self.stack.addWidget(self.library_page)
        self.stack.addWidget(self.sorting_page)
        self.stack.addWidget(self.compare_page)

        self.scan_overlay = ScanOverlay(root)
        self.toast = Toast(root)
        self.exit_fullscreen_button = QPushButton(tr("Exit fullscreen"), root)
        self.exit_fullscreen_button.setObjectName("ImmersiveExit")
        self.exit_fullscreen_button.setIcon(icon("minimize", "#f4f1ea", 16))
        self.exit_fullscreen_button.setFixedHeight(40)
        self.exit_fullscreen_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_fullscreen_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_fullscreen_button.setToolTip(tr("Exit fullscreen (Esc / F)"))
        self.exit_fullscreen_button.setStyleSheet(
            "QPushButton#ImmersiveExit {"
            " background: rgba(17, 19, 23, 225);"
            " color: #f4f1ea;"
            " border: 1px solid rgba(255, 255, 255, 55);"
            " border-radius: 10px;"
            " padding: 8px 14px;"
            " font-size: 9.5pt;"
            " font-weight: 600;"
            " }"
            "QPushButton#ImmersiveExit:hover {"
            " background: rgba(35, 38, 46, 240);"
            " border-color: rgba(240, 189, 88, 150);"
            " }"
        )
        self.exit_fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.exit_fullscreen_button.hide()
        self._connect_signals()
        self._refresh_library()
        self.show_library()
        QApplication.instance().installEventFilter(self)
        # Keep a Python reference to the active top-level window. This also
        # protects a freshly recreated window when the language changes.
        QApplication.instance()._photoswipe_main_window = self
        QTimer.singleShot(200, self._initial_controller_status)

    # ------------------------------------------------------------------
    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            width = min(1440, max(1100, available.width() - 80))
            height = min(900, max(700, available.height() - 80))
            self.resize(width, height)
            self.move(
                available.x() + max(0, (available.width() - width) // 2),
                available.y() + max(0, (available.height() - height) // 2),
            )

    def _restore_geometry(self) -> None:
        geometry = self._ui_state.get("geometry")
        restored = False
        if isinstance(geometry, list) and len(geometry) == 4:
            try:
                x, y, width, height = (int(value) for value in geometry)
            except (TypeError, ValueError):
                x = y = width = height = 0
            if width >= 1100 and height >= 700:
                rect = QRect(x, y, width, height)
                if any(
                    screen.availableGeometry().intersects(rect)
                    for screen in QApplication.screens()
                ):
                    self.setGeometry(rect)
                    restored = True
        if not restored:
            self._center_on_screen()

    def _connect_signals(self) -> None:
        self.library_page.add_requested.connect(self.add_source)
        self.library_page.open_requested.connect(self.open_source)
        self.library_page.settings_requested.connect(self.open_settings)
        self.library_page.help_requested.connect(self.open_help)
        self.library_page.source_action.connect(self._source_action)
        self.library_page.language_requested.connect(self.change_language)

        self.sorting_page.back_requested.connect(self.show_library)
        self.sorting_page.settings_requested.connect(self.open_settings)
        self.sorting_page.help_requested.connect(self.open_help)
        self.sorting_page.compare_requested.connect(self.open_compare)
        self.sorting_page.view_mode_cycle_requested.connect(self._set_raw_view_mode)
        self.sorting_page.decision_requested.connect(self._on_decision)
        self.sorting_page.undo_requested.connect(self._undo)
        self.sorting_page.next_round_requested.connect(self._next_round)
        self.sorting_page.first_round_requested.connect(self._first_round)
        self.sorting_page.reveal_requested.connect(self._reveal_destination)
        self.sorting_page.fullscreen_requested.connect(self.toggle_fullscreen)
        self.sorting_page.error_occurred.connect(
            lambda message: self.toast.show_message(message, "error", 4000)
        )

        self.compare_page.exit_requested.connect(self.exit_compare)
        self.compare_page.choose_requested.connect(self._compare_choose)
        self.compare_page.skip_side_requested.connect(self._compare_skip_side)
        self.compare_page.view_mode_cycle_requested.connect(
            self._cycle_global_view_mode
        )
        self.compare_page.undo_requested.connect(self._undo)
        self.compare_page.settings_requested.connect(self.open_settings)
        self.compare_page.help_requested.connect(self.open_help)
        self.compare_page.error_occurred.connect(
            lambda message: self.toast.show_message(message, "error", 4000)
        )

    # ------------------------------------------------------------------
    def _save_config(self) -> Config:
        self.config = self.store.save(self.config)
        self.manager.config = self.config
        self.sorting_page.set_config(self.config)
        self.compare_page.set_config(self.config)
        return self.config

    def _refresh_library(self) -> None:
        summaries: dict[str, dict] = {}
        for source in self.config.sources:
            try:
                summaries[source.id] = self.manager.summary(source)
            except Exception:
                summaries[source.id] = {}
        self._summary_cache = summaries
        self.library_page.set_data(self.config, summaries)

    def show_library(self) -> None:
        if self._scan_worker is not None:
            return
        if self._immersive:
            self._set_immersive(False)
        self._in_compare = False
        self._set_busy(False)
        self.sorting_page.clear()
        self.current_session = None
        self.current_source = None
        self._refresh_library()
        self.stack.setCurrentWidget(self.library_page)
        self.setWindowTitle(tr("PhotoSwipe — Library"))
        self.toast.hide()

    # ------------------------------------------------------------------
    def open_folder(self, path: str) -> None:
        """Add and open a folder passed by the OS or command line."""
        folder = Path(path).expanduser()
        try:
            folder = folder.resolve()
        except OSError:
            pass
        if folder.is_file():
            folder = folder.parent
        if not folder.is_dir():
            self.toast.show_message(
                tr("Folder not found: {path}", path=folder), "error", 5000
            )
            return
        before = len(self.config.sources)
        try:
            source = self.config.add_source(folder)
        except ValueError as error:
            self.toast.show_message(str(error), "error", 5000)
            return
        if len(self.config.sources) != before:
            self._save_config()
            self._refresh_library()
        self.open_source(source.id)

    def add_source(self) -> None:
        pictures = Path.home() / "Pictures"
        remembered = self._ui_state.get("last_add_dir")
        start = (
            remembered
            if isinstance(remembered, str) and Path(remembered).is_dir()
            else (str(pictures) if pictures.exists() else str(Path.home()))
        )
        folder = QFileDialog.getExistingDirectory(
            self, tr("Choose a folder with photos"), start
        )
        if not folder:
            return
        self._ui_state["last_add_dir"] = folder
        try:
            source = self.config.add_source(
                folder, self.config.behavior.recursive_default
            )
        except ValueError as error:
            self.toast.show_message(str(error), "error")
            return
        self._save_config()
        self._refresh_library()
        self.open_source(source.id)

    def open_source(self, source_id: str) -> None:
        if self._scan_worker is not None:
            return
        source = self.config.source(source_id)
        if source is None:
            self.toast.show_message(tr("Folder not found in the library"), "error")
            return
        if not source.exists:
            self.toast.show_message(tr("The source folder no longer exists"), "error")
            self._refresh_library()
            return
        self.current_source = source
        self.scan_overlay.start(source)
        self._reposition_overlays()
        self.scan_overlay.raise_()
        self._set_busy(True)
        worker = ScanWorker(self.manager, source)
        worker.signals.progress.connect(self.scan_overlay.update_progress)
        worker.signals.finished.connect(self._scan_finished)
        worker.signals.failed.connect(self._scan_failed)
        self._scan_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _scan_finished(self, session: SortSession) -> None:
        self._scan_worker = None
        self.scan_overlay.stop()
        self._set_busy(False)
        self.current_source = session.source
        self.current_session = session
        self.sorting_page.set_session(session)
        self.stack.setCurrentWidget(self.sorting_page)
        self.setWindowTitle(f"PhotoSwipe — {session.source.name}")
        self._refresh_library()
        self._on_controller_status(self.controller.name)

    def _scan_failed(self, message: str) -> None:
        self._scan_worker = None
        self.scan_overlay.stop()
        self._set_busy(False)
        self.current_session = None
        self.current_source = None
        self.show_library()
        self.toast.show_message(
            tr("Could not open folder: {error}", error=message), "error", 5000
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.sorting_page.set_busy(busy)
        self.compare_page.set_busy(busy)
        self.library_page.add_button.setEnabled(not busy)

    # ------------------------------------------------------------------
    def _on_decision(self, verdict: str) -> None:
        if self._busy or not self.current_session or not self.current_session.queue:
            return
        session = self.current_session
        if verdict == "round2" and session.mode == "second":
            self.toast.show_message(
                tr("The second round is already running — choose a final destination"),
                "info",
            )
            return
        group = session.queue[0]
        self._set_busy(True)
        try:
            session.decide([group], [verdict])
        except SessionError as error:
            self._set_busy(False)
            self.toast.show_message(str(error), "error", 4500)
            return
        self._set_busy(False)
        self.sorting_page.refresh(force=True)
        if self._immersive and not session.queue:
            self._set_immersive(False)
        if self.config.controller.vibration:
            self.controller.rumble()
        messages = {
            "favorite": (
                tr("In Favorites · {name}", name=group.display_name),
                "success",
            ),
            "trash": (tr("To trash · {name}", name=group.display_name), "info"),
            "maybe": (tr("To Maybe · {name}", name=group.display_name), "warning"),
            "round2": (
                tr("Deferred to second round · {name}", name=group.display_name),
                "info",
            ),
        }
        self.toast.show_message(*messages[verdict])

    def _undo(self) -> None:
        if self._busy or not self.current_session:
            return
        session = self.current_session
        self._set_busy(True)
        try:
            result = session.undo()
        except SessionError as error:
            self._set_busy(False)
            self.toast.show_message(str(error), "error", 5000)
            return
        self._set_busy(False)
        if self._in_compare:
            self.compare_page.pair_number = max(1, self.compare_page.pair_number - 1)
            self.compare_page.reload()
        else:
            self.sorting_page.refresh(force=True)
        count = len(result.restored)
        self.toast.show_message(tr("Undone: {count}", count=count), "success")
        if self.config.controller.vibration:
            self.controller.rumble()

    # ------------------------------------------------------------------
    def open_compare(self) -> None:
        if not self.current_session or len(self.current_session.queue) < 2:
            self.toast.show_message(
                tr("Comparison needs at least two photos"), "warning"
            )
            return
        self._in_compare = True
        self.compare_page.set_session(self.current_session)
        self.stack.setCurrentWidget(self.compare_page)
        if self._immersive:
            self.compare_page.set_immersive(True)
        source_name = self.current_source.name if self.current_source else ""
        self.setWindowTitle(tr("PhotoSwipe — Compare · {source}", source=source_name))

    def exit_compare(self) -> None:
        self._in_compare = False
        self.stack.setCurrentWidget(self.sorting_page)
        self.sorting_page.set_immersive(self._immersive)
        self.sorting_page.refresh(force=True)
        if self.current_source:
            self.setWindowTitle(f"PhotoSwipe — {self.current_source.name}")

    def _compare_skip_side(self, side: str) -> None:
        if self._busy or not self.current_session:
            return
        pair = self.compare_page.pair_groups()
        if not pair:
            return
        if self.current_session.mode != "first":
            self.toast.show_message(
                tr("Skipping is not available in the second round"),
                "info",
            )
            return
        group = pair[0] if side == "left" else pair[1]
        letter = "A" if side == "left" else "B"
        self._set_busy(True)
        try:
            self.current_session.decide([group], ["round2"])
        except SessionError as error:
            self._set_busy(False)
            self.toast.show_message(str(error), "error", 5000)
            return
        self._set_busy(False)
        if len(self.current_session.queue) >= 2:
            self.compare_page.replace_side(side, self.current_session.queue[1])
        else:
            self.compare_page.reload(force=True)
            if self._immersive:
                self._set_immersive(False)
        if self.config.controller.vibration:
            self.controller.rumble()
        self.toast.show_message(
            tr("{letter} deferred to the second round", letter=letter), "info"
        )

    def _compare_choose(self, choice: str) -> None:
        if self._busy or not self.current_session:
            return
        pair = self.compare_page.pair_groups()
        if not pair:
            return
        if choice == "skip" and self.current_session.mode != "first":
            self.toast.show_message(
                tr("Skipping is not available in the second round"),
                "info",
            )
            return
        if choice == "left":
            groups, verdicts = list(pair), ["favorite", "trash"]
        elif choice == "right":
            groups, verdicts = list(reversed(pair)), ["favorite", "trash"]
        elif choice == "both":
            groups, verdicts = list(pair), ["favorite", "favorite"]
        else:
            groups, verdicts = list(pair), ["round2", "round2"]
        self._set_busy(True)
        try:
            self.current_session.decide(groups, verdicts)
        except SessionError as error:
            self._set_busy(False)
            self.toast.show_message(str(error), "error", 5000)
            return
        self._set_busy(False)
        self.compare_page.advance()
        if self._immersive and (
            not self.current_session.queue or self.compare_page.pair_groups() is None
        ):
            self._set_immersive(False)
        if self.config.controller.vibration:
            self.controller.rumble()
        if choice == "both":
            message = tr("Both photos are in Favorites")
        elif choice == "skip":
            message = tr("Pair deferred to the second round")
        else:
            message = tr("Best shot in Favorites, the other moved to trash")
        self.toast.show_message(message, "success")

    def _next_round(self) -> None:
        if not self.current_session:
            return
        try:
            session = self.current_session.start_second_round()
        except SessionError as error:
            self.toast.show_message(str(error), "error")
            return
        self.current_session = session
        self.sorting_page.set_session(session)
        self.stack.setCurrentWidget(self.sorting_page)
        self.toast.show_message(
            tr("Second round · {count}", count=len(session.queue)), "info"
        )
        self._refresh_library()

    def _first_round(self) -> None:
        if not self.current_session:
            return
        session = self.current_session.back_to_first_round()
        self.current_session = session
        self.sorting_page.set_session(session)
        self.stack.setCurrentWidget(self.sorting_page)
        self.toast.show_message(tr("Back to the first round"), "info")
        self._refresh_library()

    # ------------------------------------------------------------------
    def change_language(self, code: str) -> None:
        if code == self.config.language or self._closing:
            return
        self.config.language = code
        set_language(code)
        self._save_config()
        QTimer.singleShot(0, self._reopen_for_language)

    def _reopen_for_language(self) -> None:
        if self._closing:
            return
        source_id = self.current_source.id if self.current_source else None
        new_window = MainWindow()
        geometry = (
            self.normalGeometry()
            if self.isFullScreen() or self.isMaximized()
            else self.geometry()
        )
        new_window.setGeometry(geometry)
        new_window.show()
        new_window.raise_()
        if source_id:
            QTimer.singleShot(0, lambda: new_window.open_source(source_id))
        self._replacement_window = new_window
        self.close()

    def _view_mode_label(self, mode: str) -> str:
        return {
            "jpeg": tr("JPEG"),
            "thumbnail": tr("RAW thumbnail"),
            "full": tr("RAW full"),
        }.get(mode, mode)

    def _set_raw_view_mode(self, mode: str) -> None:
        if mode not in {"jpeg", "thumbnail", "full"}:
            return
        if self.config.behavior.raw_view_mode == mode:
            return
        self.config.behavior.raw_view_mode = mode
        self._save_config()
        if self._in_compare:
            self.compare_page.reload(force=True)
        else:
            self.sorting_page.apply_view_mode()
        self.toast.show_message(
            tr(
                "Display mode: {mode}",
                mode=self._view_mode_label(mode),
            ),
            "info",
            1800,
        )

    def _cycle_global_view_mode(self) -> None:
        order = ["jpeg", "thumbnail", "full"]
        try:
            index = order.index(self.config.behavior.raw_view_mode)
        except ValueError:
            index = -1
        self._set_raw_view_mode(order[(index + 1) % len(order)])

    def open_settings(self) -> None:
        if self._immersive:
            self._set_immersive(False)
        old_language = self.config.language
        old_theme = self.config.behavior.theme
        old_raw_mode = self.config.behavior.raw_view_mode
        dialog = SettingsDialog(
            self.config,
            preview_service=self.preview_service,
            controller=self.controller,
            current_source=self.current_source
            or (self.config.sources[0] if self.config.sources else None),
            parent=self,
        )
        from PySide6.QtWidgets import QDialog

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.config = dialog.result_config
        self._save_config()
        if (
            self.config.language != old_language
            or self.config.behavior.theme != old_theme
        ):
            if self.config.language != old_language:
                set_language(self.config.language)
            if self.config.behavior.theme != old_theme:
                theme.set_theme(self.config.behavior.theme)
            QTimer.singleShot(0, self._reopen_for_language)
            return
        self.controller.set_deadzone(self.config.controller.deadzone)
        self.controller.set_enabled(self.config.controller.enabled)
        self._on_controller_status(
            self.controller.name if self.config.controller.enabled else ""
        )
        if self.current_session and self.current_source:
            self.current_session.config = self.config
            self.current_session.destinations = self.config.destinations.for_source(
                self.current_source
            )
            try:
                self.current_session.save()
            except OSError as error:
                self.toast.show_message(
                    tr("Could not save the session: {error}", error=error), "error"
                )
        self._refresh_library()
        self.toast.show_message(tr("Settings saved"), "success")
        if self.config.behavior.raw_view_mode != old_raw_mode:
            if self._in_compare:
                self.compare_page.reload(force=True)
            else:
                self.sorting_page.apply_view_mode()
        elif self._in_compare:
            self.compare_page.reload()
        elif self.stack.currentWidget() is self.sorting_page:
            self.sorting_page.refresh(force=True)

    def open_help(self) -> None:
        if self._immersive:
            self._set_immersive(False)
        HelpDialog(self.config, self).exec()

    # ------------------------------------------------------------------
    def _source_action(self, source_id: str, action: str) -> None:
        source = self.config.source(source_id)
        if not source:
            return
        if action == "reveal":
            reveal_in_file_manager(source.path)
        elif action == "rename":
            name, ok = QInputDialog.getText(
                self,
                tr("Rename folder"),
                tr("Name:"),
                text=source.name,
            )
            if ok and name.strip():
                source.name = safe_source_name(name.strip(), source.name)
                self._save_config()
                if self.current_source and self.current_source.id == source.id:
                    self.current_source = source
                self._refresh_library()
                self.toast.show_message(tr("Name updated"), "success")
        elif action in {"recursive", "flat"}:
            source.recursive = action == "recursive"
            self._save_config()
            self._refresh_library()
            self.toast.show_message(
                tr("Subfolders will be scanned")
                if source.recursive
                else tr("This folder only"),
                "info",
            )
        elif action == "reset":
            if (
                QMessageBox.question(
                    self,
                    tr("Reset progress"),
                    tr(
                        "Counters and undo history for this folder will be cleared. Files that were already moved will stay in place.\n\nContinue?"
                    ),
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            try:
                self.manager.reset_state(source)
            except SessionError as error:
                self.toast.show_message(str(error), "error")
                return
            if self.current_source and self.current_source.id == source.id:
                self.show_library()
            self._refresh_library()
            self.toast.show_message(tr("Progress reset"), "success")
        elif action == "remove":
            if (
                QMessageBox.question(
                    self,
                    tr("Remove folder"),
                    tr(
                        "Remove “{name}” from the library?\n\nPhotos and sorting results will stay on disk.",
                        name=source.name,
                    ),
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            self.config.remove_source(source.id)
            self._save_config()
            if self.current_source and self.current_source.id == source.id:
                self.show_library()
            self._refresh_library()
            self.toast.show_message(tr("Folder removed from the library"), "info")

    def _reveal_destination(self, verdict: str) -> None:
        if not self.current_session:
            return
        path = self.current_session.destinations.get(verdict)
        if not path:
            return
        path.mkdir(parents=True, exist_ok=True)
        if not reveal_in_file_manager(path):
            self.toast.show_message(
                tr("Could not open folder: {path}", path=path), "error"
            )

    # ------------------------------------------------------------------
    def toggle_fullscreen(self) -> None:
        self._set_immersive(not self._fullscreen)

    def _set_immersive(self, enabled: bool) -> None:
        self._fullscreen = enabled
        self._immersive = enabled
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()
        if self.stack.currentWidget() is self.sorting_page:
            self.sorting_page.set_immersive(enabled)
        elif self.stack.currentWidget() is self.compare_page:
            self.compare_page.set_immersive(enabled)
        self.sorting_page.fullscreen_button.setIcon(
            icon("minimize" if enabled else "maximize", theme.TEXT_MUTED, 18)
        )
        self.exit_fullscreen_button.setVisible(enabled)
        self.toast.set_suppressed(enabled)
        if enabled:
            self.toast.hide()
            self.exit_fullscreen_button.raise_()
        QTimer.singleShot(0, self._reposition_overlays)

    # ------------------------------------------------------------------
    def _on_controller_status(self, name: str) -> None:
        self.sorting_page.set_controller(name if self.config.controller.enabled else "")
        self.library_page.set_controller(name if self.config.controller.enabled else "")

    def _on_controller_connected(self, name: str) -> None:
        if self.config.controller.enabled:
            self.toast.show_message(
                tr("Gamepad connected: {name}", name=name), "success", 3500
            )

    def _on_controller_disconnected(self) -> None:
        if self.config.controller.enabled:
            self.toast.show_message(tr("Gamepad disconnected"), "info")

    def _initial_controller_status(self) -> None:
        self._on_controller_status(self.controller.name)

    def _on_controller_stick(self, x: float, y: float) -> None:
        if (
            self._scan_worker
            or QApplication.activeModalWidget()
            or not self.config.controller.enabled
            or self._in_compare
            or self._busy
        ):
            return
        if self.stack.currentWidget() is self.sorting_page:
            self.sorting_page.view.pan_by(int(x * 22), int(y * 22))

    def _on_controller_button(self, index: int) -> None:
        if (
            self._scan_worker
            or QApplication.activeModalWidget()
            or not self.config.controller.enabled
        ):
            return
        if self._in_compare:
            if index in (14, 4):
                self._compare_choose("left")
            elif index in (15, 5):
                self._compare_choose("right")
            elif index == 0:
                self._compare_choose("both")
            elif index == 1:
                self.exit_compare()
            elif index == 8:
                self._undo()
            return
        if self.stack.currentWidget() is not self.sorting_page:
            return
        for action in self.config.controller.mappings:
            if index in self.config.controller.mappings[action]:
                self.sorting_page.trigger_action(action)
                if (
                    action in {"favorite", "trash", "maybe", "round2"}
                    and self.config.controller.vibration
                ):
                    self.controller.rumble(0.2, 0.2, 40)
                return

    # ------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        if self._closing:
            return False
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)
        if QApplication.activeModalWidget() or QApplication.activePopupWidget():
            return super().eventFilter(obj, event)
        if event_to_combo(event) == "Ctrl+KeyQ":
            self.close()
            return True
        if self._scan_worker is not None:
            return True
        focus = QApplication.focusWidget()
        if isinstance(
            focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox)
        ):
            return super().eventFilter(obj, event)
        if event.isAutoRepeat():
            return True
        key = event.key()
        combo = event_to_combo(event)
        if self._in_compare:
            if combo and self.config.shortcut_for(combo) == "toggleRaw":
                self._cycle_global_view_mode()
                return True
            if key == Qt.Key.Key_Escape:
                if self._fullscreen:
                    self.toggle_fullscreen()
                else:
                    self.exit_compare()
                return True
            if combo == "KeyC":
                self.exit_compare()
                return True
            if combo == "Shift+ArrowLeft":
                self._compare_skip_side("left")
                return True
            if combo == "Shift+ArrowRight":
                self._compare_skip_side("right")
                return True
            if combo in {"ArrowLeft", "KeyA"}:
                self._compare_choose("left")
                return True
            if combo in {"ArrowRight", "KeyD"}:
                self._compare_choose("right")
                return True
            if combo == "Space":
                self._compare_choose("both")
                return True
            if combo in {"KeyS", "ArrowDown"}:
                self._compare_choose("skip")
                return True
            if combo == "KeyZ":
                self._undo()
                return True
            if combo in {"Equal", "NumpadAdd"}:
                self.compare_page.left.view.zoom_in()
                self.compare_page.right.view.zoom_in()
                return True
            if combo in {"Minus", "NumpadSubtract"}:
                self.compare_page.left.view.zoom_out()
                self.compare_page.right.view.zoom_out()
                return True
            if combo == "KeyR":
                self.compare_page.left.view.rotate_cw()
                self.compare_page.right.view.rotate_cw()
                return True
            if combo == "Shift+KeyR":
                self.compare_page.left.view.rotate_ccw()
                self.compare_page.right.view.rotate_ccw()
                return True
            if combo == "KeyF":
                self.toggle_fullscreen()
                return True
            return super().eventFilter(obj, event)

        if self.stack.currentWidget() is self.library_page:
            if combo == "Ctrl+KeyO":
                self.add_source()
                return True
            if combo == "Ctrl+Comma":
                self.open_settings()
                return True
            if combo in {"F1", "Shift+Slash"}:
                self.open_help()
                return True
            return super().eventFilter(obj, event)

        if self.stack.currentWidget() is self.sorting_page:
            if key == Qt.Key.Key_Escape:
                if self._fullscreen:
                    self.toggle_fullscreen()
                else:
                    self.show_library()
                return True
            if combo:
                action = self.config.shortcut_for(combo)
                if action:
                    if action == "fullscreen":
                        self.toggle_fullscreen()
                    elif action == "help":
                        self.open_help()
                    else:
                        self.sorting_page.trigger_action(action)
                    return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        if hasattr(self, "scan_overlay"):
            self.scan_overlay.setGeometry(0, 0, self.root.width(), self.root.height())
        if hasattr(self, "toast") and self.toast.isVisible():
            self.toast.adjustSize()
            self.toast.move(
                max(16, (self.root.width() - self.toast.width()) // 2),
                self.root.height() - self.toast.height() - 24,
            )
        if hasattr(self, "exit_fullscreen_button") and self._immersive:
            self.exit_fullscreen_button.adjustSize()
            self.exit_fullscreen_button.move(
                max(16, self.root.width() - self.exit_fullscreen_button.width() - 24),
                22,
            )
            self.exit_fullscreen_button.raise_()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._closing = True
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        if self._scan_worker is not None:
            self._scan_worker.cancel()
        workers = []
        for page in (self.sorting_page, self.compare_page):
            for worker in list(getattr(page, "_workers", set())) + list(
                getattr(page, "_prefetch_workers", set())
            ):
                try:
                    worker.cancel()
                except Exception:
                    pass
                workers.append(worker)
        self._closing_workers = workers
        QThreadPool.globalInstance().clear()
        QThreadPool.globalInstance().waitForDone(5000)
        try:
            self._save_config()
        except Exception:
            pass
        try:
            geometry = (
                self.normalGeometry()
                if self.isFullScreen() or self.isMaximized()
                else self.geometry()
            )
            self._ui_state["geometry"] = [
                geometry.x(),
                geometry.y(),
                geometry.width(),
                geometry.height(),
            ]
            save_ui_state(self._ui_state)
        except Exception:
            pass
        self.controller.shutdown()
        super().closeEvent(event)
