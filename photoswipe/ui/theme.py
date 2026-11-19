from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# Palette tokens shared by widgets that need explicit colors (icons, custom
# painting, overlays) and by the stylesheet below.
BG = "#0e1013"
BG_DEEP = "#0a0b0d"
PANEL = "#16191e"
PANEL_RAISED = "#1c2026"
PANEL_HOVER = "#232832"
BORDER = "#282d36"
BORDER_LIGHT = "#353c48"
TEXT = "#eceef2"
TEXT_MUTED = "#9aa1ad"
TEXT_DIM = "#6d7480"
ACCENT = "#f0bd58"
ACCENT_HOVER = "#f6ca72"
ACCENT_DARK = "#2a2110"
GREEN = "#64c48e"
GREEN_DARK = "#14251c"
RED = "#ed7078"
RED_DARK = "#271619"
AMBER = "#e4a84f"
AMBER_DARK = "#241d10"
BLUE = "#78aaf5"
BLUE_DARK = "#151d2a"
VIOLET = "#b295f2"

VERDICT_COLORS = {
    "favorite": GREEN,
    "trash": RED,
    "maybe": AMBER,
    "round2": BLUE,
}

VERDICT_BG = {
    "favorite": "#18261f",
    "trash": "#281a1d",
    "maybe": "#262013",
    "round2": "#17202e",
}


def _font(
    family: str, size: float, weight: QFont.Weight = QFont.Weight.Normal
) -> QFont:
    font = QFont(family)
    font.setPointSizeF(size)
    font.setWeight(weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_RAISED))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL_RAISED))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL_RAISED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#17130a"))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_DIM)
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TEXT_DIM)
    )
    app.setPalette(palette)
    app.setFont(_font("Cantarell", 10.5))
    app.setStyleSheet(STYLESHEET)


