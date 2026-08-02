"""
theme.py

Shared light/dark color tokens and stylesheet for every PyQt6 window in
this project: monitor_gui.py, run_experiment_gui.py, and (via
espi_app/styles.py) espi_app's landing page and Settings dialog.

Both dashboards already describe their look as "the same strictly
monochrome dark theme...for visual consistency between the two
dashboards" (see each file's own stylesheet comment, before this module
existed). This is that shared theme, split into two variants (light and
dark) instead of one hardcoded dark palette, plus the icon color that
belongs with each. Centralizing it here means every window always
matches whichever theme is currently selected, and a color only ever
needs to change in one place.

Light theme intentionally never uses pure white (#ffffff) — every
"light" surface is a distinct shade of light gray, the same way the dark
theme never uses pure black.
"""

# Color tokens. Keys are shared between both themes; only the values
# differ. See build_stylesheet() below for what each one styles.
DARK = {
    "base_bg": "#1e1e1e",
    "surface_bg": "#292929",
    "rail_bg": "#171717",
    "elevated_bg": "#232323",
    "deep_bg": "#141414",
    "border": "#383838",
    "text_primary": "#e0e0e0",
    "text_secondary": "#8a8a8a",
    "text_disabled": "#5a5a5a",
    "nav_disabled": "#4a4a4a",
    "nav_hover_bg": "#202020",
    "hover_bg": "#333333",
    "pressed_bg": "#202020",
    "disabled_bg": "#232323",
    "disabled_border": "#2e2e2e",
    "selection_bg": "#4a4a4a",
    "on_primary": "#181818",
    "primary_hover": "#cfcfcf",
    "primary_pressed": "#b0b0b0",
    "primary_disabled_bg": "#4a4a4a",
    "primary_disabled_border": "#4a4a4a",
    "primary_disabled_text": "#7a7a7a",
    "log_text": "#cfcfcf",
}

LIGHT = {
    "base_bg": "#e8e8e8",
    "surface_bg": "#f2f2f2",
    "rail_bg": "#dcdcdc",
    "elevated_bg": "#ececec",
    "deep_bg": "#d6d6d6",
    "border": "#c4c4c4",
    "text_primary": "#1e1e1e",
    "text_secondary": "#5a5a5a",
    "text_disabled": "#a5a5a5",
    "nav_disabled": "#b0b0b0",
    "nav_hover_bg": "#d6d6d6",
    "hover_bg": "#e2e2e2",
    "pressed_bg": "#d0d0d0",
    "disabled_bg": "#e5e5e5",
    "disabled_border": "#d0d0d0",
    "selection_bg": "#c8c8c8",
    "on_primary": "#f2f2f2",
    "primary_hover": "#333333",
    "primary_pressed": "#0d0d0d",
    "primary_disabled_bg": "#b5b5b5",
    "primary_disabled_border": "#b5b5b5",
    "primary_disabled_text": "#8a8a8a",
    "log_text": "#2e2e2e",
}


def colors(theme_name: str) -> dict:
    """
    Return the color token dict for "light" or "dark" (defaults to dark
    for any other value, matching every window's original hardcoded
    look before theming existed).
    """
    return LIGHT if theme_name == "light" else DARK


def icon_color(theme_name: str) -> str:
    """
    Return the hex color qtawesome icons should use for this theme.

    Icons are drawn once, as a bitmap, at whatever color they are given
    (unlike stylesheet-driven colors, they do not update automatically
    when the app's stylesheet changes) — callers must re-create any icon
    they want to follow a live theme switch, using this color.
    """
    return colors(theme_name)["text_primary"]


def icon_color_secondary(theme_name: str) -> str:
    """The muted/secondary icon color (e.g. a "Learn More" button icon)."""
    return colors(theme_name)["text_secondary"]


