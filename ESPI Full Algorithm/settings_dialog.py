"""
settings_dialog.py
==================
Settings page UI for run_experiment_gui.

Provides a comprehensive settings page where users can configure:
- Grayscale conversion method (standard vs single-channel)
- Default camera and camera index
- Capture settings defaults (exposure, gain, gain_factor, frequencies, n_averages)
- Live monitoring during sweep option

All settings are loaded from and saved to disk via settings_manager.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QRadioButton,
    QButtonGroup, QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QPushButton,
    QDialog, QTextBrowser, QScrollArea, QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

import qtawesome as qta
from settings_manager import load_settings, save_settings, validate_settings


# Color palette (matches monitor_gui styling)
_TEXT_PRIMARY = "#e0e0e0"
_TEXT_SECONDARY = "#8a8a8a"
_BG_PRIMARY = "#1e1e1e"
_BG_SECONDARY = "#252525"


class LearnMoreDialog(QDialog):
    """
    Popup dialog showing plain language explanations of settings groups.

    Used when user clicks "Learn More" button in a group. Displays HTML
    content in a scrollable QTextBrowser with a Close button.
    """

    def __init__(self, title: str, html_content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 460)

        self.browser = QTextBrowser()
        self.browser.setObjectName("LearnMoreBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(html_content)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        layout.addWidget(self.close_button)
        self.setLayout(layout)


class SettingsPage(QWidget):
    """
    Settings configuration page for run_experiment_gui.

    Displays four logical groups:
    1. Grayscale Conversion Method (standard vs single-channel)
    2. Default Camera (Basler/USB/Allied Vision + index)
    3. Capture Settings Defaults (exposure, gain, frequencies, n_averages, gain_factor)
    4. Live Monitoring During Sweep toggle

    All controls automatically load/save from settings_manager.
    """

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ========== Group 1: Grayscale Conversion Method ==========
        grayscale_group = QGroupBox("Grayscale Conversion Method")
        grayscale_layout = QVBoxLayout()

        # Learn More button
        self._grayscale_learn_more = QPushButton("Learn More")
        self._grayscale_learn_more.setIcon(
            qta.icon('mdi6.help-circle-outline', color=QColor(_TEXT_SECONDARY))
        )
        self._grayscale_learn_more.setObjectName("LearnMoreButton")
        self._grayscale_learn_more.clicked.connect(
            lambda: LearnMoreDialog(
                "About Grayscale Conversion",
                _GRAYSCALE_HELP_HTML,
                self
            ).exec()
        )
        learn_row = QHBoxLayout()
        learn_row.addStretch()
        learn_row.addWidget(self._grayscale_learn_more)
        grayscale_layout.addLayout(learn_row)

        # Radio buttons
        self._grayscale_group = QButtonGroup()
        self._grayscale_radios = {}

        standard_radio = QRadioButton("Standard Full-RGB")
        standard_radio.setToolTip("Blend all color channels using luminosity weighting")
        self._grayscale_group.addButton(standard_radio)
        self._grayscale_radios["standard"] = standard_radio
        grayscale_layout.addWidget(standard_radio)

        single_radio = QRadioButton("Single-Channel Extraction")
        single_radio.setToolTip("Extract a single color channel (R, G, or B)")
        self._grayscale_group.addButton(single_radio)
        self._grayscale_radios["single_channel"] = single_radio
        grayscale_layout.addWidget(single_radio)

        # Color and backend controls (hidden for standard)
        self._color_label = QLabel("Target Color Channel:")
        self._color_combo = QComboBox()
        self._color_combo.addItems(["Red (R)", "Green (G)", "Blue (B)"])
        self._color_combo.setCurrentIndex(0)

        color_layout = QHBoxLayout()
        color_layout.addWidget(self._color_label)
        color_layout.addWidget(self._color_combo)
        color_layout.addStretch()
        grayscale_layout.addLayout(color_layout)

        self._backend_label = QLabel("Processing Algorithm:")
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["NumPy (Fast)", "Pillow", "OpenCV HSV"])
        self._backend_combo.setCurrentIndex(0)

        backend_layout = QHBoxLayout()
        backend_layout.addWidget(self._backend_label)
        backend_layout.addWidget(self._backend_combo)
        backend_layout.addStretch()
        grayscale_layout.addLayout(backend_layout)

        grayscale_layout.addStretch()
        grayscale_group.setLayout(grayscale_layout)
        layout.addWidget(grayscale_group)

        # Wire visibility updates BEFORE setting initial state
        for radio in self._grayscale_radios.values():
            radio.toggled.connect(self._update_grayscale_visibility)

        self._grayscale_radios["standard"].setChecked(True)

        # ========== Group 2: Default Camera ==========
        camera_group = QGroupBox("Default Camera")
        camera_layout = QVBoxLayout()

        # Learn More button
        self._camera_learn_more = QPushButton("Learn More")
        self._camera_learn_more.setIcon(
            qta.icon('mdi6.help-circle-outline', color=QColor(_TEXT_SECONDARY))
        )
        self._camera_learn_more.clicked.connect(
            lambda: LearnMoreDialog(
                "About Camera Selection",
                _CAMERA_HELP_HTML,
                self
            ).exec()
        )
        cam_learn_row = QHBoxLayout()
        cam_learn_row.addStretch()
        cam_learn_row.addWidget(self._camera_learn_more)
        camera_layout.addLayout(cam_learn_row)

        # Camera choice radio buttons
        self._camera_group = QButtonGroup()
        self._camera_radios = {}

        for choice, name, icon_name in [
            ("1", "Basler camera", "mdi6.camera"),
            ("2", "USB / webcam (OpenCV)", "mdi6.usb"),
            ("3", "Allied Vision (Vimba X)", "mdi6.camera-outline"),
        ]:
            radio = QRadioButton(name)
            radio.setIcon(qta.icon(icon_name, color=QColor(_TEXT_PRIMARY)))
            self._camera_group.addButton(radio)
            self._camera_radios[choice] = radio
            camera_layout.addWidget(radio)

        self._camera_radios["2"].setChecked(True)

        # Camera index (hidden for Basler)
        self._index_label = QLabel("Camera index (0 = first device):")
        self._index_spin = QSpinBox()
        self._index_spin.setRange(0, 10)
        self._index_spin.setValue(0)

        index_layout = QHBoxLayout()
        index_layout.addWidget(self._index_label)
        index_layout.addWidget(self._index_spin)
        index_layout.addStretch()
        camera_layout.addLayout(index_layout)

        camera_layout.addStretch()
        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)

        # Wire camera visibility updates (will be called at end of __init__)
        for radio in self._camera_radios.values():
            radio.toggled.connect(lambda checked: self._update_camera_visibility())

        # ========== Group 3: Capture Settings Defaults ==========
        capture_group = QGroupBox("Capture Settings Defaults")
        capture_layout = QVBoxLayout()

        # Learn More button
        self._capture_learn_more = QPushButton("Learn More")
        self._capture_learn_more.setIcon(
            qta.icon('mdi6.help-circle-outline', color=QColor(_TEXT_SECONDARY))
        )
        self._capture_learn_more.clicked.connect(
            lambda: LearnMoreDialog(
                "About Capture Settings",
                _CAPTURE_HELP_HTML,
                self
            ).exec()
        )
        cap_learn_row = QHBoxLayout()
        cap_learn_row.addStretch()
        cap_learn_row.addWidget(self._capture_learn_more)
        capture_layout.addLayout(cap_learn_row)

        # Show Gain toggle
        self._show_gain_checkbox = QCheckBox("Show Gain (dB) control")
        self._show_gain_checkbox.setChecked(False)
        # Use lambda to ensure the slot is always called with update
        self._show_gain_checkbox.toggled.connect(lambda: self._update_capture_visibility())
        capture_layout.addWidget(self._show_gain_checkbox)

        # Frequency range
        capture_layout.addWidget(QLabel("Start Frequency (Hz):"))
        self.start_freq_spin = QDoubleSpinBox()
        self.start_freq_spin.setRange(0, 100000)
        self.start_freq_spin.setValue(100.0)
        capture_layout.addWidget(self.start_freq_spin)

        capture_layout.addWidget(QLabel("End Frequency (Hz):"))
        self.end_freq_spin = QDoubleSpinBox()
        self.end_freq_spin.setRange(0, 100000)
        self.end_freq_spin.setValue(1000.0)
        capture_layout.addWidget(self.end_freq_spin)

        capture_layout.addWidget(QLabel("Step Size (Hz):"))
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.1, 10000)
        self.step_spin.setValue(100.0)
        capture_layout.addWidget(self.step_spin)

        capture_layout.addWidget(QLabel("Frames Per Frequency:"))
        self.n_averages_spin = QSpinBox()
        self.n_averages_spin.setRange(1, 50)
        self.n_averages_spin.setValue(5)
        capture_layout.addWidget(self.n_averages_spin)

        capture_layout.addWidget(QLabel("Exposure (s):"))
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setDecimals(4)
        self.exposure_spin.setRange(0.0001, 10.0)
        self.exposure_spin.setSingleStep(0.01)
        self.exposure_spin.setValue(0.01)
        capture_layout.addWidget(self.exposure_spin)

        # Gain (shown only if checkbox is checked)
        self._gain_label = QLabel("Gain (dB):")
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setDecimals(2)
        self.gain_spin.setRange(-20.0, 50.0)
        self.gain_spin.setValue(0.0)
        capture_layout.addWidget(self._gain_label)
        capture_layout.addWidget(self.gain_spin)

        capture_layout.addWidget(QLabel("Gain Factor (amplification):"))
        self.gain_factor_spin = QDoubleSpinBox()
        self.gain_factor_spin.setDecimals(2)
        self.gain_factor_spin.setRange(0.01, 200.0)
        self.gain_factor_spin.setValue(1.0)
        capture_layout.addWidget(self.gain_factor_spin)

        capture_layout.addStretch()
        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group)



        # ========== Group 4: Saved Image During Sweep ==========
        live_group = QGroupBox("Saved Image During Sweep")
        live_layout = QVBoxLayout()

        # Learn More button
        self._live_learn_more = QPushButton("Learn More")
        self._live_learn_more.setIcon(
            qta.icon('mdi6.help-circle-outline', color=QColor(_TEXT_SECONDARY))
        )
        self._live_learn_more.clicked.connect(
            lambda: LearnMoreDialog(
                "About the Saved Image Preview",
                _LIVE_HELP_HTML,
                self
            ).exec()
        )
        live_learn_row = QHBoxLayout()
        live_learn_row.addStretch()
        live_learn_row.addWidget(self._live_learn_more)
        live_layout.addLayout(live_learn_row)

        self._saved_image_checkbox = QCheckBox(
            "Show saved image after each capture"
        )
        self._saved_image_checkbox.setChecked(False)
        live_layout.addWidget(self._saved_image_checkbox)

        live_layout.addStretch()
        live_group.setLayout(live_layout)
        layout.addWidget(live_group)

        # ========== Save control ==========
        # This is the missing piece that caused the reported "settings
        # don't propagate" bug: save_settings() below always worked
        # correctly on its own, but nothing in the app ever called it, so
        # every change made here was silently discarded the moment the
        # user navigated to a different page. An explicit Save button is
        # the same predictable pattern SetupPage already uses (it saves
        # when the user clicks "Continue to Preview"): one clear action
        # the user takes, that always writes the whole current form state
        # to disk, rather than guessing which single field change should
        # trigger an autosave.
        self.save_button = QPushButton("Save Settings")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.setIcon(
            qta.icon('mdi6.content-save-outline', color=QColor(_TEXT_PRIMARY))
        )
        self.save_button.clicked.connect(self._on_save_clicked)
        layout.addWidget(self.save_button)

        self._save_status_label = QLabel("")
        self._save_status_label.setObjectName("SaveStatusLabel")
        layout.addWidget(self._save_status_label)

        # ========== Finalize Layout ==========
        layout.addStretch()

        # Wrap in scroll area
        scroll_widget = QWidget()
        scroll_widget.setLayout(layout)
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

        # Update visibility after widget tree is complete
        self._update_grayscale_visibility()
        self._update_camera_visibility()
        self._update_capture_visibility()

    def _update_grayscale_visibility(self):
        """Show/hide color and backend controls based on method selection."""
        is_single = self._grayscale_radios["single_channel"].isChecked()
        should_show = is_single
        # Use setVisible (which is more reliable than show/hide in this context)
        self._color_label.setVisible(should_show)
        self._color_combo.setVisible(should_show)
        self._backend_label.setVisible(should_show)
        self._backend_combo.setVisible(should_show)

    def _update_camera_visibility(self):
        """Show/hide camera index spinner for non-Basler cameras."""
        is_basler = self._camera_radios["1"].isChecked()
        should_show = not is_basler
        self._index_label.setVisible(should_show)
        self._index_spin.setVisible(should_show)

    def _update_capture_visibility(self):
        """Show/hide gain control based on checkbox."""
        should_show = self._show_gain_checkbox.isChecked()
        self._gain_label.setVisible(should_show)
        self.gain_spin.setVisible(should_show)

    def showEvent(self, event):
        """
        Reload from disk every time this page becomes visible, not just at
        construction time. Without this, navigating away without saving
        (or another part of the app changing settings) left this page
        showing stale state the next time the user opened it.
        """
        super().showEvent(event)
        self.load_settings()

    def _on_save_clicked(self):
        """Persist every control's current value to disk (see save_button above for why this exists)."""
        if self.save_settings():
            self._save_status_label.setText("Settings saved.")
        else:
            self._save_status_label.setText("Could not save settings — check the values above.")

    def load_settings(self):
        """Load settings from disk and populate controls."""
        settings = load_settings()

        # Grayscale
        method = settings.get("grayscale_method", "standard")
        self._grayscale_radios[method].setChecked(True)
        
        color_map = {"R": 0, "G": 1, "B": 2}
        color_idx = color_map.get(settings.get('grayscale_color', 'R'), 0)
        self._color_combo.setCurrentIndex(color_idx)

        backend_map = {"numpy": 0, "pillow": 1, "opencv_hsv": 2}
        backend = settings.get("grayscale_backend", "numpy")
        self._backend_combo.setCurrentIndex(backend_map.get(backend, 0))

        # Camera
        camera_choice = settings.get("default_camera_choice", "2")
        self._camera_radios[camera_choice].setChecked(True)
        self._index_spin.setValue(settings.get("default_camera_index", 0))

        # Capture
        self._show_gain_checkbox.setChecked(settings.get("show_gain", False))
        self.start_freq_spin.setValue(settings.get("default_start_freq", 100.0))
        self.end_freq_spin.setValue(settings.get("default_end_freq", 1000.0))
        self.step_spin.setValue(settings.get("default_step_size", 100.0))
        self.n_averages_spin.setValue(settings.get("default_n_averages", 5))
        self.exposure_spin.setValue(settings.get("default_exposure", 0.01))
        self.gain_spin.setValue(settings.get("default_gain", 0.0))
        self.gain_factor_spin.setValue(settings.get("default_gain_factor", 1.0))

        self._saved_image_checkbox.setChecked(
            settings.get("show_saved_image_after_capture", False)
        )

        self._apply_lock_state(settings)

    def _apply_lock_state(self, settings):
        """
        "Use Last Settings as Default" (set from espi_app's Settings
        dialog, bridged into this same settings file) means camera,
        index, frequency sweep, and capture fields are now auto-managed
        from whatever was actually last used to run a Preview or Sweep —
        this page exists specifically to hand-set those defaults, so it
        (including its own Save button) is locked while that is active.
        Grayscale, show-gain, and saved-image are unrelated
        display/processing preferences and stay editable either way.
        """
        locked = settings.get("use_last_settings_as_default", False)
        for radio in self._camera_radios.values():
            radio.setEnabled(not locked)
        self._index_spin.setEnabled(not locked)
        self.start_freq_spin.setEnabled(not locked)
        self.end_freq_spin.setEnabled(not locked)
        self.step_spin.setEnabled(not locked)
        self.n_averages_spin.setEnabled(not locked)
        self.exposure_spin.setEnabled(not locked)
        self.gain_spin.setEnabled(not locked)
        self.gain_factor_spin.setEnabled(not locked)
        self.save_button.setEnabled(not locked)

    def save_settings(self) -> bool:
        """Save current control values to disk."""
        color_text = self._color_combo.currentText()
        color_code = color_text.split(" ")[0][0]

        backend_map = {0: "numpy", 1: "pillow", 2: "opencv_hsv"}
        backend = backend_map[self._backend_combo.currentIndex()]

        # Get current camera choice
        camera_choice = None
        for choice, radio in self._camera_radios.items():
            if radio.isChecked():
                camera_choice = choice
                break

        settings = {
            "grayscale_method": "single_channel" if self._grayscale_radios["single_channel"].isChecked() else "standard",
            "grayscale_color": color_code,
            "grayscale_backend": backend,
            "default_camera_choice": camera_choice or "2",
            "default_camera_index": self._index_spin.value(),
            "show_gain": self._show_gain_checkbox.isChecked(),
            "default_start_freq": self.start_freq_spin.value(),
            "default_end_freq": self.end_freq_spin.value(),
            "default_step_size": self.step_spin.value(),
            "default_n_averages": self.n_averages_spin.value(),
            "default_exposure": self.exposure_spin.value(),
            "default_gain": self.gain_spin.value(),
            "default_gain_factor": self.gain_factor_spin.value(),
            "show_saved_image_after_capture": self._saved_image_checkbox.isChecked(),
        }

        if not validate_settings(settings):
            return False

        return save_settings(settings)


