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
    QBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QMessageBox,
    QApplication,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QByteArray

from espi_app.settings import SettingsManager
from espi_app.settings_dialog import SettingsDialog
from espi_app.styles import apply_theme, icon_color, landing_accent_colors, text_secondary_color
from espi_app.logo import ESPILogo
from espi_app.mode_card import ModeCard
from espi_app.background_decoration import LandingBackground
import qtawesome as qta

# Below this window width, the mode cards stack vertically instead of
# sitting side by side (see _apply_responsive_layout()).
_NARROW_WIDTH_BREAKPOINT = 800


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

        current_theme = self.settings_manager.get("ui.theme")
        current_icon_color = icon_color(current_theme)
        accents = landing_accent_colors(current_theme)

        # Central widget — everything goes here. LandingBackground paints
        # the shared theme background plus a subtle corner dot decoration
        # behind every widget added to it below.
        central = LandingBackground(current_theme, current_icon_color)
        self._background = central
        layout = QVBoxLayout()
        layout.setSpacing(16)  # Space between elements
        layout.setContentsMargins(32, 32, 32, 32)  # Padding around edges

        # --- Logo ---
        self.logo = ESPILogo(current_theme, size_px=100)
        logo_row = QHBoxLayout()
        logo_row.addStretch()
        logo_row.addWidget(self.logo)
        logo_row.addStretch()
        layout.addLayout(logo_row)
        layout.addSpacing(16)

        # --- Title ---
        title = QLabel("ESPI Camera System")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # --- Subtitle ---
        subtitle = QLabel("Electronic Speckle Pattern Interferometry Control")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # --- Small divider under the subtitle ---
        top_divider = QFrame()
        top_divider.setFixedSize(24, 2)
        top_divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        top_divider.setStyleSheet(f"background-color: {accents['divider_color']}; border: none;")
        top_divider_row = QHBoxLayout()
        top_divider_row.addStretch()
        top_divider_row.addWidget(top_divider)
        top_divider_row.addStretch()
        layout.addLayout(top_divider_row)

        layout.addSpacing(32)

        # --- Mode selection cards ---
        # A QBoxLayout (QHBoxLayout is one) can switch orientation live via
        # setDirection(), which is what makes the cards stack vertically on
        # a narrow window instead of side by side — see
        # _apply_responsive_layout(), called once here and again from
        # resizeEvent().
        self._card_layout = QHBoxLayout()
        self._card_layout.setSpacing(24)

        self.monitor_card = ModeCard(
            'mdi6.camera-iris', "Monitor Mode",
            "Real-time observation\nand live data monitoring",
            current_icon_color, accents["icon_badge_bg"], accents["divider_color"],
        )
        self.monitor_card.setToolTip("Continuously monitor the camera live feed with real-time frame analysis")
        self.monitor_card.clicked.connect(self._on_monitor_clicked)
        self._card_layout.addWidget(self.monitor_card)

        self.scan_card = ModeCard(
            'mdi6.radar', "Scan Mode",
            "Frequency sweep analysis\nand vibrometry scanning",
            current_icon_color, accents["icon_badge_bg"], accents["divider_color"],
        )
        self.scan_card.setToolTip("Run a frequency sweep and analyze the plate response at multiple frequencies")
        self.scan_card.clicked.connect(self._on_scan_clicked)
        self._card_layout.addWidget(self.scan_card)

        self._apply_card_stylesheet(current_theme, accents)
        layout.addLayout(self._card_layout)

        # --- Spacer (push everything up) ---
        layout.addStretch()

        # --- Bottom controls ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)
        bottom_layout.addStretch()

        # Settings button
        self.settings_button = QPushButton(qta.icon('mdi.cog', color=current_icon_color), "Settings")
        self.settings_button.setMinimumWidth(120)
        self.settings_button.clicked.connect(self._on_settings_clicked)
        bottom_layout.addWidget(self.settings_button)

        # Help button
        self.help_button = QPushButton(qta.icon('mdi.help-circle-outline', color=current_icon_color), "Help")
        self.help_button.setMinimumWidth(120)
        self.help_button.clicked.connect(self._on_help_clicked)
        bottom_layout.addWidget(self.help_button)

        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

        layout.addSpacing(20)

        # --- Footer, with small dots flanking the text ---
        footer_font = QFont()
        footer_font.setPointSize(9)
        footer_color_qss = f"color: {text_secondary_color(current_theme)};"

        self.footer_left_dot = QLabel("•")
        self.footer_left_dot.setFont(footer_font)
        self.footer_left_dot.setStyleSheet(footer_color_qss)
        self.footer_right_dot = QLabel("•")
        self.footer_right_dot.setFont(footer_font)
        self.footer_right_dot.setStyleSheet(footer_color_qss)

        self.footer_label = QLabel("Select a mode to begin")
        self.footer_label.setFont(footer_font)
        self.footer_label.setStyleSheet(footer_color_qss)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)
        footer_row.addStretch()
        footer_row.addWidget(self.footer_left_dot)
        footer_row.addWidget(self.footer_label)
        footer_row.addWidget(self.footer_right_dot)
        footer_row.addStretch()
        layout.addLayout(footer_row)

        # Set central widget
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._apply_tooltip_settings()
        self._apply_responsive_layout()

    def _apply_card_stylesheet(self, theme_name: str, accents: dict):
        """
        Style the mode cards from espi_app's own landing-page tokens (see
        espi_app/styles.py's landing_accent_colors()) — deliberately not
        part of the shared ESPI Full Algorithm/theme.py, which stays
        monochrome for monitor_gui.py and run_experiment_gui.py too.
        """
        description_color = text_secondary_color(theme_name)
        card_qss = f"""
            #ModeCard {{
                background-color: {accents["card_bg"]};
                border: 1px solid {accents["card_border"]};
                border-radius: 16px;
            }}
            #ModeCard:hover {{
                background-color: {accents["card_hover_bg"]};
            }}
            #ModeCardDescription {{
                color: {description_color};
            }}
        """
        self.monitor_card.setStyleSheet(card_qss)
        self.scan_card.setStyleSheet(card_qss)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self):
        """Stack the mode cards vertically below _NARROW_WIDTH_BREAKPOINT."""
        if self.width() <= _NARROW_WIDTH_BREAKPOINT:
            self._card_layout.setDirection(QBoxLayout.Direction.TopToBottom)
        else:
            self._card_layout.setDirection(QBoxLayout.Direction.LeftToRight)

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
        """Clear card tooltips if the user turned off Show Tooltips."""
        if self.settings_manager.get("ui.show_tooltips"):
            self.monitor_card.setToolTip(
                "Continuously monitor the camera live feed with real-time frame analysis"
            )
            self.scan_card.setToolTip(
                "Run a frequency sweep and analyze the plate response at multiple frequencies"
            )
        else:
            self.monitor_card.setToolTip("")
            self.scan_card.setToolTip("")

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
            button=self.monitor_card,
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
            button=self.scan_card,
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
        Re-color this window's own qtawesome icons, the logo, and the
        mode cards for the given theme.

        A QIcon is a static bitmap baked at one fixed color — unlike the
        stylesheet-driven colors elsewhere, it does not follow along when
        the app's stylesheet changes, so each icon has to be re-created.
        The mode cards' colors are espi_app's own landing-page-only tokens
        (see espi_app/styles.py's landing_accent_colors()), not part of
        the shared theme, so they are re-applied here too rather than by
        the app-wide stylesheet.
        """
        current_icon_color = icon_color(theme_name)
        self.settings_button.setIcon(qta.icon('mdi.cog', color=current_icon_color))
        self.help_button.setIcon(qta.icon('mdi.help-circle-outline', color=current_icon_color))
        self._background.set_theme(theme_name, current_icon_color)

        accents = landing_accent_colors(theme_name)
        self.logo.set_theme(theme_name)
        self.monitor_card.set_colors(current_icon_color, accents["icon_badge_bg"])
        self.scan_card.set_colors(current_icon_color, accents["icon_badge_bg"])
        self._apply_card_stylesheet(theme_name, accents)

        footer_color_qss = f"color: {text_secondary_color(theme_name)};"
        self.footer_label.setStyleSheet(footer_color_qss)
        self.footer_left_dot.setStyleSheet(footer_color_qss)
        self.footer_right_dot.setStyleSheet(footer_color_qss)

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
