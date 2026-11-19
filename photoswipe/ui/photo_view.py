from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .icons import icon
from .widgets import Spinner

_SWIPE_META = {
    "left": ("trash", "В корзину", theme.RED),
    "right": ("favorite", "В избранное", theme.GREEN),
    "up": ("round2", "На второй раунд", theme.BLUE),
    "down": ("maybe", "Может быть", theme.AMBER),
}


class SwipeHint(QWidget):
    """Transparent overlay shown while dragging a photo at fit scale."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._direction: str | None = None
        self._progress = 0.0
        self.hide()

    def set_state(self, direction: str | None, progress: float) -> None:
        self._direction = direction
        self._progress = max(0.0, min(1.0, progress))
        if direction and progress > 0.03:
            self.raise_()
            self.show()
        else:
            self.hide()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._direction:
            return
        name, label, color = _SWIPE_META[self._direction]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        alpha = int(min(92, 16 + self._progress * 84))
        tint = QColor(color)
        tint.setAlpha(alpha)
        painter.fillRect(self.rect(), tint)
        # Strong edge gradient in the swipe direction.
        gradient = QLinearGradient(0, 0, self.width(), 0)
        if self._direction == "left":
            gradient.setStart(self.width(), 0)
            gradient.setFinalStop(0, 0)
        elif self._direction == "right":
            gradient.setStart(0, 0)
            gradient.setFinalStop(self.width(), 0)
        elif self._direction == "up":
            gradient = QLinearGradient(0, self.height(), 0, 0)
        else:
            gradient = QLinearGradient(0, 0, 0, self.height())
        edge = QColor(color)
        edge.setAlpha(min(168, alpha + 54))
        transparent = QColor(color)
        transparent.setAlpha(0)
        gradient.setColorAt(0.0, edge)
        gradient.setColorAt(0.65, transparent)
        painter.fillRect(self.rect(), gradient)

        # Use a direction arrow glyph above the label for clarity.
        arrow_name = {
            "left": "arrow-left",
            "right": "arrow-right",
            "up": "arrow-up",
            "down": "arrow-down",
        }[self._direction]
        arrow = icon(arrow_name, "#ffffff", 46).pixmap(46, 46)
        font = QFont(self.font())
        font.setPointSizeF(19)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        label_rect = self.rect()
        painter.drawText(
            label_rect.adjusted(0, -52, 0, -52), Qt.AlignmentFlag.AlignCenter, label
        )
        x = (self.width() - 46) // 2
        y = self.height() // 2 + 18
        painter.drawPixmap(x, y, arrow)
        painter.end()


class LoadingOverlay(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            f"QFrame {{ background: rgba(13, 15, 18, 185); border: 1px solid {theme.BORDER}; border-radius: 14px; }}"
            "QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner = Spinner(self, 28)
        self.label = QLabel("Загрузка…")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10pt;")
        layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignHCenter)
        self.hide()

    def show_message(self, text: str) -> None:
        self.label.setText(text)
        self.label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10pt;")
        self.spinner.show()
        self.adjustSize()
        self._center()
        self.show()
        self.raise_()

    def show_error(self, text: str) -> None:
        self.label.setText(text)
        self.label.setStyleSheet(f"color: {theme.RED}; font-size: 10pt;")
        self.spinner.hide()
        self.adjustSize()
        self._center()
        self.show()
        self.raise_()

    def _center(self) -> None:
        if self.parentWidget():
            self.move(
                max(12, (self.parentWidget().width() - self.width()) // 2),
                max(12, (self.parentWidget().height() - self.height()) // 2),
            )


class PhotoView(QGraphicsView):
    swipe = Signal(str)  # left / right / up / down
    zoom_changed = Signal(int)  # percentage relative to actual pixels
    rotation_changed = Signal(int)
    double_clicked = Signal()

    def __init__(
        self, parent: QWidget | None = None, *, allow_swipe: bool = True
    ) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._item)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QColor(theme.BG_DEEP))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontSavePainterState, True
        )
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._pixmap: QPixmap | None = None
        self._rotation = 0
        self._fit_scale = 1.0
        self._auto_fit = True
        self._allow_swipe = allow_swipe
        self._pressed = False
        self._press_pos = QPoint()
        self._last_pos = QPoint()
        self._swipe_direction: str | None = None

        self._swipe_hint = SwipeHint(self.viewport())
        self._loading = LoadingOverlay(self.viewport())
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)

    # ------------------------------------------------------------------
    @property
    def has_image(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    @property
    def rotation(self) -> int:
        return self._rotation

    @property
    def zoom_factor(self) -> float:
        return self.transform().m11() / self._fit_scale if self._fit_scale else 1.0

    def set_allow_swipe(self, value: bool) -> None:
        self._allow_swipe = value

    # ------------------------------------------------------------------
    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._loading.hide()
        self._pixmap = pixmap
        self._item.setPixmap(pixmap)
        self._item.setTransformOriginPoint(self._item.boundingRect().center())
        self._rotation = 0
        self._item.setRotation(0)
        self.fit_to_window()
        self.rotation_changed.emit(0)

    def set_loading(self, message: str = "Загрузка фото…") -> None:
        if self.has_image:
            return
        self._loading.show_message(message)
        self._loading._center()

    def set_error(self, message: str = "Не удалось открыть фотографию") -> None:
        self._pixmap = None
        self._item.setPixmap(QPixmap())
        self._loading.show_error(message)

    def clear(self) -> None:
        self._pixmap = None
        self._item.setPixmap(QPixmap())
        self._loading.hide()
        self.resetTransform()
        self._fit_scale = 1.0

    # ------------------------------------------------------------------
    def _compute_fit_scale(self) -> float:
        if not self.has_image:
            return 1.0
        rect = self._item.sceneBoundingRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return 1.0
        viewport = self.viewport().size()
        available_w = max(80, viewport.width() - 36)
        available_h = max(80, viewport.height() - 36)
        return min(available_w / rect.width(), available_h / rect.height())

    def _apply_scale(self, scale: float, *, center: QPoint | None = None) -> None:
        self.resetTransform()
        self.scale(scale, scale)
        if center is not None:
            self.centerOn(self.mapToScene(center))
        else:
            self.centerOn(self._item)
        self.emit_zoom()

    def fit_to_window(self) -> None:
        if not self.has_image:
            return
        self._fit_scale = self._compute_fit_scale()
        self._apply_scale(self._fit_scale)
        self._auto_fit = True

    def actual_size(self) -> None:
        if not self.has_image:
            return
        self._apply_scale(1.0)
        self._auto_fit = False

    def zoom_in(self) -> None:
        self.zoom_by(1.25)

    def zoom_out(self) -> None:
        self.zoom_by(0.8)

    def zoom_by(self, factor: float, anchor: QPoint | None = None) -> None:
        if not self.has_image:
            return
        current = self.transform().m11()
        fit = self._compute_fit_scale()
        self._fit_scale = fit
        target = max(fit, min(fit * 14.0, current * factor))
        if abs(target - current) < 0.0001:
            return
        anchor_pos = anchor or QPoint(
            self.viewport().width() // 2, self.viewport().height() // 2
        )
        scene_point = self.mapToScene(anchor_pos)
        self.resetTransform()
        self.scale(target, target)
        self.centerOn(self._item)
        after = self.mapFromScene(scene_point)
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() + (after.x() - anchor_pos.x())
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() + (after.y() - anchor_pos.y())
        )
        self._auto_fit = target <= fit * 1.01
        if self._auto_fit:
            self._apply_scale(fit)
        self.emit_zoom()

    def rotate_cw(self) -> None:
        self._rotate_by(90)

    def rotate_ccw(self) -> None:
        self._rotate_by(-90)

    def _rotate_by(self, delta: int) -> None:
        if not self.has_image:
            return
        factor = max(1.0, self.zoom_factor)
        self._rotation = (self._rotation + delta) % 360
        self._item.setRotation(self._rotation)
        self._fit_scale = self._compute_fit_scale()
        self._apply_scale(self._fit_scale * factor)
        self._auto_fit = factor <= 1.01
        self.rotation_changed.emit(self._rotation)

    def set_rotation_degrees(self, degrees: int) -> None:
        if not self.has_image:
            return
        factor = max(1.0, self.zoom_factor)
        self._rotation = int(degrees) % 360
        self._item.setRotation(self._rotation)
        self._fit_scale = self._compute_fit_scale()
        self._apply_scale(self._fit_scale * factor)
        self._auto_fit = factor <= 1.01
        self.rotation_changed.emit(self._rotation)

    def reset_view(self) -> None:
        if not self.has_image:
            return
        self._rotation = 0
        self._item.setRotation(0)
        self.rotation_changed.emit(0)
        self.fit_to_window()

    def emit_zoom(self) -> None:
        if self.has_image:
            self.zoom_changed.emit(int(round(self.transform().m11() * 100)))

    def pan_by(self, dx: int, dy: int) -> None:
        if not self.has_image or self.zoom_factor <= 1.01:
            return
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx)
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)

    # ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        if self.has_image:
            if self._auto_fit:
                self.fit_to_window()
            else:
                self._fit_scale = self._compute_fit_scale()
                self.emit_zoom()
        self._layout_overlays()
        super().resizeEvent(event)

    def _layout_overlays(self) -> None:
        viewport = self.viewport().rect()
        self._swipe_hint.setGeometry(viewport)
        self._loading._center()

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # type: ignore[override]
        super().scrollContentsBy(dx, dy)
        self._layout_overlays()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._layout_overlays()

    # ------------------------------------------------------------------
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if not self.has_image:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            return
        factor = 1.22 if delta > 0 else 1 / 1.22
        self.zoom_by(factor, event.position().toPoint())
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.has_image:
            self._pressed = True
            self._press_pos = event.position().toPoint()
            self._last_pos = self._press_pos
            self._swipe_direction = None
            if self.zoom_factor > 1.02:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._pressed and self.has_image:
            pos = event.position().toPoint()
            if self.zoom_factor <= 1.02:
                dx = pos.x() - self._press_pos.x()
                dy = pos.y() - self._press_pos.y()
                if self._allow_swipe:
                    distance = max(abs(dx), abs(dy))
                    threshold = max(
                        70.0,
                        min(self.viewport().width(), self.viewport().height()) * 0.12,
                    )
                    if distance > 6:
                        direction = (
                            ("right" if dx > 0 else "left")
                            if abs(dx) >= abs(dy)
                            else ("down" if dy > 0 else "up")
                        )
                        self._swipe_direction = direction
                        self._swipe_hint.set_state(
                            direction, min(1.0, distance / threshold)
                        )
            else:
                dx = pos.x() - self._last_pos.x()
                dy = pos.y() - self._last_pos.y()
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - dx
                )
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._last_pos = pos
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            pos = event.position().toPoint()
            dx = pos.x() - self._press_pos.x()
            dy = pos.y() - self._press_pos.y()
            threshold = max(
                70.0, min(self.viewport().width(), self.viewport().height()) * 0.12
            )
            if (
                self._allow_swipe
                and self.zoom_factor <= 1.02
                and max(abs(dx), abs(dy)) >= threshold
            ):
                direction = (
                    ("right" if dx > 0 else "left")
                    if abs(dx) >= abs(dy)
                    else ("down" if dy > 0 else "up")
                )
                self.swipe.emit(direction)
            self._swipe_hint.set_state(None, 0)
            self._swipe_direction = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.has_image:
            if self.zoom_factor > 1.08:
                self.fit_to_window()
            else:
                self.actual_size()
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        if not self._pressed:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)