# ============================================================================
# LEARN MORE DIALOG CONTENT (Plain Language Explanations)
# ============================================================================

_GRAYSCALE_HELP_HTML = """
<h3>About Grayscale Conversion</h3>
<p>Your camera captures red, green, and blue light in every pixel, but ESPI
fringe patterns are about brightness changes, not color. Before comparing
frames, the color information must be reduced to one brightness value
per pixel. These options control how that reduction happens.</p>

<p><b>Standard Full-RGB</b> blends all three color channels using the same
weighting the human eye uses (green contributes more to perceived brightness
than red or blue). This is the default, general-purpose option.</p>

<p><b>Single-Channel Extraction</b> keeps only one color channel (Red, Green,
or Blue) and throws the others away. This is useful if your laser's color
matches one of the camera's channels strongly. The other channels mostly
contain noise, so dropping them gives a cleaner, higher-contrast signal.</p>
"""

_CAMERA_HELP_HTML = """
<h3>About Camera Selection</h3>
<p>Choose which type of camera you have connected. The software supports
three camera types, each with different hardware interfaces:</p>

<p><b>Basler camera</b> (uses pypylon SDK). Professional industrial camera
with Mono8 or Mono12 formats. The index is always 0 (no choice needed).</p>

<p><b>USB / webcam</b> (uses OpenCV). Any OpenCV-compatible camera, such as
a USB webcam or ELP Camera. If you have multiple cameras, use the index
selector to choose which one (0 = first device found).</p>

<p><b>Allied Vision (Vimba X)</b> (uses vmbpy SDK). Professional camera with
Vimba X drivers installed. Like USB cameras, supports multiple devices via
the index selector.</p>
"""

