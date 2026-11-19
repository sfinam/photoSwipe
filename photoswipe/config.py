from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .i18n import default_folder_names, normalize_language, system_language, tr
from .paths import config_file, ensure_dirs

MODIFIERS = ("Ctrl", "Alt", "Shift", "Meta")
_CODE_RE = re.compile(
    r"^(?:Key[A-Z]|Digit[0-9]|F(?:[1-9]|1[0-2])|"
    r"Arrow(?:Up|Down|Left|Right)|"
    r"Numpad(?:[0-9]|Add|Subtract|Multiply|Divide|Decimal|Enter)|"
    r"(?:Space|Escape|Enter|Tab|Backspace|Delete|Insert|Home|End|PageUp|PageDown|"
    r"Minus|Equal|BracketLeft|BracketRight|Backslash|Semicolon|Quote|Comma|Period|"
    r"Slash|Backquote|CapsLock|ContextMenu|PrintScreen|Pause|NumLock|ScrollLock))$"
)

SHORTCUT_ACTIONS = (
    "favorite",
    "trash",
    "maybe",
    "round2",
    "undo",
    "compare",
    "toggleRaw",
    "zoomIn",
    "zoomOut",
    "rotateCw",
    "rotateCcw",
    "resetView",
    "fullscreen",
    "help",
)

CONTROLLER_ACTIONS = (
    "favorite",
    "trash",
    "maybe",
    "round2",
    "undo",
    "compare",
    "zoomIn",
    "zoomOut",
    "rotateCw",
    "rotateCcw",
)

DEFAULT_SHORTCUTS: dict[str, list[str]] = {
    "favorite": ["ArrowRight", "KeyD"],
    "trash": ["ArrowLeft", "KeyA"],
    "maybe": ["ArrowDown", "KeyS"],
    "round2": ["ArrowUp", "KeyW"],
    "undo": ["KeyZ"],
    "compare": ["KeyC"],
    "toggleRaw": ["KeyT"],
    "zoomIn": ["Equal", "NumpadAdd"],
    "zoomOut": ["Minus", "NumpadSubtract"],
    "rotateCw": ["KeyR"],
    "rotateCcw": ["Shift+KeyR"],
    "resetView": ["Digit0"],
    "fullscreen": ["KeyF"],
    "help": ["Shift+Slash", "F1"],
}

DEFAULT_CONTROLLER_MAPPINGS: dict[str, list[int]] = {
    "favorite": [0, 15],
    "trash": [1, 14],
    "maybe": [3, 13],
    "round2": [2, 12],
    "undo": [8],
    "compare": [9],
    "zoomIn": [7],
    "zoomOut": [6],
    "rotateCw": [5],
    "rotateCcw": [4],
}

SAFE_FOLDER_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_id(path: str | Path) -> str:
    normalized = os.path.normcase(str(Path(path).expanduser().resolve()))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def safe_folder_name(value: str, fallback: str) -> str:
    cleaned = SAFE_FOLDER_RE.sub("_", str(value or "").strip()).strip(" .")
    return cleaned[:120] or fallback


def safe_source_name(value: str, fallback: str) -> str:
    return safe_folder_name(value, fallback)


