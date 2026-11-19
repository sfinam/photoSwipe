from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from PySide6.QtCore import QObject, QTimer, Signal

from .i18n import tr

try:
    import pygame
except Exception:  # pragma: no cover - optional dependency runtime failure
    pygame = None

BUTTON_LABELS = {
    0: "A / ×",
    1: "B / ○",
    2: "X / □",
    3: "Y / △",
    4: "LB",
    5: "RB",
    6: "LT",
    7: "RT",
    8: "Back / Select",
    9: "Start / Options",
    10: "LS",
    11: "RS",
    12: "D-pad ↑",
    13: "D-pad ↓",
    14: "D-pad ←",
    15: "D-pad →",
}


def button_label(index: int) -> str:
    return BUTTON_LABELS.get(index, tr("Button {index}", index=index))


def button_choices() -> list[tuple[int, str]]:
    return [(index, button_label(index)) for index in range(16)]


class ControllerManager(QObject):
    button_pressed = Signal(int)
    stick_moved = Signal(float, float)
    connected = Signal(str)
    disconnected = Signal()
    status_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._available = pygame is not None
        self._joysticks: list = []
        self._pressed: set[int] = set()
        self._deadzone = 0.25
        self._enabled = True
        self._last_count = -1
        self._name = ""
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._poll)
        self._init_error = ""
        if self._available:
            try:
                pygame.joystick.init()
            except Exception as error:  # noqa: BLE001
                self._available = False
                self._init_error = str(error)
        self._scan(force=True)
        self._timer.start()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return bool(self._joysticks)

    def set_deadzone(self, value: float) -> None:
        self._deadzone = min(0.8, max(0.0, float(value)))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._last_count = -1
        if not enabled:
            self._name = ""
            self.status_changed.emit("")
        else:
            self._scan(force=True)
            self.status_changed.emit(self._name)

    def _scan(self, force: bool = False) -> None:
        if not self._available or not self._enabled:
            return
        try:
            pygame.event.pump()
            count = pygame.joystick.get_count()
        except Exception:
            return
        if not force and count == self._last_count:
            return
        self._last_count = count
        was_connected = bool(self._joysticks)
        self._joysticks = []
        for index in range(count):
            try:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
                self._joysticks.append(joystick)
            except Exception:
                continue
        if self._joysticks:
            self._name = ", ".join(joy.get_name() for joy in self._joysticks)
            self.connected.emit(self._name)
            self.status_changed.emit(self._name)
        else:
            self._name = ""
            if was_connected:
                self.disconnected.emit()
            self.status_changed.emit("")

    def _poll(self) -> None:
        if not self._available or not self._enabled:
            return
        self._scan()
        if not self._joysticks:
            self._pressed.clear()
            return
        joystick = self._joysticks[0]
        try:
            pygame.event.pump()
            pressed_now: set[int] = set()
            for index in range(min(32, joystick.get_numbuttons())):
                if joystick.get_button(index):
                    pressed_now.add(index)
            axes = []
            for index in range(min(8, joystick.get_numaxes())):
                try:
                    axes.append(float(joystick.get_axis(index)))
                except Exception:
                    axes.append(0.0)
        except Exception:
            return
        # SDL exposes many controller triggers as axes rather than buttons.
        if len(axes) >= 6:
            if axes[4] > 0.55:
                pressed_now.add(6)
            if axes[5] > 0.55:
                pressed_now.add(7)
        new_buttons = pressed_now - self._pressed
        for index in sorted(new_buttons):
            self.button_pressed.emit(index)
        self._pressed = pressed_now
        if len(axes) >= 2:
            x, y = axes[0], axes[1]
            magnitude = max(abs(x), abs(y))
            if magnitude <= self._deadzone:
                x = y = 0.0
            else:
                x = (x - (1 if x > 0 else -1) * self._deadzone) / (1 - self._deadzone)
                y = (y - (1 if y > 0 else -1) * self._deadzone) / (1 - self._deadzone)
            if x or y:
                self.stick_moved.emit(max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)))

    def rumble(
        self, low: float = 0.35, high: float = 0.35, duration_ms: int = 90
    ) -> None:
        if not self._joysticks:
            return
        for joystick in self._joysticks:
            rumble = getattr(joystick, "rumble", None)
            if not callable(rumble):
                continue
            try:
                rumble(low, high, duration_ms)
            except Exception:
                pass

    def shutdown(self) -> None:
        self._timer.stop()
