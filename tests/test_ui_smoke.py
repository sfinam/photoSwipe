from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from photoswipe.config import Config, ConfigStore
from photoswipe.session import SessionManager
from photoswipe.ui.main_window import MainWindow
from photoswipe.ui.theme import apply_theme
from tests.helpers import TempWorkspace


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self) -> None:
        self.ws = TempWorkspace()
        self.root = self.ws.make_pair()

    def tearDown(self) -> None:
        self.ws.cleanup()

    def test_window_builds_and_shows_first_pair(self) -> None:
        config = Config()
        source = config.add_source(self.root, recursive=False)
        store = ConfigStore(self.ws.base / "config.json")
        store.save(config)
        manager = SessionManager(store)
        window = MainWindow()
        window.show()
        self.app.processEvents()
        session = manager.open(source)
        window.current_source = source
        window.current_session = session
        window.sorting_page.set_session(session)
        window.stack.setCurrentWidget(window.sorting_page)
        self.app.processEvents()
        self.assertEqual(window.sorting_page.photo_name.text(), "A7309498")
        self.assertIn("ARW", window.sorting_page.format_badge.text())
        window.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
