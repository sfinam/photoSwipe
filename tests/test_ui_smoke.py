from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import shutil

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

    def test_compare_skip_replaces_only_one_side(self) -> None:
        shutil.copy2(self.root / "A7309498.JPG", self.root / "IMG_0002.JPG")
        shutil.copy2(self.root / "A7309498.JPG", self.root / "IMG_0003.JPG")
        config = Config()
        source = config.add_source(self.root, recursive=False)
        store = ConfigStore(self.ws.base / "skip-config.json")
        store.save(config)
        manager = SessionManager(store)
        window = MainWindow()
        window.show()
        session = manager.open(source)
        window.current_source = source
        window.current_session = session
        window.sorting_page.set_session(session)
        window.stack.setCurrentWidget(window.sorting_page)
        window.open_compare()
        self.app.processEvents()
        before_left, before_right = window.compare_page.pair
        window._compare_skip_side("left")
        self.app.processEvents()
        self.assertEqual(session.deferred_count, 1)
        self.assertEqual(len(session.queue), 2)
        new_left, new_right = window.compare_page.pair
        self.assertEqual(new_right.id, before_right.id)
        self.assertNotEqual(new_left.id, before_left.id)
        window.close()
        self.app.processEvents()

    def test_immersive_fullscreen_hides_chrome_and_keeps_shortcuts(self) -> None:
        shutil.copy2(self.root / "A7309498.JPG", self.root / "IMG_0002.JPG")
        shutil.copy2(self.root / "A7309498.JPG", self.root / "IMG_0003.JPG")
        config = Config()
        source = config.add_source(self.root, recursive=False)
        store = ConfigStore(self.ws.base / "immersive-config.json")
        store.save(config)
        manager = SessionManager(store)
        window = MainWindow()
        window.resize(1200, 800)
        window.show()
        session = manager.open(source)
        window.current_source = source
        window.current_session = session
        window.sorting_page.set_session(session)
        window.stack.setCurrentWidget(window.sorting_page)
        window._set_immersive(True)
        self.app.processEvents()
        self.assertTrue(window._immersive)
        self.assertFalse(window.sorting_page.header.isVisible())
        self.assertFalse(window.sorting_page.stage_header.isVisible())
        self.assertFalse(window.sorting_page.action_bar.isVisible())
        self.assertTrue(window.exit_fullscreen_button.isVisible())
        before = dict(session.stats)
        window._on_decision("favorite")
        self.app.processEvents()
        self.assertGreater(session.stats["favorite"], before["favorite"])
        self.assertTrue(window._immersive)
        window._set_immersive(False)
        self.app.processEvents()
        self.assertFalse(window.exit_fullscreen_button.isVisible())
        self.assertTrue(window.sorting_page.header.isVisible())
        window.close()
        self.app.processEvents()

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
