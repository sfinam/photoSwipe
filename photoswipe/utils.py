from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def format_bytes(value: int | float) -> str:
    value = float(value or 0)
    if value <= 0:
        return "0 Б"
    units = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} {units[index]}"
    return f"{value:.1f}".replace(".", ",") + f" {units[index]}"


def format_count(value: int, one: str, few: str, many: str) -> str:
    value = int(value)
    if value % 10 == 1 and value % 100 != 11:
        word = one
    elif 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14:
        word = few
    else:
        word = many
    return f"{value} {word}"


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
