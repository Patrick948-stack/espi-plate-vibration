"""
main_window.py

The landing page. The first window users see when they open the app.

The landing page presents two mode choices:
1. Monitor Camera: continuous live feed
2. Run Experiment (Scan): frequency sweep

Users can also access settings from this page.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QApplication,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from espi_app.settings import SettingsManager
from espi_app.settings_dialog import SettingsDialog
from espi_app.styles import apply_theme
import qtawesome as qta


class LandingPage(QMainWindow):
    """
    Main application window — presents mode selection.

    User can choose:
    - Monitor Camera (continuous live feed)
    - Run Experiment (frequency sweep)

    Also provides access to settings and help.
    """

    def __init__(self):
        """
        Initialize the landing page.

        Creates the UI layout with buttons for mode selection,
        settings, and help.

        Example:
            landing = LandingPage()
            landing.show()  # Display the landing page
        """
        super().__init__()

        # Load settings
        self.settings_manager = SettingsManager()

        # Window properties
        self.setWindowTitle("ESPI Camera Control")
        self.resize(600, 500)

        # Central widget — everything goes here
        central = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)  # Space between elements
        layout.setContentsMargins(32, 32, 32, 32)  # Padding around edges

        # --- Title ---
        title = QLabel("ESPI Camera System")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # --- Subtitle ---
        subtitle = QLabel("Choose a mode to begin")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # --- Mode selection buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)

        # Monitor Mode button
        self.monitor_button = QPushButton(qta.icon('mdi.camera'), "Monitor Mode")
        self.monitor_button.setMinimumSize(200, 80)
        self.monitor_button.setToolTip("Continuously monitor the camera live feed with real-time frame analysis")
        self.monitor_button.clicked.connect(self._on_monitor_clicked)
        button_layout.addWidget(self.monitor_button)

        # Scan Mode button
        self.scan_button = QPushButton(qta.icon('mdi.pulse'), "Scan Mode")
        self.scan_button.setMinimumSize(200, 80)
        self.scan_button.setToolTip("Run a frequency sweep and analyze the plate response at multiple frequencies")
        self.scan_button.clicked.connect(self._on_scan_clicked)
        button_layout.addWidget(self.scan_button)

        layout.addLayout(button_layout)

        # --- Spacer (push everything up) ---
        layout.addStretch()

        # --- Bottom controls ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        # Settings button
        self.settings_button = QPushButton(qta.icon('mdi.cog'), "Settings")
        self.settings_button.setMinimumWidth(120)
        self.settings_button.clicked.connect(self._on_settings_clicked)
        bottom_layout.addWidget(self.settings_button)

        # Help button
        self.help_button = QPushButton(qta.icon('mdi.help'), "Help")
        self.help_button.setMinimumWidth(120)
        self.help_button.clicked.connect(self._on_help_clicked)
        bottom_layout.addWidget(self.help_button)

        layout.addLayout(bottom_layout)

        # Set central widget
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _on_monitor_clicked(self):
        """
        Handle Monitor Camera button click.

        Example:
            # Called automatically when user clicks "Monitor Mode" button
        """
        # TODO: Launch monitor GUI
        QMessageBox.information(
            self,
            "Monitor Mode",
            "Monitor Camera mode will open here.\n\n(Not yet implemented)",
        )

    def _on_scan_clicked(self):
        """
        Handle Run Experiment button click.

        Example:
            # Called automatically when user clicks "Scan Mode" button
        """
        # TODO: Launch scan GUI
        QMessageBox.information(
            self,
            "Scan Mode",
            "Run Experiment mode will open here.\n\n(Not yet implemented)",
        )

    def _on_settings_clicked(self):
        """
        Handle Settings button click.

        Example:
            # Called automatically when user clicks "Settings" button
            # Opens the SettingsDialog (modal window)
        """
        try:
            dialog = SettingsDialog(parent=self)
            # Connect theme_changed signal to apply new theme
            dialog.theme_changed.connect(self._on_theme_changed)
            dialog.exec()  # Show the dialog (modal)
        except Exception as e:
            import traceback
            error_msg = f"Error opening settings:\n{str(e)}\n\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Settings Error", error_msg)

    def _on_theme_changed(self, new_theme: str):
        """
        Handle theme change from settings dialog.

        Args:
            new_theme: The new theme name ("light" or "dark")

        Example:
            # Called automatically when SettingsDialog emits theme_changed signal
            # Applies the new theme to the entire application
        """
        app = QApplication.instance()
        apply_theme(app, new_theme)

    def _on_help_clicked(self):
        """
        Handle Help button click.

        Example:
            # Called automatically when user clicks "Help" button
            # Shows a message box with application help text
        """
        help_text = """
ESPI Camera Control — Help

This application provides two modes:

📹 Monitor Camera:
View a live feed from the camera with optional intensity graphs.
Use this to position your sample and verify camera settings.

📊 Run Experiment:
Run a frequency sweep from one frequency to another, measuring
the camera response at each step. Results are displayed after
the sweep completes.

⚙️ Settings:
Configure default values for exposure, gain, camera selection,
and display preferences. Settings are saved automatically.

For more information, see the project README.
        """
        QMessageBox.information(self, "Help", help_text.strip())
