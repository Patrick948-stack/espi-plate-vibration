"""
styles.py

Theme stylesheet for the ESPI app.

The actual color tokens and stylesheet live in ESPI Full Algorithm/theme.py,
shared with monitor_gui.py and run_experiment_gui.py, so the landing page,
Settings dialog, and both dashboards always match whichever theme is
selected — one theme choice, one stylesheet, applied everywhere.
"""

import sys
from pathlib import Path


def _ensure_espi_algorithm_on_path():
    """
    Add the ESPI Full Algorithm folder to sys.path so theme.py can be
    imported. See main_window.py's copy of this same helper for the full
    explanation of why this is needed.
    """
    algo_dir = Path(__file__).resolve().parent.parent / "ESPI Full Algorithm"
    if str(algo_dir) not in sys.path:
        sys.path.insert(0, str(algo_dir))


def apply_theme(app, theme_name: str):
    """
    Apply a theme to the entire application.

    Applies the shared stylesheet (see ESPI Full Algorithm/theme.py) to
    all widgets. Light theme uses several shades of light gray with dark
    text (never pure white); dark theme uses dark grays with light text.

    Args:
        app: QApplication instance
        theme_name: Either "light" or "dark"

    Example:
        from PyQt6.QtWidgets import QApplication
        app = QApplication([])

        # Apply dark theme to entire app
        apply_theme(app, "dark")

        # Later, change to light theme
        apply_theme(app, "light")
    """
    _ensure_espi_algorithm_on_path()
    import theme

    normalized = "dark" if theme_name.lower() == "dark" else "light"
    app.setStyleSheet(theme.build_stylesheet(normalized))


def icon_color(theme_name: str) -> str:
    """Return the hex color espi_app's own qtawesome icons should use."""
    _ensure_espi_algorithm_on_path()
    import theme

    normalized = "dark" if theme_name.lower() == "dark" else "light"
    return theme.icon_color(normalized)


# Landing page mode-card colors. Deliberately kept out of the shared
# ESPI Full Algorithm/theme.py (used by monitor_gui.py and
# run_experiment_gui.py too) -- these are scoped to espi_app's landing
# page alone. Monochrome throughout (matching the approved mockup): the
# icon badge is just a subtle circle a shade different from the card
# background, and icons/logo use the same primary text color as
# everything else, not a distinct accent color.
LANDING_ACCENTS = {
    "dark": {
        "card_bg": "#232323",
        "card_border": "#383838",
        "card_hover_bg": "#2e2e2e",
        "icon_badge_bg": "#2e2e2e",
        "divider_color": "#4a4a4a",
    },
    "light": {
        "card_bg": "#f5f5f7",
        "card_border": "#d8d8dc",
        "card_hover_bg": "#ececf0",
        "icon_badge_bg": "#ececf0",
        "divider_color": "#c4c4c4",
    },
}


def landing_accent_colors(theme_name: str) -> dict:
    """Return the landing page's own accent color tokens for a theme."""
    normalized = "dark" if theme_name.lower() == "dark" else "light"
    return LANDING_ACCENTS[normalized]


def text_secondary_color(theme_name: str) -> str:
    """Return the shared theme's muted/secondary text color for a theme."""
    _ensure_espi_algorithm_on_path()
    import theme

    normalized = "dark" if theme_name.lower() == "dark" else "light"
    return theme.colors(normalized)["text_secondary"]
