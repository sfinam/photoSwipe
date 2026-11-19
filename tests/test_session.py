from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from photoswipe.config import Config, ConfigStore
from photoswipe.session import SessionError, SessionManager
from tests.helpers import TempWorkspace


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = TempWorkspace()

    def tearDown(self) -> None:
        self.ws.cleanup()

    def _manager(
        self, root: Path, recursive: bool = False
    ) -> tuple[SessionManager, object]:
        config = Config()
        source = config.add_source(root, recursive=recursive)
        store = ConfigStore(self.ws.base / "config.json")
        store._config = config
        store.save()
        return SessionManager(store), source

    def test_favorite_moves_both_formats_and_undo_restores(self) -> None:
        root = self.ws.make_pair()
        manager, source = self._manager(root)
        session = manager.open(source)
        self.assertEqual(len(session.queue), 1)
        group = session.queue[0]
        session.decide([group], ["favorite"])
        favorite = root / "_PhotoSwipe" / "Избранное"
        self.assertEqual(
            {p.name for p in favorite.iterdir()}, {"A7309498.ARW", "A7309498.JPG"}
        )
        self.assertEqual(session.stats["favorite"], 1)
        self.assertEqual(session.undo_depth, 1)
        session.undo()
        self.assertEqual(session.stats["favorite"], 0)
        self.assertEqual(len(session.queue), 1)
        self.assertTrue((root / "A7309498.ARW").exists())
        self.assertTrue((root / "A7309498.JPG").exists())

    def test_sidecars_move_with_group(self) -> None:
        root = self.ws.make_pair()
        (root / "A7309498.xmp").write_text("<xmp/>", encoding="utf-8")
        manager, source = self._manager(root)
        session = manager.open(source)
        session.decide([session.queue[0]], ["trash"])
        trash = root / "_PhotoSwipe" / "Корзина"
        self.assertEqual(
            {p.name for p in trash.iterdir()},
            {"A7309498.ARW", "A7309498.JPG", "A7309498.xmp"},
        )

    def test_second_round_defers_without_moving_and_undo(self) -> None:
        root = self.ws.make_pair()
        manager, source = self._manager(root)
        session = manager.open(source)
        session.decide([session.queue[0]], ["round2"])
        self.assertEqual(session.deferred_count, 1)
        self.assertEqual(len(session.queue), 0)
        self.assertTrue((root / "A7309498.ARW").exists())
        session = session.start_second_round()
        self.assertEqual(session.mode, "second")
        self.assertEqual(len(session.queue), 1)
        with self.assertRaises(SessionError):
            session.decide([session.queue[0]], ["round2"])
        session.decide([session.queue[0]], ["maybe"])
        self.assertEqual(session.stats["maybe"], 1)
        self.assertTrue((root / "_PhotoSwipe" / "Может быть" / "A7309498.JPG").exists())
        session.undo()
        self.assertEqual(session.mode, "second")
        self.assertEqual(len(session.queue), 1)
        self.assertEqual(session.deferred_count, 1)

    def test_compare_batch_is_single_undo_step(self) -> None:
        root = self.ws.make_pair()
        shutil.copy2(root / "A7309498.JPG", root / "IMG_0002.JPG")
        manager, source = self._manager(root)
        session = manager.open(source)
        pair = session.queue[:2]
        session.decide(pair, ["favorite", "trash"])
        self.assertEqual(session.stats["favorite"], 1)
        self.assertEqual(session.stats["trash"], 1)
        self.assertEqual(session.undo_depth, 1)
        session.undo()
        self.assertEqual(session.stats["favorite"], 0)
        self.assertEqual(session.stats["trash"], 0)
        self.assertEqual(len(session.queue), 2)

    def test_name_collisions_get_suffix(self) -> None:
        root = self.ws.base / "library"
        for sub in ("a", "b"):
            folder = root / sub
            folder.mkdir(parents=True)
            shutil.copy2(
                self.ws.make_pair("source") / "A7309498.JPG", folder / "IMG_0001.JPG"
            )
        manager, source = self._manager(root, recursive=True)
        session = manager.open(source)
        session.decide(session.queue[:2], ["favorite", "favorite"])
        names = {p.name for p in (root / "_PhotoSwipe" / "Избранное").iterdir()}
        self.assertEqual(names, {"IMG_0001.JPG", "IMG_0001 (1).JPG"})

    def test_deferred_survives_restart_and_undo_survives_restart(self) -> None:
        root = self.ws.make_pair()
        manager, source = self._manager(root)
        session = manager.open(source)
        session.decide([session.queue[0]], ["round2"])
        # A fresh manager simulates reopening the app.
        manager2 = SessionManager(ConfigStore(self.ws.base / "config.json"))
        reopened = manager2.open(source)
        self.assertEqual(reopened.mode, "first")
        self.assertEqual(len(reopened.queue), 0)
        self.assertEqual(reopened.deferred_count, 1)
        second = reopened.start_second_round()
        self.assertEqual(len(second.queue), 1)
        second.decide([second.queue[0]], ["favorite"])
        manager3 = SessionManager(ConfigStore(self.ws.base / "config.json"))
        reopened3 = manager3.open(source)
        self.assertEqual(reopened3.stats["favorite"], 1)
        self.assertEqual(len(reopened3.queue), 0)
        reopened3.undo()
        self.assertEqual(reopened3.stats["favorite"], 0)
        self.assertTrue((root / "A7309498.ARW").exists())

    def test_undo_history_respects_configured_limit(self) -> None:
        root = self.ws.make_pair()
        shutil.copy2(root / "A7309498.JPG", root / "IMG_0002.JPG")
        shutil.copy2(root / "A7309498.JPG", root / "IMG_0003.JPG")
        config = Config()
        config.behavior.undo_limit = 2
        source = config.add_source(root, recursive=False)
        store = ConfigStore(self.ws.base / "limit-config.json")
        store._config = config
        store.save()
        manager = SessionManager(store)
        session = manager.open(source)
        for verdict in ("favorite", "trash", "maybe"):
            session.decide([session.queue[0]], [verdict])
        self.assertEqual(session.undo_depth, 2)
        self.assertEqual(len(session.state["journal"]), 2)
        session.undo()
        session.undo()
        with self.assertRaises(SessionError):
            session.undo()

    def test_lowering_undo_limit_trims_history(self) -> None:
        root = self.ws.make_pair()
        shutil.copy2(root / "A7309498.JPG", root / "IMG_0002.JPG")
        config = Config()
        config.behavior.undo_limit = 10
        source = config.add_source(root, recursive=False)
        store = ConfigStore(self.ws.base / "trim-config.json")
        store._config = config
        store.save()
        manager = SessionManager(store)
        session = manager.open(source)
        for verdict in ("favorite", "trash"):
            session.decide([session.queue[0]], [verdict])
        self.assertEqual(session.undo_depth, 2)
        session.config.behavior.undo_limit = 1
        session.save()
        self.assertEqual(session.undo_depth, 1)

    def test_summary_reports_processed_and_remaining(self) -> None:
        root = self.ws.make_pair()
        manager, source = self._manager(root)
        session = manager.open(source)
        session.decide([session.queue[0]], ["favorite"])
        summary = manager.summary(source)
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["stats"]["favorite"], 1)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["remaining"], 0)


if __name__ == "__main__":
    unittest.main()
