from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ARW = ROOT / "A7309498.ARW"
SAMPLE_JPG = ROOT / "A7309498.JPG"


class TempWorkspace:
    def __init__(self) -> None:
        workspace = ROOT / ".tmp"
        workspace.mkdir(exist_ok=True)
        self.base = Path(tempfile.mkdtemp(prefix="photoswipe-test-", dir=workspace))
        self.old_data = os.environ.get("PHOTOSWIPE_DATA_DIR")
        self.old_cache = os.environ.get("PHOTOSWIPE_CACHE_DIR")
        os.environ["PHOTOSWIPE_DATA_DIR"] = str(self.base / "data")
        os.environ["PHOTOSWIPE_CACHE_DIR"] = str(self.base / "cache")

    def cleanup(self) -> None:
        if self.old_data is None:
            os.environ.pop("PHOTOSWIPE_DATA_DIR", None)
        else:
            os.environ["PHOTOSWIPE_DATA_DIR"] = self.old_data
        if self.old_cache is None:
            os.environ.pop("PHOTOSWIPE_CACHE_DIR", None)
        else:
            os.environ["PHOTOSWIPE_CACHE_DIR"] = self.old_cache
        shutil.rmtree(self.base, ignore_errors=True)

    def make_pair(
        self,
        folder: str = "library",
        names: tuple[str, str] = ("A7309498.ARW", "A7309498.JPG"),
    ) -> Path:
        root = self.base / folder
        root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SAMPLE_ARW, root / names[0])
        shutil.copy2(SAMPLE_JPG, root / names[1])
        return root

    def copy_jpeg(self, folder: str = "library", name: str = "IMG_0002.JPG") -> Path:
        root = self.base / folder
        root.mkdir(parents=True, exist_ok=True)
        target = root / name
        shutil.copy2(SAMPLE_JPG, target)
        return target
