from __future__ import annotations

import hashlib
import io
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import rawpy
from PIL import Image, ImageOps

from . import image_support  # noqa: F401  (registers HEIF/HEIC)
from .models import PhotoGroup, MediaVariant
from .paths import cache_dir, ensure_dirs

_BACKGROUND = (20, 22, 26)


@dataclass(frozen=True)
class PreviewResult:
    path: str
    width: int
    height: int
    from_cache: bool


def _hash_key(*parts: object) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(str(part).encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
    return digest.hexdigest()


def _load_raster(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (*_BACKGROUND, 255))
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        return image.copy()


def _load_raw(path: Path, full_decode: bool) -> Image.Image:
    with rawpy.imread(str(path)) as raw:
        if not full_decode:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    with Image.open(io.BytesIO(thumb.data)) as image:
                        return image.convert("RGB").copy()
                # PPM and other simple formats can be opened by Pillow too.
                with Image.open(io.BytesIO(thumb.data)) as image:
                    return image.convert("RGB").copy()
            except Exception:
                pass
        array = raw.postprocess(
            use_camera_wb=True,
            use_auto_wb=False,
            half_size=not full_decode,
            output_bps=8,
            no_auto_bright=False,
        )
        return Image.fromarray(array).convert("RGB")


class PreviewService:
    """Creates and caches JPEG previews for regular images and RAW files.

    Embedded camera previews are used for RAW by default (fast culling). If a
    file has no embedded preview, or full RAW decoding is enabled, LibRaw is
    used to demosaic the image.
    """

    def __init__(self, cache_root: Path | None = None) -> None:
        ensure_dirs()
        self.cache_root = Path(cache_root) if cache_root else cache_dir()
        self.preview_dir = self.cache_root / "previews"
        self.raw_dir = self.cache_root / "raw"
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _raw_base(self, variant: MediaVariant, full_decode: bool) -> Path:
        key = _hash_key(
            variant.path,
            variant.mtime,
            variant.size,
            "full" if full_decode else "embedded",
        )
        destination = self.raw_dir / f"{key}.jpg"
        if destination.exists() and destination.stat().st_size > 512:
            return destination
        lock = self._lock_for(str(destination))
        with lock:
            if destination.exists() and destination.stat().st_size > 512:
                return destination
            image = _load_raw(Path(variant.path), full_decode)
            # Keep enough pixels for 1:1 viewing on a normal desktop monitor.
            image.thumbnail((3200, 3200), Image.Resampling.LANCZOS)
            self._save_jpeg(image, destination, quality=93)
        return destination

    @staticmethod
    def _save_jpeg(image: Image.Image, destination: Path, quality: int) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix="preview-", suffix=".jpg", dir=destination.parent
        )
        os.close(fd)
        try:
            image.save(
                tmp, format="JPEG", quality=quality, optimize=True, progressive=True
            )
            os.replace(tmp, destination)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def preview(
        self,
        group: PhotoGroup,
        variant_index: int | None = None,
        *,
        max_side: int = 2200,
        full_raw_decode: bool = False,
    ) -> PreviewResult:
        variant = group.variant_at(
            variant_index if variant_index is not None else group.primary_index
        )
        source = Path(variant.path)
        if not source.is_file():
            raise FileNotFoundError(variant.name)
        max_side = max(480, min(int(max_side), 4096))
        key = _hash_key(
            variant.path,
            variant.mtime,
            variant.size,
            max_side,
            "full" if full_raw_decode else "fast",
        )
        destination = self.preview_dir / f"{key}.jpg"
        if destination.exists() and destination.stat().st_size > 256:
            try:
                with Image.open(destination) as image:
                    return PreviewResult(
                        str(destination), image.width, image.height, True
                    )
            except OSError:
                destination.unlink(missing_ok=True)

        lock = self._lock_for(str(destination))
        with lock:
            if destination.exists() and destination.stat().st_size > 256:
                try:
                    with Image.open(destination) as image:
                        return PreviewResult(
                            str(destination), image.width, image.height, True
                        )
                except OSError:
                    destination.unlink(missing_ok=True)
            if variant.is_raw:
                base_path = self._raw_base(variant, full_raw_decode)
                with Image.open(base_path) as base:
                    image = base.convert("RGB").copy()
            else:
                image = _load_raster(source)
            if max(image.size) > max_side:
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            self._save_jpeg(image, destination, quality=90)
            return PreviewResult(str(destination), image.width, image.height, False)

    def cache_size(self) -> int:
        total = 0
        for root in (self.preview_dir, self.raw_dir):
            if not root.exists():
                continue
            for path in root.rglob("*.jpg"):
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
        return total

    def clear_cache(self) -> None:
        for root in (self.preview_dir, self.raw_dir):
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    try:
                        path.unlink()
                    except OSError:
                        pass
