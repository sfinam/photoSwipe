from __future__ import annotations

from pathlib import Path

RAW_EXTENSIONS = {
    ".arw": "Sony ARW",
    ".srf": "Sony SRF",
    ".sr2": "Sony SR2",
    ".dng": "Adobe DNG",
    ".cr2": "Canon CR2",
    ".cr3": "Canon CR3",
    ".nef": "Nikon NEF",
    ".nrw": "Nikon NRW",
    ".raf": "Fujifilm RAF",
    ".orf": "Olympus ORF",
    ".rw2": "Panasonic RW2",
    ".pef": "Pentax PEF",
    ".srw": "Samsung SRW",
    ".3fr": "Hasselblad 3FR",
    ".erf": "Epson ERF",
    ".kdc": "Kodak KDC",
    ".mrw": "Minolta MRW",
    ".x3f": "Sigma X3F",
    ".iiq": "Phase One IIQ",
    ".rwl": "Leica RWL",
    ".raw": "RAW",
    ".mef": "Mamiya MEF",
    ".mos": "Leaf MOS",
    ".gpr": "GoPro GPR",
}

RASTER_EXTENSIONS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".jpe": "JPEG",
    ".png": "PNG",
    ".webp": "WebP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".bmp": "BMP",
    ".gif": "GIF",
    ".avif": "AVIF",
    ".heic": "HEIC",
    ".heif": "HEIF",
}

SIDECAR_EXTENSIONS = {
    ".xmp",
    ".aae",
    ".pp3",
    ".dop",
    ".on1",
    ".cos",
}

IMAGE_EXTENSIONS = set(RAW_EXTENSIONS) | set(RASTER_EXTENSIONS)
ALL_EXTENSIONS = IMAGE_EXTENSIONS | SIDECAR_EXTENSIONS

IGNORED_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__MACOSX",
    "@eaDir",
    ".thumbnails",
    ".cache",
    "$RECYCLE.BIN",
    "System Volume Information",
    "_PhotoSwipe",
    "_photoswipe",
}

MAX_EXTENSION_LABEL = {
    ".jpeg": "JPEG",
    ".tiff": "TIFF",
}


def ext_label(ext: str) -> str:
    ext = ext.lower()
    if ext in MAX_EXTENSION_LABEL:
        return MAX_EXTENSION_LABEL[ext]
    if ext in RAW_EXTENSIONS:
        return ext[1:].upper()
    return RASTER_EXTENSIONS.get(ext, ext.lstrip(".").upper() or "FILE")


def kind_for_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in RAW_EXTENSIONS:
        return "raw"
    if ext in (".jpg", ".jpeg", ".jpe"):
        return "jpeg"
    if ext in (".tif", ".tiff"):
        return "tiff"
    if ext == ".png":
        return "png"
    if ext == ".webp":
        return "webp"
    return "raster"


def is_raw(path: str | Path) -> bool:
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def supports_preview(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS
