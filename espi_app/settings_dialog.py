"""
settings_dialog.py

Settings dialog — allows users to configure application preferences.

The dialog is organized into tabs:
1. Hardware — camera choice, exposure, gain, gain factor, preview size
2. UI — theme selection, persistence, window behavior
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QPushButton,
)
from PyQt6.QtCore import pyqtSignal

from espi_app.settings import SettingsManager


def _ensure_espi_algorithm_on_path():
    """
    Add the ESPI Full Algorithm folder to sys.path so its settings_manager
    can be imported. A local copy of the same helper in main_window.py and
    styles.py — kept local rather than imported from main_window.py to
    avoid a circular import (main_window.py itself imports SettingsDialog
    from this file).
    """
    algo_dir = Path(__file__).resolve().parent.parent / "ESPI Full Algorithm"
    if str(algo_dir) not in sys.path:
        sys.path.insert(0, str(algo_dir))


# Camera choices (same as in run_experiment.py)
CAMERA_NAMES = {
    "1": "Basler",
    "2": "USB / webcam (eg. elp camera)",
    "3": "Allied Vision",
}

# Preview window size choices, mapped to pixel dimensions.
PREVIEW_SIZES = {
    "Small": (640, 480),
    "Medium": (1024, 768),
    "Large": (1920, 1080),
}


class SettingsDialog(QDialog):
    """
    Modal dialog for configuring application settings.

    Users can adjust hardware settings (camera, exposure, gain, gain
    factor, preview size) and UI preferences (theme, persistence,
    window behavior).

    Settings are saved to disk when the user clicks "Save".

    Signals:
        theme_changed: Emitted with (new_theme_name) when user saves a theme change
        hardware_defaults_changed: Emitted (no args) when the Hardware tab's
            camera/exposure/gain/gain_factor fields were editable (i.e. "Use
            Last Settings as Default" was off) and just got saved, so the
            landing page can push them out to Monitor/Scan mode's own
            settings file. Not emitted when those fields were locked —
            they're auto-managed in that case, not being set by hand here.
    """

    theme_changed = pyqtSignal(str)
    hardware_defaults_changed = pyqtSignal()

    def __init__(self, parent=None):
        """
        Initialize the settings dialog.

        Args:
            parent: Parent widget (usually the main window)

        Example:
            dialog = SettingsDialog(parent=main_window)
            dialog.exec()  # Show dialog (modal)
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 400)

        # Load current settings
        self.settings_manager = SettingsManager()

        # Build the UI
        layout = QVBoxLayout()

        # --- Tab widget ---
        self.tabs = QTabWidget()

        # Create each tab
        self.hardware_tab = self._create_hardware_tab()
        self.ui_tab = self._create_ui_tab()

        # Add tabs
        self.tabs.addTab(self.hardware_tab, "Hardware")
        self.tabs.addTab(self.ui_tab, "UI")

        layout.addWidget(self.tabs)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Push buttons to the right

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_hardware_tab(self) -> QWidget:
        """
        Create the Hardware tab.

        Settings on this tab:
        - Default Camera selection
        - Default Exposure time (in seconds)
        - Default Gain value
        - Default Gain Factor value
        - Preview Window Size (Small/Medium/Large)

        When "Use Last Settings as Default" is on, the camera/exposure/gain/
        gain factor fields are disabled and instead show whatever was
        actually last used in Monitor Mode or Scan Mode (see
        _default_value_source()) — these values are now managed
        automatically, not typed in by hand. Preview Window Size stays
        editable either way, since it is a window-size preference, not a
        measurement default.

        Returns:
            QWidget: The hardware tab widget

        Example:
            # Called automatically during __init__()
            # User can adjust exposure from 0.001 to 10.0 seconds
            # User can set gain and gain factor from 0 to 100
        """
        widget = QWidget()
        layout = QVBoxLayout()

        locked = self.settings_manager.get("persistence.user_last_settings_as_default")
        camera_choice, exposure, gain, gain_factor = self._default_value_source(locked)
        # Default Gain / Gain Factor are QSpinBox (integers), but the
        # dashboards' own gain widgets are QDoubleSpinBox (real decimals) —
        # round rather than truncate so display is as close as possible.
        gain = round(gain)
        gain_factor = round(gain_factor)

        # --- Camera selection ---
        layout.addWidget(QLabel("Default Camera:"))
        self.camera_combo = QComboBox()

        # Add camera options with their choice codes
        # Store the choice code ("1", "2", "3") as userdata
        for choice_code, camera_name in CAMERA_NAMES.items():
            self.camera_combo.addItem(camera_name, choice_code)

        current_index = self.camera_combo.findData(camera_choice)
        if current_index >= 0:
            self.camera_combo.setCurrentIndex(current_index)
        else:
            self.camera_combo.setCurrentIndex(0)  # Default to first option
        self.camera_combo.setEnabled(not locked)

        layout.addWidget(self.camera_combo)

        # --- Exposure time ---
        layout.addWidget(QLabel("Default Exposure (s):"))
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setMinimum(0.001)
        self.exposure_spin.setMaximum(10.0)
        self.exposure_spin.setDecimals(3)
        self.exposure_spin.setValue(exposure)
        self.exposure_spin.setEnabled(not locked)
        layout.addWidget(self.exposure_spin)

        # --- Gain ---
        layout.addWidget(QLabel("Default Gain:"))
        self.default_gain_spin = QSpinBox()
        self.default_gain_spin.setMinimum(0)
        self.default_gain_spin.setMaximum(100)
        self.default_gain_spin.setValue(gain)
        self.default_gain_spin.setEnabled(not locked)
        layout.addWidget(self.default_gain_spin)

        # --- Gain Factor ---
        layout.addWidget(QLabel("Default Gain Factor:"))
        self.default_gain_factor_spin = QSpinBox()
        self.default_gain_factor_spin.setMinimum(0)
        self.default_gain_factor_spin.setMaximum(100)
        self.default_gain_factor_spin.setValue(gain_factor)
        self.default_gain_factor_spin.setEnabled(not locked)
        layout.addWidget(self.default_gain_factor_spin)

        # --- Preview window size ---
        layout.addWidget(QLabel("Preview Window Size:"))
        self.preview_size_combo = QComboBox()
        self.preview_size_combo.addItems(list(PREVIEW_SIZES.keys()))
        preview_size_index = self.preview_size_combo.findText(
            self.settings_manager.get("hardware.preview_size")
        )
        self.preview_size_combo.setCurrentIndex(max(preview_size_index, 0))
        layout.addWidget(self.preview_size_combo)

        layout.addStretch()  # Fill remaining space
        widget.setLayout(layout)
        return widget

    def _default_value_source(self, locked: bool):
        """
        Return (camera_choice, exposure, gain, gain_factor) to display on
        the Hardware tab.

        If not locked, these are simply espi_app's own saved values — the
        normal, editable case. If locked ("Use Last Settings as Default"
        is on), read the shared ESPI Full Algorithm settings file instead,
        and pick whichever dashboard's keys match "last_used_dashboard" —
        monitor_gui.py and run_experiment_gui.py keep separate
        exposure/gain/gain_factor keys (they have different historical
        defaults), so we cannot just read one fixed key regardless of
        which dashboard actually ran. Falls back to espi_app's own values
        if neither dashboard has auto-saved anything yet.
        """
        if not locked:
            return (
                self.settings_manager.get("hardware.default_camera_choice"),
                self.settings_manager.get("hardware.exposure_s"),
                self.settings_manager.get("persistence.default_gain"),
                self.settings_manager.get("persistence.default_gain_factor"),
            )

        _ensure_espi_algorithm_on_path()
        import settings_manager as espi_settings_manager

        other = espi_settings_manager.load_settings()
        last_used = other.get("last_used_dashboard")

        if last_used == "monitor":
            return (
                other.get("default_camera_choice"),
                other.get("monitor_default_exposure"),
                other.get("monitor_default_gain"),
                other.get("monitor_default_gain_factor"),
            )
        if last_used == "scan":
            return (
                other.get("default_camera_choice"),
                other.get("default_exposure"),
                other.get("default_gain"),
                other.get("default_gain_factor"),
            )

        # Neither dashboard has auto-saved yet — fall back to espi_app's
        # own values so the (disabled) fields show something sensible.
        return (
            self.settings_manager.get("hardware.default_camera_choice"),
            self.settings_manager.get("hardware.exposure_s"),
            self.settings_manager.get("persistence.default_gain"),
            self.settings_manager.get("persistence.default_gain_factor"),
        )

    def _create_ui_tab(self) -> QWidget:
        """
        Create the UI tab.

        Settings on this tab:
        - Theme selection (light/dark)
        - Use Last Settings as Default checkbox
        - Remember Window Position and Size checkbox
        - Show Tooltips checkbox

        Returns:
            QWidget: The UI tab widget

        Example:
            # Called automatically during __init__()
            # User can select light or dark theme
            # User can toggle whether to use last run's settings as defaults
        """
        widget = QWidget()
        layout = QVBoxLayout()

        # --- Theme selection ---
        layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        theme = self.settings_manager.get("ui.theme").capitalize()
        index = self.theme_combo.findText(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        layout.addWidget(self.theme_combo)

        # --- Use Last Settings as Default checkbox ---
        self.use_last_settings_check = QCheckBox("Use Last Settings as Default")
        self.use_last_settings_check.setChecked(
            self.settings_manager.get("persistence.user_last_settings_as_default")
        )
        layout.addWidget(self.use_last_settings_check)

        # --- Remember window position and size ---
        self.remember_geometry_check = QCheckBox("Remember Window Position and Size")
        self.remember_geometry_check.setChecked(
            self.settings_manager.get("ui.remember_window_geometry")
        )
        layout.addWidget(self.remember_geometry_check)

        # --- Show tooltips ---
        self.show_tooltips_check = QCheckBox("Show Tooltips")
        self.show_tooltips_check.setChecked(
            self.settings_manager.get("ui.show_tooltips")
        )
        layout.addWidget(self.show_tooltips_check)

        layout.addStretch()  # Fill remaining space
        widget.setLayout(layout)
        return widget

    def _on_save(self):
        """
        Save all settings and close the dialog.

        Collects values from all widgets and saves them to disk.

        If theme changed, emits theme_changed signal so the app can
        re-apply the theme immediately. If the Hardware tab's
        camera/exposure/gain/gain_factor fields were editable (not locked
        by "Use Last Settings as Default"), emits hardware_defaults_changed
        so the landing page can push them to Monitor/Scan mode.

        Example:
            # Called automatically when user clicks "Save" button
            # All settings are written to ~/.espi_app/settings.json
            # Dialog closes with accept() status
        """
        # Track the old theme to detect changes
        old_theme = self.settings_manager.get("ui.theme")
        # Whether the Hardware tab's default-value fields were editable
        # (not locked by "Use Last Settings as Default") — determines
        # whether hardware_defaults_changed fires below.
        hardware_fields_were_unlocked = self.camera_combo.isEnabled()

        # Hardware settings
        # Store the camera choice code ("1", "2", or "3"), not the index
        camera_choice = self.camera_combo.currentData()
        self.settings_manager.set("hardware.default_camera_choice", camera_choice)
        self.settings_manager.set("hardware.exposure_s", self.exposure_spin.value())
        self.settings_manager.set("hardware.control_gain", False)
        self.settings_manager.set("hardware.control_gain_factor", True)
        self.settings_manager.set(
            "hardware.preview_size", self.preview_size_combo.currentText()
        )

        # UI settings (including theme)
        new_theme = self.theme_combo.currentText().lower()
        self.settings_manager.set("ui.theme", new_theme)
        self.settings_manager.set(
            "ui.remember_window_geometry",
            self.remember_geometry_check.isChecked()
        )
        self.settings_manager.set(
            "ui.show_tooltips",
            self.show_tooltips_check.isChecked()
        )

        # Persistence settings
        self.settings_manager.set(
            "persistence.user_last_settings_as_default",
            self.use_last_settings_check.isChecked()
        )
        self.settings_manager.set(
            "persistence.default_exposure_s",
            self.exposure_spin.value()
        )
        self.settings_manager.set(
            "persistence.default_camera_choice",
            camera_choice
        )
        self.settings_manager.set(
            "persistence.default_gain",
            self.default_gain_spin.value()
        )
        self.settings_manager.set(
            "persistence.default_gain_factor",
            self.default_gain_factor_spin.value()
        )

        # Write to disk
        self.settings_manager.save()

        # Emit signal if theme changed
        if old_theme != new_theme:
            self.theme_changed.emit(new_theme)

        # Emit signal if the hardware defaults were actually editable
        # (i.e. not locked by "Use Last Settings as Default") — locked
        # fields are auto-managed, not something this Save should push.
        if hardware_fields_were_unlocked:
            self.hardware_defaults_changed.emit()

        # Close dialog (success)
        self.accept()
