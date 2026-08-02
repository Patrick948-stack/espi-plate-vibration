"""
main_window.py

The landing page. The first window users see when they open the app.

The landing page presents two mode choices:
1. Monitor Camera: continuous live feed
2. Run Experiment (Scan): frequency sweep

Users can also access settings from this page.
"""

import sys
from pathlib import Path

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
from PyQt6.QtCore import Qt, QByteArray

from espi_app.settings import SettingsManager
from espi_app.settings_dialog import SettingsDialog
from espi_app.styles import apply_theme, icon_color
import qtawesome as qta


def _ensure_espi_algorithm_on_path():
    """
    Add the ESPI Full Algorithm folder to sys.path.

    monitor_gui.py and run_experiment_gui.py live in that folder and use
    flat, top level imports (import monitor, import live_graphs, and so
    on). Those imports only resolve when that folder is on sys.path, which
    happens automatically when either script is run directly (python3
    monitor_gui.py adds its own folder to sys.path). Since espi_app
    launches them as a library instead of running them as a script, we add
    the folder ourselves, once, the first time either mode is opened.
    """
    algo_dir = Path(__file__).resolve().parent.parent / "ESPI Full Algorithm"
    if str(algo_dir) not in sys.path:
        sys.path.insert(0, str(algo_dir))


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

        # References to the currently open Monitor/Scan dashboard windows,
        # if any. Kept as attributes (not local variables) so Python does
        # not garbage collect them the moment _on_monitor_clicked() or
        # _on_scan_clicked() returns, which would close the window
        # immediately after it opened.
        self._monitor_window = None
        self._scan_window = None

        # Window properties
        self.setWindowTitle("ESPI Camera Control")
        self._restore_or_default_geometry()

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

        current_icon_color = icon_color(self.settings_manager.get("ui.theme"))

        # Monitor Mode button
        self.monitor_button = QPushButton(qta.icon('mdi.camera', color=current_icon_color), "Monitor Mode")
        self.monitor_button.setMinimumSize(200, 80)
        self.monitor_button.setToolTip("Continuously monitor the camera live feed with real-time frame analysis")
        self.monitor_button.clicked.connect(self._on_monitor_clicked)
        button_layout.addWidget(self.monitor_button)

        # Scan Mode button
        self.scan_button = QPushButton(qta.icon('mdi.pulse', color=current_icon_color), "Scan Mode")
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
        self.settings_button = QPushButton(qta.icon('mdi.cog', color=current_icon_color), "Settings")
        self.settings_button.setMinimumWidth(120)
        self.settings_button.clicked.connect(self._on_settings_clicked)
        bottom_layout.addWidget(self.settings_button)

        # Help button
        self.help_button = QPushButton(qta.icon('mdi.help', color=current_icon_color), "Help")
        self.help_button.setMinimumWidth(120)
        self.help_button.clicked.connect(self._on_help_clicked)
        bottom_layout.addWidget(self.help_button)

        layout.addLayout(bottom_layout)

        # Set central widget
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._apply_tooltip_settings()

    def _restore_or_default_geometry(self):
        """
        Restore the window's last position and size, if enabled and saved.

        Falls back to the configured default size when geometry has
        never been saved yet, "Remember Window Position and Size" is
        turned off, or the saved geometry fails to restore (for example,
        it was saved on a monitor that is no longer connected).
        """
        self.resize(
            self.settings_manager.get("ui.window_width"),
            self.settings_manager.get("ui.window_height"),
        )

        if not self.settings_manager.get("ui.remember_window_geometry"):
            return
        saved = self.settings_manager.get("ui.window_geometry")
        if not saved:
            return
        geometry = QByteArray.fromBase64(saved.encode("ascii"))
        self.restoreGeometry(geometry)

    def _apply_tooltip_settings(self):
        """Clear button tooltips if the user turned off Show Tooltips."""
        if self.settings_manager.get("ui.show_tooltips"):
            self.monitor_button.setToolTip(
                "Continuously monitor the camera live feed with real-time frame analysis"
            )
            self.scan_button.setToolTip(
                "Run a frequency sweep and analyze the plate response at multiple frequencies"
            )
        else:
            self.monitor_button.setToolTip("")
            self.scan_button.setToolTip("")

    def closeEvent(self, event):
        """Save window position and size before closing, if enabled."""
        if self.settings_manager.get("ui.remember_window_geometry"):
            geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.settings_manager.set("ui.window_geometry", geometry)
            self.settings_manager.save()
        super().closeEvent(event)

    def _on_monitor_clicked(self):
        """
        Handle Monitor Camera button click.

        Launches monitor_gui.py's dashboard in its own window.

        Example:
            # Called automatically when user clicks "Monitor Mode" button
        """
        self._launch_child_window(
            attr_name="_monitor_window",
            button=self.monitor_button,
            window_factory=self._create_monitor_window,
            label="Monitor Mode",
        )

    def _create_monitor_window(self):
        """
        Build monitor_gui.py's MainWindow.

        A local import, done only when the button is actually clicked,
        keeps camera and matplotlib dependencies out of the landing
        page's startup path until Monitor Mode is actually needed.
        """
        self._sync_settings_to_espi_full_algorithm()
        _ensure_espi_algorithm_on_path()
        from monitor_gui import MainWindow as MonitorWindow

        return MonitorWindow()

    def _on_scan_clicked(self):
        """
        Handle Run Experiment button click.

        Launches run_experiment_gui.py's dashboard in its own window.

        Example:
            # Called automatically when user clicks "Scan Mode" button
        """
        self._launch_child_window(
            attr_name="_scan_window",
            button=self.scan_button,
            window_factory=self._create_scan_window,
            label="Scan Mode",
        )

    def _create_scan_window(self):
        """
        Build run_experiment_gui.py's MainWindow.

        Its __init__ applies its own theme stylesheet (reading the same
        settings file _sync_settings_to_espi_full_algorithm() just wrote
        to), matching monitor_gui.MainWindow's behavior.
        """
        self._sync_settings_to_espi_full_algorithm()
        _ensure_espi_algorithm_on_path()
        from run_experiment_gui import MainWindow as ScanWindow

        return ScanWindow()

    def _sync_settings_to_espi_full_algorithm(self, theme_override=None):
        """
        Bridge look-and-feel settings into ESPI Full Algorithm's own
        settings file (~/.espi/settings.json via settings_manager.py),
        which monitor_gui.py and run_experiment_gui.py read their own
        defaults from. Called at every dashboard launch and every theme
        change — safe to re-run any time, since none of this can clobber
        a value the user set locally inside either dashboard.

        Theme and preview size always follow espi_app's choice, since
        those are purely how-it-looks / how-big-it-starts preferences
        that should always match the landing page. "Use Last Settings as
        Default" is bridged too (unconditionally, whatever its value),
        since both dashboards read it to decide whether to lock their own
        default-value fields and whether to auto-save on a run.

        Camera/exposure/gain/gain_factor are deliberately NOT bridged
        here — see _push_hardware_defaults_to_espi_full_algorithm(),
        which only runs from an explicit Settings Save, not from simply
        opening a dashboard.

        Args:
            theme_override: Use this theme instead of reading
                self.settings_manager's — needed because _on_theme_changed
                calls this before the just-saved theme is necessarily
                reflected in self.settings_manager yet.
        """
        _ensure_espi_algorithm_on_path()
        import settings_manager

        other_settings = settings_manager.load_settings()
        other_settings["theme"] = theme_override or self.settings_manager.get("ui.theme")
        other_settings["preview_size"] = self.settings_manager.get("hardware.preview_size")
        other_settings["use_last_settings_as_default"] = self.settings_manager.get(
            "persistence.user_last_settings_as_default"
        )

        settings_manager.save_settings(other_settings)

    def _push_hardware_defaults_to_espi_full_algorithm(self):
        """
        Push espi_app's own Hardware tab values (camera, exposure, gain,
        gain factor) into both dashboards' settings keys.

        Only ever called from a Settings Save that actually had these
        fields editable (see the hardware_defaults_changed signal in
        settings_dialog.py) — never from opening a dashboard, and never
        while "Use Last Settings as Default" has them locked. That is
        what makes a value the user set locally inside a dashboard's own
        settings stick, instead of getting silently overwritten the next
        time that dashboard is simply reopened from espi_app.

        The same camera choice and exposure/gain/gain_factor numbers are
        pushed to both dashboards: monitor_gui.py's own monitor_default_*
        keys, and run_experiment_gui.py's default_* keys (camera choice
        is one key shared by both already).
        """
        # This fires from inside the Settings dialog's still-running modal
        # loop (see hardware_defaults_changed's docstring in
        # settings_dialog.py), before self.settings_manager necessarily
        # reflects what was just saved — reload first, same reason
        # _on_theme_changed() does.
        self.settings_manager = SettingsManager()

        _ensure_espi_algorithm_on_path()
        import settings_manager

        other_settings = settings_manager.load_settings()
        camera_choice = self.settings_manager.get("hardware.default_camera_choice")
        exposure = self.settings_manager.get("hardware.exposure_s")
        gain = float(self.settings_manager.get("persistence.default_gain"))
        gain_factor = float(self.settings_manager.get("persistence.default_gain_factor"))

        other_settings["default_camera_choice"] = camera_choice
        other_settings["default_exposure"] = exposure
        other_settings["default_gain"] = gain
        other_settings["default_gain_factor"] = gain_factor
        other_settings["monitor_default_exposure"] = exposure
        other_settings["monitor_default_gain"] = gain
        other_settings["monitor_default_gain_factor"] = gain_factor

        settings_manager.save_settings(other_settings)

    def refresh_theme_icons(self, theme_name):
        """
        Re-color this window's own qtawesome icons for the given theme.

        A QIcon is a static bitmap baked at one fixed color — unlike the
        stylesheet-driven colors elsewhere, it does not follow along when
        the app's stylesheet changes, so each icon has to be re-created.
        """
        current_icon_color = icon_color(theme_name)
        self.monitor_button.setIcon(qta.icon('mdi.camera', color=current_icon_color))
        self.scan_button.setIcon(qta.icon('mdi.pulse', color=current_icon_color))
        self.settings_button.setIcon(qta.icon('mdi.cog', color=current_icon_color))
        self.help_button.setIcon(qta.icon('mdi.help', color=current_icon_color))

    def _launch_child_window(self, attr_name, button, window_factory, label):
        """
        Show a Monitor/Scan dashboard window, guarding against common bugs.

        Args:
            attr_name: Name of the self attribute holding this window
                ("_monitor_window" or "_scan_window"), used so a second
                click while one is already open focuses it instead of
                opening a duplicate.
            button: The landing page button that triggered this, disabled
                while its window is open.
            window_factory: Zero-argument callable that imports and
                constructs the child window.
            label: Human readable mode name, used in error messages.
        """
        existing = getattr(self, attr_name)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return

        button.setEnabled(False)

        try:
            window = window_factory()
        except Exception as e:
            button.setEnabled(True)
            QMessageBox.critical(
                self, f"{label} Error", f"Could not open {label}:\n{e}"
            )
            return

        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        setattr(self, attr_name, window)

        def _on_child_closed():
            setattr(self, attr_name, None)
            button.setEnabled(True)

        window.destroyed.connect(_on_child_closed)
        window.show()

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
            # Connect hardware_defaults_changed to push camera/exposure/gain
            # to both dashboards — only fires when those fields were
            # actually editable at save time (see settings_dialog.py)
            dialog.hardware_defaults_changed.connect(
                self._push_hardware_defaults_to_espi_full_algorithm
            )
            dialog.exec()  # Show the dialog (modal)
        except Exception as e:
            import traceback
            error_msg = f"Error opening settings:\n{str(e)}\n\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Settings Error", error_msg)
        finally:
            # The dialog's SettingsDialog owns its own SettingsManager
            # instance, separate from self.settings_manager — reload here
            # so this window sees whatever was actually just saved (or,
            # on Cancel, simply re-reads the same unchanged file).
            self.settings_manager = SettingsManager()
            self._apply_tooltip_settings()

    def _on_theme_changed(self, new_theme: str):
        """
        Handle theme change from settings dialog.

        Args:
            new_theme: The new theme name ("light" or "dark")

        Example:
            # Called automatically when SettingsDialog emits theme_changed signal
            # Applies the new theme to the entire application, including
            # Monitor/Scan mode windows that are already open
        """
        # theme_changed fires from inside dialog.exec()'s still-running
        # modal loop, before _on_settings_clicked() gets a chance to
        # reload self.settings_manager — reload here too so
        # _sync_settings_to_espi_full_algorithm() (called below) does not
        # read stale hardware/persistence values from before this save.
        self.settings_manager = SettingsManager()

        app = QApplication.instance()
        apply_theme(app, new_theme)
        self.refresh_theme_icons(new_theme)

        # Keep the bridged settings file in sync so a Monitor/Scan window
        # opened later also starts on the new theme, not just windows
        # already open right now.
        self._sync_settings_to_espi_full_algorithm(theme_override=new_theme)

        if self._monitor_window is not None:
            self._monitor_window.refresh_theme(new_theme)
        if self._scan_window is not None:
            self._scan_window.refresh_theme(new_theme)

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

Monitor Camera
View a live feed from the camera with optional intensity graphs.
Use this to position your sample and verify camera settings.

Run Experiment
Run a frequency sweep from one frequency to another, measuring
the camera response at each step. Results are displayed after
the sweep completes.

Settings
Configure default values for exposure, gain, camera selection,
and display preferences. Settings are saved automatically.

For more information, see the project README.
        """
        QMessageBox.information(self, "Help", help_text.strip())
