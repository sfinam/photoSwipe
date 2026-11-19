from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .i18n import decimal_separator, tr


def format_bytes(value: int | float) -> str:
    value = float(value or 0)
    if value <= 0:
        return f"0 {tr('B')}"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    separator = decimal_separator()
    number = f"{int(value)}" if index == 0 else f"{value:.1f}".replace(".", separator)
    return f"{number} {tr(units[index])}"


def reveal_in_file_manager(path: str | Path) -> bool:
    target = Path(path).expanduser()
    if not target.exists():
        target = target.parent
    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except (OSError, AttributeError):
        return False