_CAPTURE_HELP_HTML = """
<h3>About Capture Settings Defaults</h3>
<p>These values pre-fill the setup wizard when you start the app.</p>

<p><b>Frequency range (Hz)</b>: Start and end frequencies for the sweep,
with step size. If step is 100 Hz and range is 100-1000 Hz, you will
measure at 100, 200, 300 ... 1000 Hz.</p>

<p><b>Frames per frequency</b>: How many frames to grab and average at each
frequency. More frames = less noise but slower sweep.</p>

<p><b>Exposure (seconds)</b>: How long to open the camera's sensor per frame.
0.01 = 10 milliseconds. Increase if images are too dark, decrease if too bright.</p>

<p><b>Gain (dB)</b> (optional): Camera gain amplification in decibels. Usually
left at 0 dB. Only shown if you enable it above.</p>

<p><b>Gain factor</b>: Multiplies the saved difference images to make faint
fringes more visible. Same concept as the monitor's amplification.</p>
"""

_LIVE_HELP_HTML = """
<h3>About the Saved Image Preview</h3>
<p>When enabled, the Sweep page shows the most recently saved result image
underneath the progress bar, updated as each frequency finishes.</p>

<p>This is the same file that gets written to your output folder: the
averaged difference image for that frequency, contrast-stretched here so
faint fringes are actually visible on screen (the saved file itself keeps
its original values, so this preview never changes what gets written to
disk).</p>

<p>This helps you catch a bad measurement (camera out of focus, plate not
vibrating, wrong exposure) while the sweep is still running, instead of
only finding out once it finishes.</p>
"""