STYLESHEET = f"""
* {{
    outline: none;
}}
QMainWindow, QWidget#AppRoot, QWidget#PageRoot {{
    background: {BG};
}}
QDialog {{
    background: {BG};
}}
QToolTip {{
    background: {PANEL_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 7px;
    padding: 6px 9px;
    font-size: 9.5pt;
}}
QFrame[role="panel"] {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame[role="subtle"] {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame[role="card"] {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame[role="card"]:hover {{
    border-color: {BORDER_LIGHT};
}}
QFrame[role="sep"] {{
    background: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QLabel {{
    color: {TEXT};
    background: transparent;
}}
QLabel[role="muted"] {{
    color: {TEXT_MUTED};
}}
QLabel[role="dim"] {{
    color: {TEXT_DIM};
}}
QLabel[role="title"] {{
    font-size: 23pt;
    font-weight: 700;
    color: {TEXT};
}}
QLabel[role="h2"] {{
    font-size: 15.5pt;
    font-weight: 700;
}}
QLabel[role="h3"] {{
    font-size: 12pt;
    font-weight: 600;
}}
QLabel[role="brand"] {{
    font-size: 13.5pt;
    font-weight: 700;
    letter-spacing: 0.4px;
}}
QLabel[role="micro"] {{
    color: {TEXT_DIM};
    font-size: 8.8pt;
}}
QLabel[role="badge"] {{
    background: {PANEL_RAISED};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 3px 8px;
    font-size: 8.8pt;
}}
QLabel[role="warning"] {{
    color: {AMBER};
    background: {AMBER_DARK};
    border: 1px solid #4b3a1c;
    border-radius: 8px;
    padding: 4px 9px;
    font-size: 9pt;
}}
QPushButton {{
    background: {PANEL_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 14px;
    min-height: 18px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {PANEL_HOVER};
    border-color: {BORDER_LIGHT};
}}
QPushButton:pressed {{
    background: #171a1f;
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: #15181c;
    border-color: #21252b;
}}
QPushButton[role="primary"] {{
    background: {ACCENT};
    color: #1b1507;
    border: 1px solid {ACCENT};
    font-weight: 700;
}}
QPushButton[role="primary"]:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[role="primary"]:pressed {{
    background: #d9a743;
}}
QPushButton[role="ghost"] {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_MUTED};
}}
QPushButton[role="ghost"]:hover {{
    background: {PANEL_RAISED};
    color: {TEXT};
    border-color: {BORDER_LIGHT};
}}
QPushButton[role="subtle"] {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER};
    color: {TEXT_MUTED};
    padding: 6px 10px;
    font-size: 9.2pt;
}}
QPushButton[role="subtle"]:hover {{
    color: {TEXT};
    border-color: {BORDER_LIGHT};
}}
QPushButton[role="danger"] {{
    background: {RED_DARK};
    border: 1px solid #5a2b31;
    color: {RED};
}}
QPushButton[role="danger"]:hover {{
    background: #341e22;
}}
QPushButton[role="chip"] {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 9px;
    color: {TEXT_MUTED};
    font-size: 9pt;
}}
QPushButton[role="chip"]:hover {{
    color: {TEXT};
    border-color: {BORDER_LIGHT};
}}
QPushButton[role="chip"]:checked {{
    background: {ACCENT_DARK};
    border-color: #69552b;
    color: {ACCENT};
}}
QPushButton[role="link"] {{
    background: transparent;
    border: none;
    color: {ACCENT};
    padding: 3px 5px;
    text-align: left;
    font-weight: 600;
}}
QPushButton[role="link"]:hover {{
    color: {ACCENT_HOVER};
    text-decoration: underline;
}}
QPushButton[role="decision"] {{
    border-radius: 13px;
    padding: 0;
    min-height: 72px;
    max-height: 72px;
    text-align: left;
    font-weight: 600;
}}
QPushButton[verdict="trash"] {{
    background: {RED_DARK};
    border: 1px solid #573038;
}}
QPushButton[verdict="trash"]:hover {{
    background: #341d22;
    border-color: #7f414b;
}}
QPushButton[verdict="maybe"] {{
    background: {AMBER_DARK};
    border: 1px solid #4e3d1e;
}}
QPushButton[verdict="maybe"]:hover {{
    background: #302715;
    border-color: #77602e;
}}
QPushButton[verdict="round2"] {{
    background: {BLUE_DARK};
    border: 1px solid #2d405c;
}}
QPushButton[verdict="round2"]:hover {{
    background: #1c2637;
    border-color: #45628e;
}}
QPushButton[verdict="favorite"] {{
    background: {GREEN_DARK};
    border: 1px solid #2e513c;
}}
QPushButton[verdict="favorite"]:hover {{
    background: #1a3024;
    border-color: #467a58;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
}}
QToolButton:hover {{
    background: {PANEL_RAISED};
}}
QToolButton:pressed {{
    background: #171a1f;
}}
QToolButton[role="icon"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 7px;
}}
QToolButton[role="icon"]:hover {{
    background: {PANEL_RAISED};
    border-color: {BORDER};
}}
QToolButton[role="icon"]:checked {{
    background: {ACCENT_DARK};
    border-color: #5d4a23;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #1b1507;
    min-height: 18px;
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: {BORDER_LIGHT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: #6f5a2e;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    color: {TEXT_DIM};
    background: #111317;
    border-color: #20242b;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT_DARK};
    selection-color: {ACCENT};
    padding: 4px;
    outline: none;
}}
QCheckBox, QRadioButton {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {TEXT_DIM};
}}
QProgressBar {{
    background: #21252b;
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: #262b33;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {TEXT};
    width: 15px;
    height: 15px;
    margin: -5px 0;
    border-radius: 7px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    background: {PANEL};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 9px 16px;
    margin-right: 2px;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 3px;
}}
QScrollBar::handle:vertical {{
    background: #30363f;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #414954;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 3px;
}}
QScrollBar::handle:horizontal {{
    background: #30363f;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QMenu {{
    background: {PANEL_RAISED};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 26px 7px 12px;
    border-radius: 6px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background: {ACCENT_DARK};
    color: {ACCENT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 5px 8px;
}}
QListWidget, QTreeWidget, QTableWidget {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 9px;
    color: {TEXT};
    alternate-background-color: {PANEL};
    selection-background-color: {ACCENT_DARK};
    selection-color: {ACCENT};
}}
QHeaderView::section {{
    background: {PANEL_RAISED};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px;
    font-weight: 600;
}}
QDialogButtonBox QPushButton {{
    min-width: 92px;
}}
QMessageBox {{
    background: {PANEL};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}
QGraphicsView {{
    border: none;
    background: transparent;
}}
"""
