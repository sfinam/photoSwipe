from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import exifread
import rawpy
from PIL import ExifTags, Image

from . import image_support  # noqa: F401  (registers HEIF/HEIC)
from .formats import (
    IGNORED_DIR_NAMES,
    IMAGE_EXTENSIONS,
    SIDECAR_EXTENSIONS,
    kind_for_ext,
)
from .models import (
    MediaVariant,
    PhotoGroup,
    PhotoMeta,
    parse_capture_datetime,
    sort_groups,
)

ProgressFn = Callable[[str, int, int], None]


@dataclass
class ScanResult:
    groups: list[PhotoGroup]
    meta_cache: dict[str, dict]
    total_files: int = 0
    total_bytes: int = 0
    sidecars: int = 0


def _rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _iter_files(
    root: Path, recursive: bool, ignored: list[Path], progress: ProgressFn | None
):
    stack = [root]
    seen = 0
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except (OSError, PermissionError):
            continue
        for entry in entries:
            try:
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.startswith("."):
                        continue
                    if entry.name in IGNORED_DIR_NAMES:
                        continue
                    if any(_is_within(path, ignore) for ignore in ignored):
                        continue
                    if recursive:
                        stack.append(path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                if entry.name.startswith("._"):
                    continue
                ext = path.suffix.lower()
                if ext not in IMAGE_EXTENSIONS and ext not in SIDECAR_EXTENSIONS:
                    continue
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            seen += 1
            if progress and seen % 200 == 0:
                progress("scan", seen, 0)
            yield path, ext, stat.st_size, stat.st_mtime


def _ratio(value) -> float | None:
    try:
        if hasattr(value, "num") and hasattr(value, "den"):
            if value.den == 0:
                return None
            return float(value.num) / float(value.den)
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        if hasattr(value, "values") and value.values:
            value = value.values[0]
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError, ZeroDivisionError, AttributeError):
        return None


def _int_value(value) -> int | None:
    try:
        if hasattr(value, "values") and value.values:
            value = value.values[0]
        number = int(float(value))
        return number if number > 0 else None
    except (TypeError, ValueError, AttributeError):
        return None


def _exifread_meta(path: Path) -> PhotoMeta:
    meta = PhotoMeta()
    try:
        with path.open("rb") as handle:
            tags = exifread.process_file(handle, details=False)
    except (OSError, Exception):
        return meta
    if not tags:
        return meta

    orientation = _int_value(tags.get("Image Orientation")) or 1
    width = (
        _int_value(tags.get("EXIF ExifImageWidth"))
        or _int_value(tags.get("Image ImageWidth"))
        or 0
    )
    height = (
        _int_value(tags.get("EXIF ExifImageLength"))
        or _int_value(tags.get("Image ImageLength"))
        or 0
    )
    if orientation in (5, 6, 7, 8) and width and height:
        width, height = height, width

    make = str(tags.get("Image Make", "")).strip()
    model = str(tags.get("Image Model", "")).strip()
    if make and model and not model.upper().startswith(make.upper()):
        camera = f"{make} {model}"
    else:
        camera = model or make

    meta.width = width
    meta.height = height
    meta.orientation = orientation
    meta.camera = camera
    meta.lens = str(tags.get("EXIF LensModel", "")).replace("----", "").strip()
    meta.iso = _int_value(tags.get("EXIF ISOSpeedRatings")) or _int_value(
        tags.get("EXIF PhotographicSensitivity")
    )
    meta.exposure = _ratio(tags.get("EXIF ExposureTime"))
    meta.aperture = _ratio(tags.get("EXIF FNumber"))
    meta.focal = _ratio(tags.get("EXIF FocalLength"))
    date_value = (
        tags.get("EXIF DateTimeOriginal")
        or tags.get("EXIF DateTimeDigitized")
        or tags.get("Image DateTime")
    )
    meta.captured_at = parse_capture_datetime(str(date_value)) if date_value else None
    return meta


