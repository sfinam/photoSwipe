from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

APP_NAME = "PhotoSwipe"
APP_SLUG = "photoswipe"


def _override() -> Path | None:
    value = os.environ.get("PHOTOSWIPE_DATA_DIR")
    return Path(value).expanduser().resolve() if value else None


def data_dir() -> Path:
    override = _override()
    if override:
        return override
    return Path(user_data_dir(APP_NAME, appauthor=False, roaming=False))


def cache_dir() -> Path:
    value = os.environ.get("PHOTOSWIPE_CACHE_DIR")
    if value:
        return Path(value).expanduser().resolve()
    override = _override()
    if override:
        return override / "cache"
    return Path(user_cache_dir(APP_NAME, appauthor=False))


def ensure_dirs() -> None:
    for directory in (
        data_dir(),
        cache_dir(),
        cache_dir() / "previews",
        cache_dir() / "raw",
        data_dir() / "sessions",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def config_file() -> Path:
    return data_dir() / "config.json"


def sessions_dir() -> Path:
    return data_dir() / "sessions"
