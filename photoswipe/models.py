from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .formats import RAW_EXTENSIONS, ext_label, kind_for_ext
from .i18n import format_date, tr


def group_id(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def natural_key(value: str) -> list[Any]:
    return [
        (0, int(piece)) if piece.isdigit() else (1, piece.casefold())
        for piece in re.split(r"(\d+)", str(value))
        if piece
    ]


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def pretty_shutter(value: float | None) -> str:
    if not value:
        return ""
    if value >= 1:
        return f"{value:g} {tr('s')}"
    return f"1/{round(1 / value)} {tr('s')}"


def pretty_fnumber(value: float | None) -> str:
    return f"f/{value:g}" if value else ""


def pretty_focal(value: float | None) -> str:
    return f"{value:g} {tr('mm')}" if value else ""


def parse_capture_datetime(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y:%m:%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def format_capture_date(iso_value: str | None) -> str:
    return format_date(iso_value)


@dataclass
class MediaVariant:
    path: str
    rel_path: str
    ext: str
    size: int
    mtime: float

    @property
    def name(self) -> str:
        return Path(self.path).name

    @property
    def kind(self) -> str:
        return kind_for_ext(self.ext)

    @property
    def label(self) -> str:
        return ext_label(self.ext)

    @property
    def is_raw(self) -> bool:
        return self.ext.lower() in RAW_EXTENSIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rel_path": self.rel_path,
            "ext": self.ext,
            "size": self.size,
            "mtime": self.mtime,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MediaVariant":
        return cls(
            path=str(raw["path"]),
            rel_path=str(raw.get("rel_path", Path(str(raw["path"])).name)),
            ext=str(raw.get("ext") or Path(str(raw["path"])).suffix).lower(),
            size=int(raw.get("size", 0)),
            mtime=float(raw.get("mtime", 0)),
        )


@dataclass
class PhotoMeta:
    width: int = 0
    height: int = 0
    orientation: int = 1
    captured_at: str | None = None
    camera: str = ""
    lens: str = ""
    iso: int | None = None
    exposure: float | None = None
    aperture: float | None = None
    focal: float | None = None

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width} × {self.height}"
        return ""

    @property
    def subtitle(self) -> str:
        bits: list[str] = []
        if self.camera:
            bits.append(self.camera)
        if self.iso:
            bits.append(f"ISO {self.iso}")
        if self.exposure:
            bits.append(pretty_shutter(self.exposure))
        if self.aperture:
            bits.append(pretty_fnumber(self.aperture))
        if self.focal:
            bits.append(pretty_focal(self.focal))
        return " · ".join(bits)

    @property
    def date_label(self) -> str:
        return format_capture_date(self.captured_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "orientation": self.orientation,
            "captured_at": self.captured_at,
            "camera": self.camera,
            "lens": self.lens,
            "iso": self.iso,
            "exposure": self.exposure,
            "aperture": self.aperture,
            "focal": self.focal,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "PhotoMeta":
        raw = raw or {}
        return cls(
            width=int(raw.get("width") or 0),
            height=int(raw.get("height") or 0),
            orientation=int(raw.get("orientation") or 1),
            captured_at=raw.get("captured_at"),
            camera=str(raw.get("camera") or ""),
            lens=str(raw.get("lens") or ""),
            iso=int(raw["iso"]) if raw.get("iso") else None,
            exposure=_safe_float(raw.get("exposure")),
            aperture=_safe_float(raw.get("aperture")),
            focal=_safe_float(raw.get("focal")),
        )


@dataclass
class PhotoGroup:
    key: str
    stem: str
    rel_dir: str
    variants: list[MediaVariant]
    sidecars: list[MediaVariant] = field(default_factory=list)
    meta: PhotoMeta = field(default_factory=PhotoMeta)
    primary_index: int = 0

    @property
    def id(self) -> str:
        return group_id(self.key)

    @property
    def primary(self) -> MediaVariant:
        return self.variants[min(self.primary_index, len(self.variants) - 1)]

    @property
    def display_name(self) -> str:
        return self.stem if self.stem else Path(self.primary.path).stem

    @property
    def total_size(self) -> int:
        return sum(v.size for v in self.variants) + sum(s.size for s in self.sidecars)

    @property
    def format_summary(self) -> str:
        seen: list[str] = []
        for variant in self.variants:
            if variant.label not in seen:
                seen.append(variant.label)
        return " + ".join(seen)

    @property
    def sort_time(self) -> str:
        return (
            self.meta.captured_at
            or datetime.fromtimestamp(self.primary.mtime, tz=timezone.utc).isoformat()
        )

    @property
    def has_raw(self) -> bool:
        return any(v.is_raw for v in self.variants)

    @property
    def files(self) -> list[MediaVariant]:
        return [*self.variants, *self.sidecars]

    def variant_at(self, index: int) -> MediaVariant:
        return self.variants[max(0, min(index, len(self.variants) - 1))]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "stem": self.stem,
            "rel_dir": self.rel_dir,
            "variants": [v.to_dict() for v in self.variants],
            "sidecars": [s.to_dict() for s in self.sidecars],
            "meta": self.meta.to_dict(),
            "primary_index": self.primary_index,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PhotoGroup":
        variants = [MediaVariant.from_dict(item) for item in raw.get("variants", [])]
        if not variants:
            raise ValueError(tr("Group has no files"))
        return cls(
            key=str(raw["key"]),
            stem=str(raw.get("stem") or Path(variants[0].path).stem),
            rel_dir=str(raw.get("rel_dir") or ""),
            variants=variants,
            sidecars=[MediaVariant.from_dict(item) for item in raw.get("sidecars", [])],
            meta=PhotoMeta.from_dict(raw.get("meta")),
            primary_index=int(raw.get("primary_index") or 0),
        )


def sort_groups(
    groups: Iterable[PhotoGroup], sort_by: str = "date"
) -> list[PhotoGroup]:
    items = list(groups)
    if sort_by == "name":
        return sorted(items, key=lambda g: natural_key(f"{g.rel_dir}/{g.display_name}"))
    return sorted(
        items,
        key=lambda g: (g.sort_time, natural_key(g.display_name), g.rel_dir.casefold()),
    )