def _pillow_meta(path: Path) -> PhotoMeta:
    meta = PhotoMeta()
    try:
        with Image.open(path) as image:
            width, height = image.size
            exif = image.getexif()
            orientation = int(exif.get(274) or 1)
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            meta.width, meta.height = width, height
            meta.orientation = orientation
            make = str(exif.get(271, "") or "").strip()
            model = str(exif.get(272, "") or "").strip()
            if make and model and not model.upper().startswith(make.upper()):
                meta.camera = f"{make} {model}"
            else:
                meta.camera = model or make
            meta.captured_at = parse_capture_datetime(
                str(
                    exif.get(36867, "")
                    or exif.get(36868, "")
                    or exif.get(306, "")
                    or ""
                )
            )
            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            except (KeyError, AttributeError):
                exif_ifd = {}
            meta.lens = (
                str(exif_ifd.get(42036, "") or exif.get(42036, "") or "")
                .replace("----", "")
                .strip()
            )
            meta.iso = _int_value(exif_ifd.get(34855) or exif.get(34855))
            meta.exposure = _ratio(exif_ifd.get(33434) or exif.get(33434))
            meta.aperture = _ratio(exif_ifd.get(33437) or exif.get(33437))
            meta.focal = _ratio(exif_ifd.get(37386) or exif.get(37386))
    except (OSError, ValueError, Image.DecompressionBombError):
        return meta
    return meta


def _raw_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with rawpy.imread(str(path)) as raw:
            sizes = raw.sizes
            width = int(sizes.width or sizes.iwidth or sizes.raw_width or 0)
            height = int(sizes.height or sizes.iheight or sizes.raw_height or 0)
            return (width, height) if width and height else None
    except Exception:
        return None


def read_metadata(path: Path) -> PhotoMeta:
    ext = path.suffix.lower()
    if kind_for_ext(ext) == "raw":
        meta = _exifread_meta(path)
        # Some DNG files expose a tiny TIFF preview as ImageWidth/ImageHeight.
        # LibRaw knows the real dimensions, so use it when the EXIF values look
        # implausible for a photograph.
        if not meta.width or not meta.height or max(meta.width, meta.height) < 1000:
            dimensions = _raw_dimensions(path)
            if dimensions:
                width, height = dimensions
                if meta.orientation in (5, 6, 7, 8):
                    width, height = height, width
                meta.width, meta.height = width, height
        if meta.width and meta.height:
            return meta
        # Last-resort TIFF reader for unusual DNGs.
        try:
            fallback = _pillow_meta(path)
        except Exception:
            fallback = PhotoMeta()
        for field in (
            "width",
            "height",
            "orientation",
            "captured_at",
            "camera",
            "lens",
            "iso",
            "exposure",
            "aperture",
            "focal",
        ):
            if not getattr(meta, field) and getattr(fallback, field):
                setattr(meta, field, getattr(fallback, field))
        return meta
    return _pillow_meta(path)


def _primary_index(variants: list[MediaVariant]) -> int:
    def score(variant: MediaVariant) -> tuple[int, int]:
        kind = variant.kind
        if kind == "jpeg":
            rank = 0
        elif kind in {"png", "webp"}:
            rank = 1
        elif kind == "tiff":
            rank = 2
        elif kind == "raw":
            rank = 3
        else:
            rank = 4
        return rank, -variant.size

    return min(range(len(variants)), key=lambda index: score(variants[index]))


def _load_meta_cached(
    group: PhotoGroup,
    root: Path,
    cache: dict[str, dict],
    lock: threading.Lock,
) -> tuple[str, PhotoMeta, dict]:
    variant = group.primary
    rel = variant.rel_path
    cached = cache.get(rel)
    if (
        isinstance(cached, dict)
        and cached.get("size") == variant.size
        and cached.get("mtime") == variant.mtime
        and isinstance(cached.get("meta"), dict)
    ):
        meta = PhotoMeta.from_dict(cached["meta"])
        return rel, meta, cached
    try:
        meta = read_metadata(Path(variant.path))
    except Exception:
        meta = PhotoMeta()
    if not meta.captured_at:
        try:
            meta.captured_at = datetime.fromtimestamp(
                variant.mtime, tz=timezone.utc
            ).isoformat(timespec="seconds")
        except (OSError, ValueError):
            pass
    entry = {"size": variant.size, "mtime": variant.mtime, "meta": meta.to_dict()}
    with lock:
        cache[rel] = entry
    return rel, meta, entry


