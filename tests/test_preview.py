from __future__ import annotations

import unittest

from PIL import Image

from photoswipe.config import Destinations, Source
from photoswipe.media import PreviewService
from photoswipe.scanner import scan_source
from tests.helpers import TempWorkspace


class PreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = TempWorkspace()
        self.root = self.ws.make_pair()
        self.group = scan_source(
            Source.create(self.root, recursive=False), Destinations()
        ).groups[0]
        self.service = PreviewService()

    def tearDown(self) -> None:
        self.ws.cleanup()

    def test_jpeg_preview(self) -> None:
        result = self.service.preview(
            self.group, self.group.primary_index, max_side=1200
        )
        self.assertTrue(result.path.endswith(".jpg"))
        with Image.open(result.path) as image:
            self.assertLessEqual(max(image.size), 1200)
            self.assertGreater(image.width, 1000)

    def test_raw_preview_uses_embedded_jpeg(self) -> None:
        raw_index = next(
            i for i, variant in enumerate(self.group.variants) if variant.is_raw
        )
        result = self.service.preview(self.group, raw_index, max_side=1200)
        with Image.open(result.path) as image:
            self.assertLessEqual(max(image.size), 1200)
            self.assertEqual(image.mode, "RGB")
        self.assertGreater(result.width, 700)
        second = self.service.preview(self.group, raw_index, max_side=1200)
        self.assertTrue(second.from_cache)

    def test_cache_is_clearable(self) -> None:
        self.service.preview(self.group, self.group.primary_index, max_side=800)
        self.assertGreater(self.service.cache_size(), 0)
        self.service.clear_cache()
        self.assertEqual(self.service.cache_size(), 0)


if __name__ == "__main__":
    unittest.main()
