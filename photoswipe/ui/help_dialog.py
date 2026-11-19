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
from ..shortcuts import ACTION_HINTS, ACTION_LABELS, display_combo
from . import theme
from .icons import icon
from .widgets import HLine, KeyBadge


class HelpDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Справка — PhotoSwipe")
        self.setModal(True)
        self.resize(800, 680)
        self.setMinimumSize(680, 540)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Как пользоваться PhotoSwipe")
        title.setStyleSheet(f"color: {theme.TEXT}; font-size: 19pt; font-weight: 750;")
        header.addWidget(title)
        header.addStretch(1)
        close = QPushButton("Закрыть")
        close.setProperty("role", "ghost")
        close.clicked.connect(self.accept)
        header.addWidget(close)
        root.addLayout(header)
        tabs = QTabWidget()
        tabs.addTab(self._shortcuts_tab(config), "Клавиши")
        tabs.addTab(self._gestures_tab(config), "Свайпы и контроллер")
        tabs.addTab(self._about_tab(), "Принцип работы")
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
            "Каждое действие можно переназначить в настройках. Стрелки работают и в русской раскладке. "
            "Кнопки на экране делают то же самое."
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
            label = QLabel(ACTION_LABELS.get(action, action))
            label.setStyleSheet(
                f"color: {theme.TEXT}; font-size: 9.6pt; font-weight: 600;"
            )
            hint = QLabel(ACTION_HINTS.get(action, ""))
            hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.2pt;")
            text.addWidget(label)
            text.addWidget(hint)
            row.addLayout(text, 1)
            bindings = config.shortcuts.get(action, [])
            if not bindings:
                empty = QLabel("не назначено")
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
                "В режиме сравнения: ← / A — выбрать левую, → / D — правую, Пробел — обе в избранное, "
                "S — отложить пару, Esc — выйти. Эти клавиши фиксированы и не зависят от основной раскладки."
            )
        )
        layout.addStretch(1)
        return self._scroll(page)

    def _gestures_tab(self, config: Config) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section("Свайпы мышью или пальцем"))
        gestures = QHBoxLayout()
        gestures.setSpacing(8)
        for icon_name, color, title, detail in (
            ("arrow-left", theme.RED, "Влево", "в корзину"),
            ("arrow-right", theme.GREEN, "Вправо", "в избранное"),
            ("arrow-up", theme.BLUE, "Вверх", "на второй раунд"),
            ("arrow-down", theme.AMBER, "Вниз", "в «Может быть»"),
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
                "Свайп работает, когда фотография вписана в окно. Если вы приблизили кадр, перетаскивание "
                "двигает изображение. Двойной щелчок переключает между вписанным видом и масштабом 1:1. "
                "Колесо мыши приближает точку под курсором."
            )
        )

        layout.addWidget(self._section("Контроллер"))
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
            label = QLabel(ACTION_LABELS.get(action, action))
            label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9.2pt;")
            row.addWidget(label, 1)
            for index in values:
                row.addWidget(KeyBadge(button_label(index)))
            body.addLayout(row)
        layout.addWidget(controller_panel)
        layout.addWidget(
            self._note(
                "В сравнении: D-pad ←/→ или LB/RB — выбрать кадр, A — оставить оба, B — выйти, "
                "Back — отменить. Подключение контроллера определяется автоматически."
            )
        )
        layout.addStretch(1)
        return self._scroll(page)

    def _about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self._section("Четыре решения"))
        steps = (
            (
                "heart",
                theme.GREEN,
                "В избранное",
                "Файл (и его RAW-пара) перемещается в папку «Избранное».",
            ),
            (
                "trash",
                theme.RED,
                "В корзину",
                "Файл перемещается в выбранную папку корзины. Это не системная корзина, поэтому отмену можно сделать в приложении.",
            ),
            (
                "clock",
                theme.AMBER,
                "Может быть",
                "Файл отправляется в отдельную папку, чтобы вернуться к нему позже.",
            ),
            (
                "clock",
                theme.BLUE,
                "На второй раунд",
                "Файл остаётся на месте и попадает в отдельную очередь. Второй раунд покажет только отложенные кадры.",
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
                "Файлы с одинаковым именем и разными расширениями считаются одной фотографией. "
                "В карточке можно переключать ARW и JPEG для просмотра, но решение применяется ко всей паре "
                "вместе — включая XMP и другие sidecar-файлы. RAW показывается через встроенное превью камеры; "
                "полное декодирование включается в настройках."
            )
        )
        layout.addWidget(self._section("Безопасность"))
        layout.addWidget(
            self._note(
                "Все операции локальные. Файлы перемещаются, а не копируются, с проверкой конфликтов имён. "
                "Последние 120 действий можно отменить, даже после перезапуска. Данные и кэш превью лежат "
                "в системной папке приложения и не попадают в вашу фотобиблиотеку."
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
