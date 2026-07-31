"""
settings_dialog.py

Settings dialog — allows users to configure application preferences.

The dialog is organized into tabs:
1. Hardware — camera choice, exposure, frame rate, pixel format
2. Visualization — graph options, refresh rate
3. UI — theme selection
"""

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
from PyQt6.QtCore import Qt, pyqtSignal

from espi_app.settings import SettingsManager

# Camera choices (same as in run_experiment.py)
CAMERA_NAMES = {
    "1": "Basler",
    "2": "USB / webcam (eg. elp camera)",
    "3": "Allied Vision",
}


class SettingsDialog(QDialog):
    """
    Modal dialog for configuring application settings.

    Users can adjust hardware settings (exposure, gain), visualization
    preferences (which graphs to show), and UI preferences (theme).

    Settings are saved to disk when the user clicks "Save".

    Signals:
        theme_changed: Emitted with (new_theme_name) when user saves a theme change
    """

    theme_changed = pyqtSignal(str)

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
        self.visualization_tab = self._create_visualization_tab()
        self.ui_tab = self._create_ui_tab()

        # Add tabs
        self.tabs.addTab(self.hardware_tab, "Hardware")
        self.tabs.addTab(self.visualization_tab, "Visualization")
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

        Returns:
            QWidget: The hardware tab widget

        Example:
            # Called automatically during __init__()
            # User can adjust exposure from 0.001 to 10.0 seconds
            # User can set gain and gain factor from 0 to 100
        """
        widget = QWidget()
        layout = QVBoxLayout()

        # --- Camera selection ---
        layout.addWidget(QLabel("Default Camera:"))
        self.camera_combo = QComboBox()

        # Add camera options with their choice codes
        # Store the choice code ("1", "2", "3") as userdata
        for choice_code, camera_name in CAMERA_NAMES.items():
            self.camera_combo.addItem(camera_name, choice_code)

        # Load current camera choice
        camera_choice = self.settings_manager.get("hardware.default_camera_choice")
        current_index = self.camera_combo.findData(camera_choice)
        if current_index >= 0:
            self.camera_combo.setCurrentIndex(current_index)
        else:
            self.camera_combo.setCurrentIndex(0)  # Default to first option

        layout.addWidget(self.camera_combo)

        # --- Exposure time ---
        layout.addWidget(QLabel("Default Exposure (s):"))
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setMinimum(0.001)
        self.exposure_spin.setMaximum(10.0)
        self.exposure_spin.setDecimals(3)
        self.exposure_spin.setValue(
            self.settings_manager.get("hardware.exposure_s")
        )
        layout.addWidget(self.exposure_spin)

        # --- Gain ---
        layout.addWidget(QLabel("Default Gain:"))
        self.default_gain_spin = QSpinBox()
        self.default_gain_spin.setMinimum(0)
        self.default_gain_spin.setMaximum(100)
        self.default_gain_spin.setValue(
            self.settings_manager.get("persistence.default_gain")
        )
        layout.addWidget(self.default_gain_spin)

        # --- Gain Factor ---
        layout.addWidget(QLabel("Default Gain Factor:"))
        self.default_gain_factor_spin = QSpinBox()
        self.default_gain_factor_spin.setMinimum(0)
        self.default_gain_factor_spin.setMaximum(100)
        self.default_gain_factor_spin.setValue(
            self.settings_manager.get("persistence.default_gain_factor")
        )
        layout.addWidget(self.default_gain_factor_spin)

        layout.addStretch()  # Fill remaining space
        widget.setLayout(layout)
        return widget

    def _create_visualization_tab(self) -> QWidget:
        """
        Create the Visualization tab.

        Settings on this tab:
        - Show Intensity Graph checkbox (master toggle for graphs)
          - When ON: Show Histogram, Show 3D Graph, Show Log Histogram can be toggled
          - When OFF: Other graph options are disabled
        - Show Live Feed checkbox

        Returns:
            QWidget: The visualization tab widget

        Example:
            # Called automatically during __init__()
            # Live feed is shown first, then intensity graph master toggle
            # Graph type options are indented and depend on intensity graph state
        """
        widget = QWidget()
        layout = QVBoxLayout()

        # --- Live feed checkbox ---
        self.show_live_feed_check = QCheckBox("Show Live Feed")
        self.show_live_feed_check.setChecked(
            self.settings_manager.get("visualization.show_live_feed")
        )
        layout.addWidget(self.show_live_feed_check)

        # --- Intensity graph checkbox (master toggle) ---
        self.show_intensity_check = QCheckBox("Show Intensity Graphs")
        self.show_intensity_check.setChecked(
            self.settings_manager.get("visualization.show_intensity_graph")
        )
        self.show_intensity_check.stateChanged.connect(self._on_intensity_graph_toggled)
        layout.addWidget(self.show_intensity_check)

        # --- Graph type options (only enabled when intensity graphs are ON) ---
        layout.addWidget(QLabel("Graph Types (when intensity graphs are enabled):"))

        self.show_histogram_check = QCheckBox("Show Histogram")
        self.show_histogram_check.setChecked(
            self.settings_manager.get("visualization.show_histogram")
        )
        layout.addWidget(self.show_histogram_check)

        self.show_3d_check = QCheckBox("Show 3D Surface Plot")
        self.show_3d_check.setChecked(
            self.settings_manager.get("visualization.show_3d_graph")
        )
        layout.addWidget(self.show_3d_check)

        self.show_log_histogram_check = QCheckBox("Show Log Histogram")
        self.show_log_histogram_check.setChecked(
            self.settings_manager.get("visualization.show_log_histogram")
        )
        layout.addWidget(self.show_log_histogram_check)

        # Set initial enabled/disabled state of graph type options
        self._update_graph_options_enabled_state()

        layout.addStretch()  # Fill remaining space
        widget.setLayout(layout)
        return widget

    def _create_ui_tab(self) -> QWidget:
        """
        Create the UI tab.

        Settings on this tab:
        - Theme selection (light/dark)
        - Use Last Settings as Default checkbox

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

        layout.addStretch()  # Fill remaining space
        widget.setLayout(layout)
        return widget

    def _update_graph_options_enabled_state(self) -> None:
        """
        Enable or disable graph type options based on show_intensity_graph state.

        If show_intensity_graph is ON, graph type options are enabled.
        If show_intensity_graph is OFF, graph type options are disabled.

        Example:
            # Called automatically when intensity graph toggle is clicked
            # or during initialization to set the correct initial state
        """
        intensity_enabled = self.show_intensity_check.isChecked()
        self.show_histogram_check.setEnabled(intensity_enabled)
        self.show_3d_check.setEnabled(intensity_enabled)
        self.show_log_histogram_check.setEnabled(intensity_enabled)

    def _on_intensity_graph_toggled(self) -> None:
        """
        Handle when the intensity graph master toggle is clicked.

        Example:
            # Called automatically when user clicks the intensity graph checkbox
            # Updates the enabled state of graph type options
        """
        self._update_graph_options_enabled_state()

    def _on_save(self):
        """
        Save all settings and close the dialog.

        Collects values from all widgets and saves them to disk.
        If "Use Last Settings as Default" is enabled, stores current
        exposure, camera, gain, and gain_factor as new defaults.

        If theme changed, emits theme_changed signal so the app can
        re-apply the theme immediately.

        Example:
            # Called automatically when user clicks "Save" button
            # All settings are written to ~/.espi_app/settings.json
            # Dialog closes with accept() status
        """
        # Track the old theme to detect changes
        old_theme = self.settings_manager.get("ui.theme")

        # Hardware settings
        # Store the camera choice code ("1", "2", or "3"), not the index
        camera_choice = self.camera_combo.currentData()
        self.settings_manager.set("hardware.default_camera_choice", camera_choice)
        self.settings_manager.set("hardware.exposure_s", self.exposure_spin.value())
        self.settings_manager.set("hardware.control_gain", False)
        self.settings_manager.set("hardware.control_gain_factor", True)

        # Visualization settings
        self.settings_manager.set(
            "visualization.show_intensity_graph",
            self.show_intensity_check.isChecked()
        )
        self.settings_manager.set(
            "visualization.show_histogram",
            self.show_histogram_check.isChecked()
        )
        self.settings_manager.set(
            "visualization.show_3d_graph",
            self.show_3d_check.isChecked()
        )
        self.settings_manager.set(
            "visualization.show_log_histogram",
            self.show_log_histogram_check.isChecked()
        )
        self.settings_manager.set(
            "visualization.show_live_feed",
            self.show_live_feed_check.isChecked()
        )

        # UI settings (including theme)
        new_theme = self.theme_combo.currentText().lower()
        self.settings_manager.set("ui.theme", new_theme)

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

        # Close dialog (success)
        self.accept()
