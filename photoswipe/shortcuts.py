from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from .config import canonical_combo

from .i18n import tr

_ACTION_LABELS = {
    "favorite": "Favorite",
    "trash": "Trash",
    "maybe": "Maybe",
    "round2": "Second round",
    "undo": "Undo",
    "compare": "Compare",
    "toggleRaw": "RAW display",
    "zoomIn": "Zoom in",
    "zoomOut": "Zoom out",
    "rotateCw": "Rotate right",
    "rotateCcw": "Rotate left",
    "resetView": "Reset view",
    "fullscreen": "Fullscreen",
    "help": "Help",
}

_ACTION_HINTS = {
    "favorite": "Keep this photo",
    "trash": "Move to trash",
    "maybe": "Move to the “Maybe” folder",
    "round2": "Revisit this photo later",
    "undo": "Undo the last decision",
    "compare": "Show two photos side by side",
    "toggleRaw": "Cycle JPEG, RAW thumbnail and full RAW",
    "zoomIn": "Zoom in",
    "zoomOut": "Zoom out",
    "rotateCw": "Rotate 90° clockwise",
    "rotateCcw": "Rotate 90° counterclockwise",
    "resetView": "Fit to window and reset rotation",
    "fullscreen": "Toggle fullscreen",
    "help": "Show shortcuts and tips",
}


def action_label(action: str) -> str:
    return tr(_ACTION_LABELS.get(action, action))


def action_hint(action: str) -> str:
    return tr(_ACTION_HINTS.get(action, ""))


_RU_TO_LATIN = {
    "й": "q",
    "ц": "w",
    "у": "e",
    "к": "r",
    "е": "t",
    "н": "y",
    "г": "u",
    "ш": "i",
    "щ": "o",
    "з": "p",
    "х": "[",
    "ъ": "]",
    "ф": "a",
    "ы": "s",
    "в": "d",
    "а": "f",
    "п": "g",
    "р": "h",
    "о": "j",
    "л": "k",
    "д": "l",
    "ж": ";",
    "э": "'",
    "я": "z",
    "ч": "x",
    "с": "c",
    "м": "v",
    "и": "b",
    "т": "n",
    "ь": "m",
    "б": ",",
    "ю": ".",
}

_SPECIAL_KEYS = {
    Qt.Key.Key_Space: "Space",
    Qt.Key.Key_Escape: "Escape",
    Qt.Key.Key_Return: "Enter",
    Qt.Key.Key_Enter: "Enter",
    Qt.Key.Key_Tab: "Tab",
    Qt.Key.Key_Backspace: "Backspace",
    Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Insert: "Insert",
    Qt.Key.Key_Home: "Home",
    Qt.Key.Key_End: "End",
    Qt.Key.Key_PageUp: "PageUp",
    Qt.Key.Key_PageDown: "PageDown",
    Qt.Key.Key_Up: "ArrowUp",
    Qt.Key.Key_Down: "ArrowDown",
    Qt.Key.Key_Left: "ArrowLeft",
    Qt.Key.Key_Right: "ArrowRight",
    Qt.Key.Key_Minus: "Minus",
    Qt.Key.Key_Equal: "Equal",
    Qt.Key.Key_BracketLeft: "BracketLeft",
    Qt.Key.Key_BracketRight: "BracketRight",
    Qt.Key.Key_Backslash: "Backslash",
    Qt.Key.Key_Semicolon: "Semicolon",
    Qt.Key.Key_Apostrophe: "Quote",
    Qt.Key.Key_Comma: "Comma",
    Qt.Key.Key_Period: "Period",
    Qt.Key.Key_Slash: "Slash",
    Qt.Key.Key_QuoteLeft: "Backquote",
    Qt.Key.Key_CapsLock: "CapsLock",
    Qt.Key.Key_Menu: "ContextMenu",
    Qt.Key.Key_Print: "PrintScreen",
    Qt.Key.Key_Pause: "Pause",
    Qt.Key.Key_NumLock: "NumLock",
    Qt.Key.Key_ScrollLock: "ScrollLock",
}

_SHIFT_CHARS = {
    "?": "Slash",
    "+": "Equal",
    "_": "Minus",
    ":": "Semicolon",
    '"': "Quote",
    "<": "Comma",
    ">": "Period",
    "{": "BracketLeft",
    "}": "BracketRight",
    "|": "Backslash",
    "~": "Backquote",
    "!": "Digit1",
    "@": "Digit2",
    "#": "Digit3",
    "$": "Digit4",
    "%": "Digit5",
    "^": "Digit6",
    "&": "Digit7",
    "*": "Digit8",
    "(": "Digit9",
    ")": "Digit0",
}

_NUMPAD_KEYS = {
    Qt.Key.Key_Plus: "NumpadAdd",
    Qt.Key.Key_Asterisk: "NumpadMultiply",
    Qt.Key.Key_Slash: "NumpadDivide",
    Qt.Key.Key_Enter: "NumpadEnter",
    Qt.Key.Key_Period: "NumpadDecimal",
}