def build_stylesheet(theme_name: str) -> str:
    """
    Build the full QSS stylesheet for the given theme ("light" or "dark").

    Covers every object name and widget type used across espi_app's
    landing page and Settings dialog, monitor_gui.py, and
    run_experiment_gui.py. A selector that does not match anything in a
    particular window (for example QPlainTextEdit#LogConsole, which only
    run_experiment_gui.py has) is simply never triggered there — one
    shared stylesheet is safe to apply everywhere.
    """
    c = colors(theme_name)
    return f"""
QMainWindow, QWidget {{
    background-color: {c['base_bg']};
    color: {c['text_primary']};
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QFrame#Sidebar {{
    background-color: {c['rail_bg']};
    border: none;
}}

QLabel#BrandTitle {{
    color: {c['text_primary']};
    font-size: 14px;
    font-weight: 600;
    background-color: transparent;
}}

QListWidget#NavRail {{
    background-color: {c['rail_bg']};
    border: none;
    border-right: 1px solid {c['border']};
    padding: 12px 0px;
    outline: 0;
}}
QListWidget#NavRail::item {{
    color: {c['text_secondary']};
    padding: 14px 22px;
    border-left: 3px solid transparent;
}}
QListWidget#NavRail::item:hover {{
    background-color: {c['nav_hover_bg']};
    color: {c['text_primary']};
}}
QListWidget#NavRail::item:selected, QListWidget#NavRail::item:selected:!active {{
    background-color: {c['surface_bg']};
    color: {c['text_primary']};
    border-left: 3px solid {c['text_primary']};
}}
QListWidget#NavRail::item:disabled {{
    color: {c['nav_disabled']};
}}

QFrame#NavSeparator {{
    background-color: {c['border']};
    margin: 8px 12px;
}}
QPushButton#SidebarSettings {{
    background-color: transparent;
    color: {c['text_secondary']};
    text-align: left;
    padding-left: 22px;
    padding: 8px 8px;
    border: none;
    outline: 0;
}}
QPushButton#SidebarSettings:hover {{
    background-color: {c['surface_bg']};
    color: {c['text_primary']};
}}
QPushButton#SidebarSettings:pressed {{
    background-color: {c['border']};
}}

QGroupBox {{
    background-color: {c['surface_bg']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    margin-top: 18px;
    padding: 20px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {c['text_secondary']};
}}

QLabel {{
    color: {c['text_primary']};
    background-color: transparent;
}}
QLabel#SummaryLabel {{
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
    background-color: {c['elevated_bg']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 12px;
}}
QLabel#FeedFrame {{
    background-color: {c['deep_bg']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    color: {c['text_secondary']};
    font-size: 13px;
}}
QLabel#InfoLabel {{
    color: {c['text_secondary']};
    font-size: 12px;
    background-color: transparent;
}}
QLabel#FreqLabel {{ font-weight: 600; font-size: 14px; }}
QLabel#WarningLabel {{
    color: {c['text_primary']};
    font-size: 12px;
    font-weight: 600;
    background-color: {c['surface_bg']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 10px;
}}

QPushButton {{
    background-color: {c['surface_bg']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 9px 18px;
    color: {c['text_primary']};
}}
QPushButton:hover {{ background-color: {c['hover_bg']}; border-color: #4a4a4a; }}
QPushButton:pressed {{ background-color: {c['pressed_bg']}; }}
QPushButton:disabled {{ color: {c['text_disabled']}; background-color: {c['disabled_bg']}; border-color: {c['disabled_border']}; }}

QPushButton#PrimaryButton {{
    background-color: {c['text_primary']};
    border: 1px solid {c['text_primary']};
    color: {c['on_primary']};
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{ background-color: {c['primary_hover']}; border-color: {c['primary_hover']}; }}
QPushButton#PrimaryButton:pressed {{ background-color: {c['primary_pressed']}; border-color: {c['primary_pressed']}; }}
QPushButton#PrimaryButton:disabled {{
    background-color: {c['primary_disabled_bg']}; border-color: {c['primary_disabled_border']}; color: {c['primary_disabled_text']};
}}

QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox {{
    background-color: {c['surface_bg']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 8px;
    color: {c['text_primary']};
    selection-background-color: {c['selection_bg']};
    selection-color: {c['text_primary']};
}}
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {c['text_primary']};
}}

QRadioButton {{
    spacing: 8px;
    padding: 4px 0px;
    background-color: transparent;
    outline: none;
}}

QCheckBox {{
    color: {c['text_primary']};
    spacing: 8px;
    background-color: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}
QCheckBox::indicator:unchecked {{
    background-color: {c['surface_bg']};
    border: 1px solid {c['border']};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background-color: {c['text_primary']};
    border: 1px solid {c['text_primary']};
    border-radius: 3px;
}}

QTabWidget::pane {{ border: 1px solid {c['border']}; }}
QTabBar::tab {{
    background-color: {c['surface_bg']};
    color: {c['text_primary']};
    padding: 8px 20px;
    margin-right: 2px;
    border: 1px solid {c['border']};
}}
QTabBar::tab:selected {{
    background-color: {c['elevated_bg']};
    border-bottom: 2px solid {c['text_primary']};
}}

QPushButton#LearnMoreButton {{
    background-color: transparent;
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 4px 10px;
    color: {c['text_secondary']};
    font-size: 12px;
}}
QPushButton#LearnMoreButton:hover {{
    background-color: {c['surface_bg']};
    color: {c['text_primary']};
    border-color: #4a4a4a;
}}

QTextBrowser#LearnMoreBrowser {{
    background-color: {c['elevated_bg']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 14px;
    color: {c['text_primary']};
    font-size: 13px;
}}

QWidget#CanvasCard {{
    background-color: {c['surface_bg']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}

QStatusBar {{
    background-color: {c['base_bg']};
    border-top: 1px solid {c['border']};
    color: {c['text_secondary']};
}}

QProgressBar {{
    border: 1px solid {c['border']};
    border-radius: 8px;
    background-color: {c['elevated_bg']};
    text-align: center;
    height: 22px;
    font-weight: 600;
    color: {c['text_primary']};
}}
QProgressBar::chunk {{
    background-color: {c['text_primary']};
    border-radius: 7px;
}}

QPlainTextEdit#LogConsole {{
    background-color: {c['deep_bg']};
    color: {c['log_text']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
    padding: 12px;
}}
"""