def scan_source(
    source,
    destinations,
    *,
    sort_by: str = "date",
    meta_cache: dict[str, dict] | None = None,
    progress: ProgressFn | None = None,
) -> ScanResult:
    root = Path(source.path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Папка-источник не найдена")
    ignored = destinations.ignored_scan_roots(source)
    raw_groups: dict[str, list[MediaVariant]] = {}
    sidecar_files: list[MediaVariant] = []
    total_files = 0
    total_bytes = 0

    for path, ext, size, mtime in _iter_files(
        root, source.recursive, ignored, progress
    ):
        rel = _rel_posix(path, root)
        variant = MediaVariant(
            path=str(path),
            rel_path=rel,
            ext=ext,
            size=size,
            mtime=mtime,
        )
        if ext in SIDECAR_EXTENSIONS:
            sidecar_files.append(variant)
            continue
        rel_without_ext = rel[: -len(ext)] if ext else rel
        key = rel_without_ext.casefold()
        raw_groups.setdefault(key, []).append(variant)
        total_files += 1
        total_bytes += size

    groups: list[PhotoGroup] = []
    for key, variants in raw_groups.items():
        variants.sort(key=lambda v: (not v.is_raw, v.ext.casefold(), v.size))
        primary_index = _primary_index(variants)
        rel_path = variants[0].rel_path
        rel_without_ext = (
            rel_path[: -len(variants[0].ext)] if variants[0].ext else rel_path
        )
        rel_dir = str(Path(rel_without_ext).parent.as_posix())
        if rel_dir == ".":
            rel_dir = ""
        stem = Path(rel_without_ext).name
        groups.append(
            PhotoGroup(
                key=key,
                stem=stem,
                rel_dir=rel_dir,
                variants=variants,
                primary_index=primary_index,
            )
        )

    # Attach sidecars to their photo group. Both "NAME.xmp" and
    # "NAME.ARW.xmp" style companions are supported.
    variant_lookup: dict[str, PhotoGroup] = {}
    group_lookup: dict[str, PhotoGroup] = {}
    for group in groups:
        group_lookup[group.key] = group
        for variant in group.variants:
            variant_lookup[variant.rel_path.casefold()] = group
    for sidecar in sidecar_files:
        base = (
            sidecar.rel_path[: -len(sidecar.ext)] if sidecar.ext else sidecar.rel_path
        )
        owner = variant_lookup.get(base.casefold()) or group_lookup.get(base.casefold())
        if owner is not None:
            owner.sidecars.append(sidecar)

    meta_cache = meta_cache if isinstance(meta_cache, dict) else {}
    cache_lock = threading.Lock()
    total = len(groups)
    if progress:
        progress("meta", 0, total)
    if groups:
        workers = min(6, max(1, (os.cpu_count() or 4)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="meta") as pool:
            futures = {
                pool.submit(
                    _load_meta_cached, group, root, meta_cache, cache_lock
                ): group
                for group in groups
            }
            done = 0
            for future in as_completed(futures):
                group = futures[future]
                try:
                    _, meta, _ = future.result()
                except Exception:
                    meta = PhotoMeta()
                group.meta = meta
                done += 1
                if progress and (done % 5 == 0 or done == total):
                    progress("meta", done, total)

    # Keep the cache tidy: only files that are part of this scan remain.
    live_paths = {variant.rel_path for group in groups for variant in group.variants}
    meta_cache = {key: value for key, value in meta_cache.items() if key in live_paths}
    sorted_groups = sort_groups(groups, sort_by)
    return ScanResult(
        groups=sorted_groups,
        meta_cache=meta_cache,
        total_files=total_files,
        total_bytes=total_bytes,
        sidecars=sum(len(g.sidecars) for g in groups),
    )