def event_to_combo(event: QKeyEvent) -> str | None:
    key = event.key()
    if key in (
        Qt.Key.Key_Control,
        Qt.Key.Key_Shift,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
        Qt.Key.Key_AltGr,
        Qt.Key.Key_unknown,
    ):
        return None
    text = event.text() or ""
    modifiers = event.modifiers()
    has_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
    has_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
    has_alt = bool(modifiers & Qt.KeyboardModifier.AltModifier)
    has_meta = bool(modifiers & Qt.KeyboardModifier.MetaModifier)
    keypad = bool(modifiers & Qt.KeyboardModifier.KeypadModifier)

    code: str | None = None
    force_shift = False

    if keypad and key in _NUMPAD_KEYS:
        code = _NUMPAD_KEYS[key]
    elif keypad and Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        code = f"Numpad{key - Qt.Key.Key_0}"
    elif text in _SHIFT_CHARS:
        code = _SHIFT_CHARS[text]
        force_shift = True
    elif key == Qt.Key.Key_Question:
        code = "Slash"
        force_shift = True
    elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        code = f"Key{chr(key)}"
    elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        code = f"Digit{key - Qt.Key.Key_0}"
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
        code = f"F{key - Qt.Key.Key_F1 + 1}"
    else:
        code = _SPECIAL_KEYS.get(key)
        if code is None and text:
            char = text.lower()
            char = _RU_TO_LATIN.get(char, char)
            if len(char) == 1 and "a" <= char <= "z":
                code = f"Key{char.upper()}"
            elif len(char) == 1 and "0" <= char <= "9":
                code = f"Digit{char}"
            elif len(char) == 1:
                reverse = {
                    "[": "BracketLeft",
                    "]": "BracketRight",
                    ";": "Semicolon",
                    "'": "Quote",
                    ",": "Comma",
                    ".": "Period",
                    "/": "Slash",
                    "\\": "Backslash",
                    "`": "Backquote",
                    "-": "Minus",
                    "=": "Equal",
                }
                code = reverse.get(char)
    if not code:
        return None

    # `?`, `+`, `_` etc. already encode Shift in the character itself. Avoid
    # double-counting it when Qt also reports ShiftModifier.
    shift = has_shift or force_shift
    parts: list[str] = []
    if has_ctrl:
        parts.append("Ctrl")
    if has_alt:
        parts.append("Alt")
    if shift:
        parts.append("Shift")
    if has_meta:
        parts.append("Meta")
    parts.append(code)
    try:
        return canonical_combo("+".join(parts))
    except ValueError:
        return None


_SHIFT_DISPLAY = {
    "Shift+Slash": "?",
    "Shift+Equal": "+",
    "Shift+Minus": "_",
    "Shift+Digit1": "!",
    "Shift+Digit2": "@",
    "Shift+Digit3": "#",
    "Shift+Digit4": "$",
    "Shift+Digit5": "%",
    "Shift+Digit6": "^",
    "Shift+Digit7": "&",
    "Shift+Digit8": "*",
    "Shift+Digit9": "(",
    "Shift+Digit0": ")",
    "Shift+Semicolon": ":",
    "Shift+Quote": '"',
    "Shift+Comma": "<",
    "Shift+Period": ">",
    "Shift+BracketLeft": "{",
    "Shift+BracketRight": "}",
    "Shift+Backslash": "|",
    "Shift+Backquote": "~",
}


def display_combo(combo: str) -> str:
    if not combo:
        return ""
    if combo in _SHIFT_DISPLAY:
        return _SHIFT_DISPLAY[combo]
    pieces = combo.split("+")
    code = pieces.pop()
    special = {
        "ArrowRight": "→",
        "ArrowLeft": "←",
        "ArrowUp": "↑",
        "ArrowDown": "↓",
        "Space": tr("Space"),
        "Escape": "Esc",
        "Enter": "Enter",
        "Tab": "Tab",
        "Backspace": "⌫",
        "Delete": "Del",
        "Insert": "Ins",
        "Home": "Home",
        "End": "End",
        "PageUp": "PgUp",
        "PageDown": "PgDn",
        "Minus": "−",
        "Equal": "=",
        "BracketLeft": "[",
        "BracketRight": "]",
        "Backslash": "\\",
        "Semicolon": ";",
        "Quote": "'",
        "Comma": ",",
        "Period": ".",
        "Slash": "/",
        "Backquote": "`",
        "NumpadAdd": "Num +",
        "NumpadSubtract": "Num −",
        "NumpadMultiply": "Num *",
        "NumpadDivide": "Num /",
        "NumpadEnter": "Num Enter",
        "NumpadDecimal": "Num .",
        "CapsLock": "Caps",
        "ContextMenu": "Menu",
        "PrintScreen": "PrtSc",
    }
    if code.startswith("Key"):
        code = code[3:]
    elif code.startswith("Digit"):
        code = code[5:]
    elif code.startswith("Numpad") and code not in special:
        code = "Num " + code[6:]
    else:
        code = special.get(code, code)
    mods = {"Ctrl": "Ctrl", "Alt": "Alt", "Shift": "Shift", "Meta": "Meta"}
    return " + ".join([*(mods.get(p, p) for p in pieces), code])


def action_for_event(event: QKeyEvent, shortcuts: dict[str, list[str]]) -> str | None:
    combo = event_to_combo(event)
    if not combo:
        return None
    for action, bindings in shortcuts.items():
        if combo in bindings:
            return action
    return None