def canonical_combo(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(tr("Empty shortcut"))
    pieces = [p.strip() for p in value.split("+")]
    code = pieces.pop()
    if not _CODE_RE.match(code):
        raise ValueError(tr("Unsupported key: {key}", key=code or "—"))
    seen: list[str] = []
    for modifier in pieces:
        if modifier not in MODIFIERS:
            raise ValueError(tr("Unknown modifier: {modifier}", modifier=modifier))
        if modifier in seen:
            raise ValueError(tr("Modifier repeated: {modifier}", modifier=modifier))
        seen.append(modifier)
    ordered = [m for m in MODIFIERS if m in seen]
    return "+".join([*ordered, code])


def combo_parts(value: str) -> tuple[frozenset[str], str]:
    pieces = [p.strip() for p in value.split("+")]
    code = pieces.pop()
    return frozenset(pieces), code


@dataclass
class Source:
    id: str
    path: str
    name: str
    recursive: bool = True
    added_at: str = field(default_factory=now_iso)

    @classmethod
    def create(
        cls, path: str | Path, recursive: bool = True, name: str | None = None
    ) -> "Source":
        resolved = str(Path(path).expanduser().resolve())
        fallback = Path(resolved).name or resolved
        return cls(
            id=source_id(resolved),
            path=resolved,
            name=safe_source_name(name or fallback, fallback),
            recursive=recursive,
            added_at=now_iso(),
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Source | None":
        path = raw.get("path")
        if not isinstance(path, str) or not path.strip():
            return None
        try:
            resolved = str(Path(path).expanduser().resolve())
        except OSError:
            return None
        fallback = Path(resolved).name or resolved
        return cls(
            id=source_id(resolved),
            path=resolved,
            name=safe_source_name(str(raw.get("name") or fallback), fallback),
            recursive=raw.get("recursive", True) is not False,
            added_at=str(raw.get("added_at") or now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "recursive": self.recursive,
            "added_at": self.added_at,
        }

    @property
    def exists(self) -> bool:
        return Path(self.path).is_dir()


@dataclass
class Destinations:
    mode: str = "beside"  # beside | custom
    beside_dir_name: str = "_PhotoSwipe"
    custom_root: str = str(Path.home() / "Pictures" / "PhotoSwipe")
    add_source_name: bool = True
    favorite: str = "Избранное"
    trash: str = "Корзина"
    maybe: str = "Может быть"

    @classmethod
    def localized(cls, language: str | None = None) -> "Destinations":
        names = default_folder_names(language)
        return cls(
            favorite=names["favorite"],
            trash=names["trash"],
            maybe=names["maybe"],
        )

    @classmethod
    def from_dict(
        cls, raw: dict[str, Any] | None, language: str | None = None
    ) -> "Destinations":
        raw = raw or {}
        folders = raw.get("folders") if isinstance(raw.get("folders"), dict) else {}
        default = cls.localized(language)
        return cls(
            mode="custom" if raw.get("mode") == "custom" else "beside",
            beside_dir_name=safe_folder_name(
                raw.get("beside_dir_name", default.beside_dir_name),
                default.beside_dir_name,
            ),
            custom_root=str(
                Path(str(raw.get("custom_root") or default.custom_root))
                .expanduser()
                .resolve()
            ),
            add_source_name=raw.get("add_source_name", True) is not False,
            favorite=safe_folder_name(
                folders.get("favorite", default.favorite), default.favorite
            ),
            trash=safe_folder_name(folders.get("trash", default.trash), default.trash),
            maybe=safe_folder_name(folders.get("maybe", default.maybe), default.maybe),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "beside_dir_name": self.beside_dir_name,
            "custom_root": self.custom_root,
            "add_source_name": self.add_source_name,
            "folders": {
                "favorite": self.favorite,
                "trash": self.trash,
                "maybe": self.maybe,
            },
        }

    def base_dir(self, source: Source) -> Path:
        if self.mode == "custom":
            root = Path(self.custom_root).expanduser()
            return (
                root / safe_source_name(source.name, Path(source.path).name)
                if self.add_source_name
                else root
            )
        return Path(source.path) / self.beside_dir_name

    def for_source(self, source: Source) -> dict[str, Path]:
        base = self.base_dir(source)
        return {
            "favorite": base / self.favorite,
            "trash": base / self.trash,
            "maybe": base / self.maybe,
        }

    def ignored_scan_roots(self, source: Source) -> list[Path]:
        roots = [self.base_dir(source)]
        custom = Path(self.custom_root).expanduser()
        if custom not in roots:
            roots.append(custom)
        return roots

    def description(self, source: Source | None = None) -> str:
        if source is not None:
            base = self.base_dir(source)
            return str(base)
        if self.mode == "beside":
            return tr("Next to each folder: {name}", name=self.beside_dir_name)
        suffix = tr(" / <source name>") if self.add_source_name else ""
        return f"{self.custom_root}{suffix}"

    def validate(self) -> None:
        if self.mode not in {"beside", "custom"}:
            raise ValueError(tr("Unknown destination mode"))
        if not self.beside_dir_name.strip():
            raise ValueError(tr("Enter a folder name for results"))
        if self.mode == "custom" and not self.custom_root.strip():
            raise ValueError(tr("Choose a shared folder for results"))
        names = [self.favorite, self.trash, self.maybe]
        if not all(name.strip() for name in names):
            raise ValueError(tr("Folder names cannot be empty"))
        if len({name.casefold() for name in names}) != 3:
            raise ValueError(
                tr("Favorites, Trash and Maybe folders must have different names")
            )


@dataclass
class ControllerSettings:
    enabled: bool = True
    deadzone: float = 0.25
    vibration: bool = True
    mappings: dict[str, list[int]] = field(
        default_factory=lambda: {
            k: list(v) for k, v in DEFAULT_CONTROLLER_MAPPINGS.items()
        }
    )

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "ControllerSettings":
        raw = raw or {}
        mappings: dict[str, list[int]] = {}
        raw_map = raw.get("mappings") if isinstance(raw.get("mappings"), dict) else {}
        for action in CONTROLLER_ACTIONS:
            values = raw_map.get(action)
            source = (
                values
                if isinstance(values, list)
                else DEFAULT_CONTROLLER_MAPPINGS[action]
            )
            cleaned = sorted(
                {
                    int(v)
                    for v in source
                    if isinstance(v, (int, float)) and 0 <= int(v) <= 31
                }
            )[:4]
            mappings[action] = cleaned
        try:
            deadzone = float(raw.get("deadzone", 0.25))
        except (TypeError, ValueError):
            deadzone = 0.25
        return cls(
            enabled=raw.get("enabled", True) is not False,
            deadzone=min(0.8, max(0.0, deadzone)),
            vibration=raw.get("vibration", True) is not False,
            mappings=mappings,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "deadzone": self.deadzone,
            "vibration": self.vibration,
            "mappings": {k: list(v) for k, v in self.mappings.items()},
        }


@dataclass
class Behavior:
    sort_by: str = "date"  # date | name
    recursive_default: bool = True
    animations: bool = True
    raw_view_mode: str = "jpeg"  # jpeg | thumbnail | full
    undo_limit: int = 120

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "Behavior":
        raw = raw or {}
        mode = raw.get("raw_view_mode")
        if mode not in {"jpeg", "thumbnail", "full"}:
            mode = "full" if raw.get("raw_full_decode") is True else "jpeg"
        try:
            undo_limit = int(raw.get("undo_limit", 120))
        except (TypeError, ValueError):
            undo_limit = 120
        undo_limit = min(1000, max(1, undo_limit))
        return cls(
            sort_by="name" if raw.get("sort_by") == "name" else "date",
            recursive_default=raw.get("recursive_default", True) is not False,
            animations=raw.get("animations", True) is not False,
            raw_view_mode=mode,
            undo_limit=undo_limit,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sort_by": self.sort_by,
            "recursive_default": self.recursive_default,
            "animations": self.animations,
            "raw_view_mode": self.raw_view_mode,
            "undo_limit": self.undo_limit,
        }


@dataclass
class Config:
    version: int = 1
    language: str = field(default_factory=system_language)
    sources: list[Source] = field(default_factory=list)
    destinations: Destinations = field(default_factory=Destinations)
    shortcuts: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_SHORTCUTS.items()}
    )
    controller: ControllerSettings = field(default_factory=ControllerSettings)
    behavior: Behavior = field(default_factory=Behavior)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "Config":
        raw = raw or {}
        language = normalize_language(raw.get("language"))
        raw_destinations = raw.get("destinations")
        if isinstance(raw_destinations, dict):
            destinations = Destinations.from_dict(raw_destinations, language)
        else:
            destinations = Destinations.localized(language)
        sources: list[Source] = []
        seen: set[str] = set()
        for item in (
            raw.get("sources", []) if isinstance(raw.get("sources"), list) else []
        ):
            if not isinstance(item, dict):
                continue
            source = Source.from_dict(item)
            if source is None or source.path in seen:
                continue
            seen.add(source.path)
            sources.append(source)

        shortcuts: dict[str, list[str]] = {}
        used: set[str] = set()
        raw_shortcuts = (
            raw.get("shortcuts") if isinstance(raw.get("shortcuts"), dict) else {}
        )
        for action in SHORTCUT_ACTIONS:
            supplied = raw_shortcuts.get(action)
            values = (
                supplied if isinstance(supplied, list) else DEFAULT_SHORTCUTS[action]
            )
            bindings: list[str] = []
            for item in values[:4]:
                try:
                    value = canonical_combo(item)
                except ValueError:
                    continue
                if value not in used:
                    used.add(value)
                    bindings.append(value)
            shortcuts[action] = bindings

        return cls(
            version=1,
            language=language,
            sources=sources,
            destinations=destinations,
            shortcuts=shortcuts,
            controller=ControllerSettings.from_dict(raw.get("controller")),
            behavior=Behavior.from_dict(raw.get("behavior")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "language": self.language,
            "sources": [s.to_dict() for s in self.sources],
            "destinations": self.destinations.to_dict(),
            "shortcuts": {k: list(v) for k, v in self.shortcuts.items()},
            "controller": self.controller.to_dict(),
            "behavior": self.behavior.to_dict(),
        }

    def source(self, source_id_value: str) -> Source | None:
        return next((s for s in self.sources if s.id == source_id_value), None)

    def shortcut_for(self, combo: str) -> str | None:
        for action, bindings in self.shortcuts.items():
            if combo in bindings:
                return action
        return None

    def add_source(self, path: str | Path, recursive: bool | None = None) -> Source:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError(tr("Folder not found"))
        existing = next((s for s in self.sources if Path(s.path) == resolved), None)
        if existing:
            return existing
        source = Source.create(
            resolved,
            self.behavior.recursive_default if recursive is None else recursive,
        )
        self.sources.append(source)
        return source

    def remove_source(self, source_id_value: str) -> bool:
        before = len(self.sources)
        self.sources = [s for s in self.sources if s.id != source_id_value]
        return len(self.sources) != before


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_file()
        self._config: Config | None = None

    def load(self) -> Config:
        if self._config is not None:
            return self._config
        ensure_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            language = system_language()
            self._config = Config(
                language=language,
                destinations=Destinations.localized(language),
            )
            self.save(self._config)
            return self._config
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        self._config = Config.from_dict(raw)
        return self._config

    def save(self, config: Config | None = None) -> Config:
        if config is not None:
            self._config = config
        if self._config is None:
            raise RuntimeError(tr("Configuration is not loaded"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        clean = Config.from_dict(self._config.to_dict())
        self._config = clean
        payload = json.dumps(clean.to_dict(), ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(
            prefix="config-", suffix=".json", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, self.path)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return clean
