from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from photoswipe.shortcuts import display_combo, event_to_combo


class ShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def event(key, text="", modifiers=Qt.KeyboardModifier.NoModifier) -> QKeyEvent:
        return QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)

    def test_letters_and_arrows(self) -> None:
        self.assertEqual(event_to_combo(self.event(Qt.Key.Key_D, "d")), "KeyD")
        self.assertEqual(event_to_combo(self.event(Qt.Key.Key_Right)), "ArrowRight")

    def test_russian_layout_maps_to_physical_keys(self) -> None:
        self.assertEqual(event_to_combo(self.event(Qt.Key.Key_D, "в")), "KeyD")
        self.assertEqual(event_to_combo(self.event(Qt.Key.Key_A, "ф")), "KeyA")

    def test_shifted_slash_and_numpad(self) -> None:
        self.assertEqual(
            event_to_combo(
                self.event(Qt.Key.Key_Question, "?", Qt.KeyboardModifier.ShiftModifier)
            ),
            "Shift+Slash",
        )
        self.assertEqual(display_combo("Shift+Slash"), "?")
        self.assertEqual(
            event_to_combo(
                self.event(Qt.Key.Key_Plus, "+", Qt.KeyboardModifier.KeypadModifier)
            ),
            "NumpadAdd",
        )


if __name__ == "__main__":
    unittest.main()
