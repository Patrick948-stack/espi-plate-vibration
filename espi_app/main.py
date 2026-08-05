"""
main.py

Application entry point.

This is the script users run to start the ESPI app:
    python -m espi_app.main
    or
    python espi_app/main.py

The main() function:
1. Loads settings from disk
2. Creates the PyQt6 application
3. Applies the user's chosen theme
4. Shows the landing page
5. Starts the event loop
"""

import sys
from PyQt6.QtWidgets import QApplication

from espi_app.settings import SettingsManager
from espi_app.main_window import LandingPage
from espi_app.styles import apply_theme
from espi_app.logo import build_icon


def main():
    """
    Application entry point.

    Sets up the PyQt6 application and shows the landing page.

    Example:
        # Called automatically when you run:
        # python -m espi_app.main
        # or
        # python espi_app/main.py
    """
    # Load settings from disk (or create defaults)
    settings_mgr = SettingsManager()

    # Create the PyQt6 application
    # This must be created before any widgets
    app = QApplication(sys.argv)

    # Sets the taskbar/dock/alt-tab icon for every window this app opens
    # (landing page, and Monitor/Scan mode, since they are additional
    # windows in this same QApplication, not separate processes). Without
    # this, Windows specifically shows a generic icon in the taskbar while
    # the app is open, even though the .exe file's own icon is correct.
    app.setWindowIcon(build_icon())

    # Apply the user's chosen theme
    theme = settings_mgr.get("ui.theme")
    apply_theme(app, theme)

    # Create and show the landing page
    window = LandingPage()
    window.show()

    # Start the event loop
    # This keeps the window open and processes events (clicks, redraws, etc.)
    # The program doesn't exit until the user closes the window
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
