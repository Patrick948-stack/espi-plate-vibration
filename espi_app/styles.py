"""
styles.py

Theme stylesheets for the ESPI app.

PyQt6 uses "stylesheets" (similar to CSS) to style widgets.
This file defines both light and dark themes, and provides a function
to apply them to the entire application.

Light theme uses a light background with dark text.
Dark theme uses a dark background with light text.
"""

# Light theme — light background with dark text
LIGHT_THEME = """
    QMainWindow, QWidget {
        background-color: #F5F5F5;
        color: #000000;
    }

    QLabel {
        color: #000000;
        background-color: transparent;
    }

    QPushButton {
        background-color: #E0E0E0;
        color: #000000;
        padding: 8px 16px;
        border-radius: 4px;
        border: 1px solid #B0B0B0;
        font-size: 14px;
    }

    QPushButton:hover {
        background-color: #D0D0D0;
        border: 1px solid #A0A0A0;
    }

    QPushButton:pressed {
        background-color: #FFFFFF;
        border: 1px solid #A0A0A0;
    }

    QPushButton:disabled {
        background-color: #D5D5D5;
        color: #999999;
    }

    QGroupBox {
        color: #000000;
        border: 1px solid #B0B0B0;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
        font-weight: bold;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px 0 3px;
    }

    QTabWidget::pane {
        border: 1px solid #B0B0B0;
    }

    QTabBar::tab {
        background-color: #E0E0E0;
        color: #000000;
        padding: 8px 20px;
        margin-right: 2px;
        border: 1px solid #B0B0B0;
    }

    QTabBar::tab:selected {
        background-color: #FFFFFF;
        border-bottom: 2px solid #3366CC;
    }

    QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #FFFFFF;
        color: #000000;
        border: 1px solid #B0B0B0;
        border-radius: 3px;
        padding: 4px;
    }

    QCheckBox {
        color: #000000;
        spacing: 5px;
    }

    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }

    QCheckBox::indicator:unchecked {
        background-color: #FFFFFF;
        border: 1px solid #B0B0B0;
        border-radius: 3px;
    }

    QCheckBox::indicator:checked {
        background-color: #E0E0E0;
        border: 1px solid #3366CC;
        border-radius: 3px;
    }
"""

# Dark theme — dark background with light text
DARK_THEME = """
    QMainWindow, QWidget {
        background-color: #1E1E1E;
        color: #FFFFFF;
    }

    QLabel {
        color: #FFFFFF;
        background-color: transparent;
    }

    QPushButton {
        background-color: #292929;
        color: #FFFFFF;
        padding: 8px 16px;
        border-radius: 4px;
        border: 1px solid #4D4D4D;
        font-size: 14px;
    }

    QPushButton:hover {
        background-color: #383838;
        border: 1px solid #4D4D4D;
    }

    QPushButton:pressed {
        background-color: #000000;
        border: 1px solid #000000;
    }

    QPushButton:disabled {
        background-color: #2D2D2D;
        color: #666666;
    }

    QGroupBox {
        color: #FFFFFF;
        border: 1px solid #4D4D4D;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
        font-weight: bold;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px 0 3px;
    }

    QTabWidget::pane {
        border: 1px solid #4D4D4D;
    }

    QTabBar::tab {
        background-color: #292929;
        color: #FFFFFF;
        padding: 8px 20px;
        margin-right: 2px;
        border: 1px solid #4D4D4D;
    }

    QTabBar::tab:selected {
        background-color: #383838;
        border-bottom: 2px solid #6699FF;
    }

    QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #292929;
        color: #FFFFFF;
        border: 1px solid #4D4D4D;
        border-radius: 3px;
        padding: 4px;
    }

    QCheckBox {
        color: #FFFFFF;
        spacing: 5px;
    }

    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }

    QCheckBox::indicator:unchecked {
        background-color: #292929;
        border: 1px solid #4D4D4D;
        border-radius: 3px;
    }

    QCheckBox::indicator:checked {
        background-color: #383838;
        border: 1px solid #6699FF;
        border-radius: 3px;
    }
"""


def apply_theme(app, theme_name: str):
    """
    Apply a theme to the entire application.

    Applies a complete stylesheet to all widgets. Light theme has light
    background with dark text. Dark theme has dark background with light text.

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
    if theme_name.lower() == "dark":
        app.setStyleSheet(DARK_THEME)
    else:
        app.setStyleSheet(LIGHT_THEME)
