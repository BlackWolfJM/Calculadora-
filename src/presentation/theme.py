"""Tokens, QSS e iconos locales del escritorio claro aprobado."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

BACKGROUND = "#F5F3EE"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#ECEFE8"
RESULT_SURFACE = "#E9F3EB"
TEXT = "#24332F"
MUTED = "#50615A"
BORDER = "#CCD3C8"
PRIMARY = "#216653"
FOCUS = "#087858"
SUCCESS = "#047857"
WARNING = "#B45309"
DANGER = "#B91C1C"
INFO = "#0369A1"
SIDEBAR_WIDTH = 176
RESULT_FONT_SIZE = 32
STEP_FONT_SIZE = 18

_PATHS = {
    "calculator": '<rect x="4" y="2" width="16" height="20" rx="2"/>'
    '<path d="M7 6h10M8 11h1m6 0h1m-8 4h1m6 0h1m-8 4h1m6 0h1"/>',
    "derivative": '<path d="M7 21c4 0 3-18 8-18m-8 7h9m1-7 1-2"/>',
    "integral": '<path d="M7 21c8 4 2-24 10-18"/>',
    "equation": '<path d="m5 8 6 8m0-8-6 8m10-8h5m-5 7h5"/>',
    "multivariable": '<path d="M12 3v18M3 12h18M5 19 19 5"/>',
    "graph": '<path d="M4 3v17h17M6 15l4-5 4 3 6-8"/>',
    "history": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    "plus": '<path d="M12 4v16M4 12h16"/>',
    "solve": '<path d="m6 3 15 9-15 9z"/>',
    "play": '<path d="m7 4 13 8-13 8z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "cancel": '<path d="m6 6 12 12M6 18 18 6"/>',
    "copy": '<rect x="8" y="6" width="12" height="15" rx="2"/>'
    '<path d="M16 6V3H4v15h4"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3m-7 3v7m4-7v7m4-7v7M6 7l1 13h10l1-13"/>',
    "sliders": '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/>'
    '<circle cx="15" cy="12" r="2"/><circle cx="11" cy="18" r="2"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/>'
    '<path d="M3 10h18M3 15h18M9 4v16M15 4v16"/>',
    "points": '<circle cx="6" cy="16" r="2.5"/><circle cx="12" cy="8" r="2.5"/>'
    '<circle cx="18" cy="13" r="2.5"/><path d="m8 14 2.5-4m3.5 0 2.5 2"/>',
}


def icon(name: str, color: str = MUTED) -> QIcon:
    """Iconos vectoriales de trazo uniforme, sin archivos ni red."""
    path_data = _PATHS.get(name, _PATHS["calculator"])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.75" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{path_data}</svg>"
    )
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    return QIcon(pixmap)


QSS = f"""
QMainWindow, QDialog {{ background: {BACKGROUND}; }}
QWidget {{ background: {SURFACE}; color: {TEXT};
 font-family: "Segoe UI"; font-size: 15px; }}
