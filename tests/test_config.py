from __future__ import annotations

import unittest

from photoswipe.config import (
    Behavior,
    Config,
    ConfigStore,
    Destinations,
    Source,
    canonical_combo,
    source_id,
)
from tests.helpers import TempWorkspace


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = TempWorkspace()

    def tearDown(self) -> None:
        self.ws.cleanup()

    def test_source_id_is_stable_and_path_based(self) -> None:
        source = Source.create(self.ws.base, recursive=False)
        self.assertEqual(source.id, source_id(self.ws.base))
        self.assertEqual(source.id, Source.create(self.ws.base).id)

    def test_raw_display_shortcut_default(self) -> None:
        self.assertEqual(Config().shortcuts["toggleRaw"], ["KeyT"])

    def test_canonical_combo(self) -> None:
        self.assertEqual(canonical_combo("Shift+KeyR"), "Shift+KeyR")
        self.assertEqual(canonical_combo("KeyD"), "KeyD")
        with self.assertRaises(ValueError):
            canonical_combo("Hyper+KeyA")
        with self.assertRaises(ValueError):
            canonical_combo("KeyA+KeyB")

    def test_raw_view_mode_migrates_from_legacy_flag(self) -> None:
        self.assertEqual(
            Behavior.from_dict({"raw_full_decode": True}).raw_view_mode, "full"
        )
        self.assertEqual(
            Behavior.from_dict({"raw_view_mode": "thumbnail"}).raw_view_mode,
            "thumbnail",
        )
        self.assertEqual(Behavior.from_dict({}).raw_view_mode, "jpeg")

    def test_destinations_beside_and_custom(self) -> None:
        source = Source.create(self.ws.base, name="Свадьба")
        dest = Destinations(mode="beside", beside_dir_name="_Sorted")
        paths = dest.for_source(source)
        self.assertEqual(paths["favorite"], self.ws.base / "_Sorted" / "Избранное")
        self.assertEqual(paths["trash"], self.ws.base / "_Sorted" / "Корзина")
        custom = Destinations(
            mode="custom", custom_root=str(self.ws.base / "out"), add_source_name=True
        )
        paths = custom.for_source(source)
        self.assertEqual(
            paths["favorite"], self.ws.base / "out" / "Свадьба" / "Избранное"
        )

    def test_destination_validation_rejects_duplicates(self) -> None:
        dest = Destinations(favorite="A", trash="a", maybe="B")
        with self.assertRaises(ValueError):
            dest.validate()

    def test_store_round_trip_preserves_shortcuts_and_sources(self) -> None:
        path = self.ws.base / "config.json"
        config = Config()
        source = config.add_source(self.ws.base)
        config.shortcuts["favorite"] = ["KeyF"]
        store = ConfigStore(path)
        store.save(config)
        loaded = ConfigStore(path).load()
        self.assertEqual(len(loaded.sources), 1)
        self.assertEqual(loaded.sources[0].path, source.path)
        self.assertEqual(loaded.shortcuts["favorite"], ["KeyF"])
        self.assertTrue(loaded.destinations.favorite)


if __name__ == "__main__":
    unittest.main()
