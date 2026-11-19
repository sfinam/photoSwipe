from __future__ import annotations

import unittest

from photoswipe.config import Destinations, Source
from photoswipe.scanner import read_metadata, scan_source
from tests.helpers import TempWorkspace


class GroupingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = TempWorkspace()
        self.root = self.ws.make_pair()
        (self.root / "A7309498.xmp").write_text("<xmp/>", encoding="utf-8")
        (self.root / "A7309498.ARW.aae").write_text("<aae/>", encoding="utf-8")

    def tearDown(self) -> None:
        self.ws.cleanup()

    def test_raw_and_jpeg_are_one_group_with_sidecars(self) -> None:
        source = Source.create(self.root, recursive=False)
        result = scan_source(source, Destinations())
        self.assertEqual(len(result.groups), 1)
        group = result.groups[0]
        self.assertEqual(group.format_summary, "ARW + JPEG")
        self.assertEqual(
            {v.name for v in group.variants}, {"A7309498.ARW", "A7309498.JPG"}
        )
        self.assertEqual(
            {s.name for s in group.sidecars}, {"A7309498.xmp", "A7309498.ARW.aae"}
        )
        self.assertEqual(group.primary.name, "A7309498.JPG")
        self.assertEqual(group.meta.camera, "SONY ILCE-7M3")
        self.assertEqual((group.meta.width, group.meta.height), (3936, 2624))
        self.assertEqual(group.meta.iso, 3200)
        self.assertIsNotNone(group.meta.captured_at)

    def test_same_stem_in_different_folders_stays_separate(self) -> None:
        nested = self.root / "other"
        nested.mkdir()
        (nested / "A7309498.JPG").write_bytes((self.root / "A7309498.JPG").read_bytes())
        result = scan_source(Source.create(self.root, recursive=True), Destinations())
        self.assertEqual(len(result.groups), 2)
        self.assertEqual(len({group.key for group in result.groups}), 2)

    def test_non_recursive_scan_stays_at_root(self) -> None:
        nested = self.root / "other"
        nested.mkdir()
        (nested / "IMG_9.JPG").write_bytes((self.root / "A7309498.JPG").read_bytes())
        result = scan_source(Source.create(self.root, recursive=False), Destinations())
        self.assertEqual(len(result.groups), 1)

    def test_raw_only_metadata_uses_exifread(self) -> None:
        meta = read_metadata(self.root / "A7309498.ARW")
        self.assertEqual(meta.camera, "SONY ILCE-7M3")
        self.assertGreaterEqual(meta.width, 3900)
        self.assertGreaterEqual(meta.height, 2600)
        self.assertEqual(meta.iso, 3200)
        self.assertIsNotNone(meta.captured_at)

    def test_name_sort_is_natural_and_total(self) -> None:
        root = self.ws.base / "names"
        root.mkdir()
        for name in ("IMG_10.JPG", "IMG_2.JPG", "A.JPG"):
            (root / name).write_bytes((self.root / "A7309498.JPG").read_bytes())
        result = scan_source(Source.create(root, recursive=False), Destinations())
        self.assertEqual(
            [g.display_name for g in result.groups], ["A", "IMG_2", "IMG_10"]
        )

    def test_destination_folder_is_ignored(self) -> None:
        destination = self.root / "_PhotoSwipe" / "Избранное"
        destination.mkdir(parents=True)
        (destination / "OLD.JPG").write_bytes((self.root / "A7309498.JPG").read_bytes())
        result = scan_source(Source.create(self.root, recursive=True), Destinations())
        self.assertEqual(len(result.groups), 1)


if __name__ == "__main__":
    unittest.main()