QWidget#shell, QWidget#work-content {{ background: {BACKGROUND}; }}
QFrame#top-bar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QFrame#sidebar {{ background: {SURFACE_ALT}; border-right: 1px solid {BORDER}; }}
QScrollArea#sidebar-scroll {{ background: {SURFACE_ALT}; }}
QLabel {{ background: transparent; }}
QLabel[role="module-subtitle"] {{ color: {MUTED}; font-size: 15px; }}
QLabel[role="empty-state"] {{ color: {MUTED}; padding: 18px 0px; }}
QListWidget {{ outline: none; border: 1px solid {BORDER}; border-radius: 8px;
 selection-background-color: #DDECE2; selection-color: {TEXT}; }}
QListWidget::item {{ padding: 12px 14px; border-bottom: 1px solid {BORDER};
 outline: none; }}
QListWidget::item:selected {{ background: #DDECE2; color: {TEXT};
 border-left: 3px solid {PRIMARY}; }}
QListWidget::item:hover {{ background: {SURFACE_ALT}; }}
QListWidget:focus {{ border: 2px solid {FOCUS}; }}
QPushButton#btn-clear {{ color: {DANGER}; }}
QPushButton#btn-solve:pressed {{ background: #103D31; }}
QFrame#response-card {{ border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#brand {{ font-size: 19px; font-weight: 700; }}
QLabel#module-context {{ color: {MUTED}; font-size: 17px; }}
QLabel#module-title {{ font-size: 30px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {MUTED}; font-size: 13px; }}
QLabel[role="section"] {{ font-size: 17px; font-weight: 600; }}
QLabel[role="nav-group"] {{ color: {MUTED}; font-size: 13px; font-weight: 600;
 padding: 12px 14px 4px; }}
QFrame#input-card {{ background: {SURFACE};
 border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#summary {{ background: {RESULT_SURFACE}; border: none; border-radius: 8px; }}
QLabel#result-title {{ font-size: 19px; font-weight: 700; }}
QLabel#interpretation {{ font-family: "Consolas"; font-size: 17px; }}
QLabel[role="success"] {{ color: {SUCCESS}; font-weight: 600; }}
QLabel[role="warning"] {{ color: {WARNING}; background: #FFFBEB;
 border-left: 3px solid {WARNING}; padding: 8px 12px; border-radius: 6px; }}
QLabel[role="error"] {{ color: {DANGER}; background: #FEF2F2;
 border-left: 3px solid {DANGER}; padding: 8px 12px; border-radius: 6px; }}
QLabel[role="info"] {{ color: {INFO}; background: #EFF6FF; padding: 8px 12px;
 border-radius: 6px; }}
QLabel[role="step-number"] {{ color: {PRIMARY}; background: #E0EEE4;
 border-radius: 16px; font-size: 16px; font-weight: 700; }}
QFrame[role="step"] {{ border-bottom: 1px solid {BORDER}; }}
QFrame[role="sub-step-group"] {{ background: #F8FAFC;
 border-left: 3px solid #93C5FD; border-top: none; border-right: none;
 border-bottom: none; border-radius: 4px; margin-left: 16px; }}
QPushButton {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
 border-radius: 8px; padding: 0px 14px; min-height: 40px; font-size: 15px; }}
QPushButton:hover {{ background: {SURFACE_ALT}; border-color: #819089; }}
QPushButton:pressed {{ background: #E4E9E2; }}
QPushButton:disabled {{ background: {SURFACE_ALT}; color: #53635C;
 border-color: {BORDER}; }}
QPushButton[role="step-disclosure"] {{ background: #F1F5F9; color: #1D4ED8;
 border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px 12px;
 font-weight: 600; min-height: 32px; }}
QPushButton[role="step-disclosure"]:hover,
QPushButton[role="step-disclosure"]:checked {{ background: #EFF6FF;
 border-color: #93C5FD; }}
QPushButton#btn-solve {{ background: {PRIMARY}; color: white;
 border-color: {PRIMARY}; font-weight: 600; }}
QPushButton#btn-solve:hover {{ background: #174B3D; }}
QPushButton#btn-solve:disabled {{ background: #E4E9E2; color: #53635C;
 border-color: {BORDER}; }}
QPushButton#btn-cancel {{ color: {DANGER}; border-color: {DANGER}; }}
QPushButton#btn-new {{ color: {PRIMARY}; border-color: {PRIMARY}; }}
QPushButton#btn-keyboard:checked:enabled {{ background: #DDECE2; color: {PRIMARY}; }}
QWidget#math-keyboard {{ background: {BACKGROUND}; border: 1px solid {BORDER};
 border-radius: 8px; padding: 6px; }}
QWidget#math-keyboard QPushButton {{ background: {SURFACE}; color: {TEXT};
 border: 1px solid {BORDER}; border-radius: 6px; padding: 2px 6px;
 min-height: 36px; font-family: "Consolas"; font-weight: 600; font-size: 15px; }}
QWidget#math-keyboard QPushButton:hover {{ background: {SURFACE_ALT};
 border-color: #819089; }}
QWidget#math-keyboard QPushButton:pressed {{ background: #DDECE2; }}
QPushButton[role="nav"] {{ text-align: left; background: transparent;
 border: 2px solid transparent; padding: 0px 14px; min-height: 44px; }}
QFrame#sidebar QPushButton[role="nav"] {{ padding: 0px 7px; min-height: 36px; }}
QFrame#sidebar QLabel[role="nav-group"] {{ padding: 5px 14px 2px; }}
QPushButton[role="nav"]:hover {{ background: {SURFACE_ALT}; }}
QPushButton[role="nav"]:checked {{ background: #DDECE2; color: {PRIMARY};
 border-left: 3px solid {PRIMARY}; font-weight: 600; }}
QPushButton:focus, QPushButton[role="nav"]:focus,
QPushButton#btn-solve:focus, QPushButton#btn-cancel:focus,
QPushButton#btn-new:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QLineEdit:focus, QTextEdit:focus,
QTabBar::tab:focus {{ border: 2px solid {FOCUS}; }}
QPushButton#btn-solve:focus {{ border-color: {SURFACE}; }}
QLineEdit {{ background: {SURFACE}; border: 1px solid #819089;
 border-radius: 6px; min-height: 38px; padding: 0px 10px; font-size: 15px; }}
QTextEdit {{ background: {SURFACE}; border: 1px solid #819089;
 border-radius: 8px; padding: 5px 10px; font-family: "Consolas"; font-size: 20px;
 selection-background-color: {PRIMARY}; selection-color: white; }}
QTextEdit[invalid="true"] {{ border: 2px solid {DANGER}; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ background: {SURFACE}; border: 1px solid #819089;
 border-radius: 6px; min-height: 38px; padding: 0px 10px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; color: {TEXT};
 selection-background-color: #DDECE2; selection-color: {PRIMARY}; }}
QScrollArea {{ background: transparent; border: none; }}
QTabWidget::pane {{ background: {SURFACE}; border: none;
 border-top: 1px solid {BORDER}; }}
QTabBar::tab {{ background: {SURFACE}; color: {MUTED}; border: 2px solid transparent;
 padding: 10px 16px; font-weight: 600; font-size: 15px; }}
QTabBar::tab:selected {{ color: {PRIMARY}; border-bottom: 3px solid {PRIMARY}; }}
QTabBar::tab:hover {{ background: {SURFACE_ALT}; }}
QScrollBar:vertical {{ background: {BACKGROUND}; width: 10px; margin: 0px; }}
QScrollBar::handle:vertical {{ background: #A5B1A8; min-height: 24px;
 border-radius: 5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""
