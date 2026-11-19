from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .paths import data_dir


def _state_file() -> Path:
    return data_dir() / "ui_state.json"


def load_ui_state() -> dict:
    try:
        raw = json.loads(_state_file().read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_ui_state(state: dict) -> None:
    path = _state_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="ui-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except OSError:
        pass
