from __future__ import annotations


from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from . import theme
from .icons import brand_pixmap, icon


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text
        self.setToolTip(text)
        self._apply_elide()

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        metrics = self.fontMetrics()
        available = max(0, self.width() - 2)
        if available <= 0:
            super().setText(self._full_text)
            return
        super().setText(
            metrics.elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, available)
        )


class HLine(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setProperty("role", "sep")
        self.setFrameShape(QFrame.Shape.NoFrame)


class BrandWidget(QWidget):
    def __init__(
        self, subtitle: str | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(brand_pixmap(42))
        logo.setFixedSize(42, 42)
        layout.addWidget(logo)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        title = QLabel("PhotoSwipe")
        title.setProperty("role", "brand")
        subtitle_label = QLabel(
            subtitle if subtitle is not None else tr("fast photo culling")
        )
        subtitle_label.setProperty("role", "micro")
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle_label)
        layout.addLayout(text_layout)
        layout.addStretch(1)


class IconButton(QToolButton):
    def __init__(
        self,
        icon_name: str,
        tooltip: str = "",
        *,
        color: str = theme.TEXT_MUTED,
        size: int = 20,
        button_size: int = 38,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "icon")
        self.setIcon(icon(icon_name, color, size))
        self.setIconSize(QSize(size, size))
        self.setFixedSize(button_size, button_size)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class StatPill(QFrame):
    def __init__(
        self,
        icon_name: str,
        color: str,
        count: int = 0,
        label: str = "",
        *,
        compact: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self.setStyleSheet(
            f"QFrame {{ background: {theme.BG_DEEP}; border: 1px solid {theme.BORDER};"
            f" border-radius: 9px; }} QLabel {{ background: transparent; border: none; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 9, 4)
        layout.setSpacing(5)
        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name, color, 14).pixmap(14, 14))
        icon_label.setFixedSize(14, 14)
        self.count_label = QLabel(str(count))
        self.count_label.setStyleSheet(
            f"color: {color}; font-size: 9.5pt; font-weight: 700;"
        )
        layout.addWidget(icon_label)
        layout.addWidget(self.count_label)
        if label and not compact:
            text = QLabel(label)
            text.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9pt;")
            layout.addWidget(text)
        self.setToolTip(label or "")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_count(self, count: int) -> None:
        self.count_label.setText(str(count))


class Badge(QLabel):
    def __init__(
        self, text: str = "", *, role: str = "badge", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("role", role)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class KeyBadge(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: {theme.KEY_BADGE_BG}; color: {theme.TEXT_MUTED};"
            f"border: 1px solid {theme.KEY_BADGE_BORDER}; border-radius: 6px;"
            "padding: 2px 6px; font-size: 8.5pt; font-weight: 600;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class DecisionButton(QPushButton):
    def __init__(
        self,
        verdict: str,
        title: str,
        icon_name: str,
        color: str,
        shortcut: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.verdict = verdict
        self.setProperty("role", "decision")
        self.setProperty("verdict", verdict)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 11, 13, 11)
        layout.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name, color, 23).pixmap(23, 23))
        icon_label.setFixedSize(23, 23)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(icon_label)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 10.5pt; font-weight: 650;"
        )
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        hint_label = QLabel(tr("click or swipe"))
        hint_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 8.2pt;")
        hint_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(title_label)
        text_layout.addWidget(hint_label)
        layout.addLayout(text_layout, 1)
        self.setMinimumHeight(72)
        self.setMaximumHeight(72)
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)
        self.key_badge = KeyBadge(shortcut)
        self.key_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.key_badge, 0, Qt.AlignmentFlag.AlignTop)

    def changeEvent(self, event) -> None:  # type: ignore[override]
        if event.type() == QEvent.Type.EnabledChange and hasattr(self, "_opacity"):
            self._opacity.setOpacity(1.0 if self.isEnabled() else 0.42)
        super().changeEvent(event)

    def set_shortcut(self, value: str) -> None:
        self.key_badge.setText(value)
        self.key_badge.setVisible(bool(value))

    def set_hint(self, value: str) -> None:
        labels = self.findChildren(QLabel)
        if len(labels) >= 3:
            labels[2].setText(value)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")


class Toast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setVisible(False)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._suppressed = False
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(14, 9, 16, 9)
        self._layout.setSpacing(9)
        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(520)
        self._label.setStyleSheet(f"color: {theme.TEXT}; font-size: 9.5pt;")
        self._layout.addWidget(self._icon)
        self._layout.addWidget(self._label)
        self.setStyleSheet(
            f"QFrame {{ background: {theme.PANEL_RAISED}; border: 1px solid {theme.BORDER_LIGHT};"
            "border-radius: 11px; } QLabel { background: transparent; border: none; }"
        )
        self.adjustSize()

    def set_suppressed(self, suppressed: bool) -> None:
        self._suppressed = suppressed
        if suppressed:
            self.hide()

    def show_message(self, text: str, kind: str = "info", duration: int = 2600) -> None:
        if self._suppressed and kind != "error":
            return
        colors = {
            "info": theme.BLUE,
            "success": theme.GREEN,
            "error": theme.RED,
            "warning": theme.AMBER,
        }
        icons = {
            "info": "info",
            "success": "check",
            "error": "alert",
            "warning": "alert",
        }
        color = colors.get(kind, theme.BLUE)
        self._icon.setPixmap(icon(icons.get(kind, "info"), color, 16).pixmap(16, 16))
        self._label.setText(text)
        self.adjustSize()
        self.raise_()
        self.show()
        self._timer.start(duration)
        if self.parentWidget():
            parent = self.parentWidget()
            x = max(16, (parent.width() - self.width()) // 2)
            y = parent.height() - self.height() - 104
            self.move(x, y)


class EmptyState(QWidget):
    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        *,
        accent: str = theme.ACCENT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 52, 36, 52)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle = QLabel()
        circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle.setFixedSize(84, 84)
        circle.setStyleSheet(
            f"background: {theme.PANEL_RAISED}; border: 1px solid {theme.BORDER}; border-radius: 42px;"
        )
        circle.setPixmap(icon(icon_name, accent, 34).pixmap(34, 34))
        layout.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)
        title_label = QLabel(title)
        title_label.setProperty("role", "h2")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        description_label = QLabel(description)
        description_label.setProperty("role", "muted")
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setMaximumWidth(520)
        layout.addWidget(description_label, 0, Qt.AlignmentFlag.AlignHCenter)


class Spinner(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 26) -> None:
        super().__init__(parent)
        self._angle = 0
        self._size = size
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def _tick(self) -> None:
        self._angle = (self._angle + 24) % 360
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        pen = painter.pen()
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setColor(QColor(theme.ACCENT))
        painter.setPen(pen)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.drawArc(rect, 20 * 16, 250 * 16)
        painter.end()


def set_style_property(widget: QWidget, name: str, value) -> None:
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
