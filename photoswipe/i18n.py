from __future__ import annotations

import locale
import os
from datetime import datetime
from typing import Any

LANGUAGES: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
    "pt": "Português (Brasil)",
}
DEFAULT_LANGUAGE = "en"
_current = DEFAULT_LANGUAGE

# Translations use the English interface text as the source key. This keeps the
# code readable and means an untranslated string still falls back to English.
from .locales.pt import TRANSLATIONS as _PT
from .locales.ru import TRANSLATIONS as _RU

_CATALOGS = {"ru": _RU, "pt": _PT}


def system_language() -> str:
    """Return a supported language based on the OS locale, defaulting to English."""
    candidates = [
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ]
    try:
        language, _ = locale.getlocale()
        candidates.append(language)
    except Exception:
        pass
    for raw in candidates:
        if not raw:
            continue
        code = raw.lower().replace("-", "_")
        if code.startswith("ru"):
            return "ru"
        if code.startswith("pt"):
            return "pt"
        if code.startswith("en"):
            return "en"
    return DEFAULT_LANGUAGE


def normalize_language(value: str | None) -> str:
    if isinstance(value, str):
        code = value.lower().replace("_", "-")
        if code.startswith("ru"):
            return "ru"
        if code.startswith("pt"):
            return "pt"
        if code.startswith("en"):
            return "en"
    return system_language()


def set_language(value: str) -> str:
    global _current
    _current = normalize_language(value)
    return _current


def current_language() -> str:
    return _current


def decimal_separator() -> str:
    return "," if _current in {"ru", "pt"} else "."


def tr(text: str, **kwargs: Any) -> str:
    translated = _CATALOGS.get(_current, {}).get(text, text)
    if kwargs:
        try:
            return translated.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return translated
    return translated


_MONTHS = {
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    "ru": (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ),
    "pt": (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ),
}


def format_date(iso_value: str | None) -> str:
    if not iso_value:
        return ""
    try:
        value = datetime.fromisoformat(iso_value)
    except ValueError:
        return iso_value
    month = _MONTHS.get(_current, _MONTHS["en"])[value.month - 1]
    if _current == "en":
        return f"{month} {value.day}, {value.year}, {value:%H:%M}"
    if _current == "pt":
        return f"{value.day} de {month} de {value.year}, {value:%H:%M}"
    return f"{value.day} {month} {value.year}, {value:%H:%M}"


DEFAULT_FOLDER_NAMES = {
    "ru": {"favorite": "Избранное", "trash": "Корзина", "maybe": "Может быть"},
    "en": {"favorite": "Favorites", "trash": "Trash", "maybe": "Maybe"},
    "pt": {"favorite": "Favoritos", "trash": "Lixeira", "maybe": "Talvez"},
}


def default_folder_names(language: str | None = None) -> dict[str, str]:
    code = normalize_language(language)
    return dict(DEFAULT_FOLDER_NAMES.get(code, DEFAULT_FOLDER_NAMES["en"]))
