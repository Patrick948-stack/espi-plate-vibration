"""
monitor_gui.py
Author: Patrick Mulikuza

A PyQt6 wizard version of monitor.py's three step terminal wizard: pick a
camera, set its exposure, gain, and gain_factor, pick an optional intensity
graph, then confirm and launch the same live "Live Feed" and
"Frame Subtraction" windows monitor.py opens.

This file owns zero business logic of its own. Every rule about what a
valid exposure is, what a camera choice means, or how to dispatch to the
right capture_and_display module already lives in monitor.py and is fully
tested by tests/test_monitor.py. This file only turns those same rules into
widgets, so a bug fixed once in monitor.py is fixed everywhere.

HOW TO RUN
----------
    python3 monitor_gui.py

DEPENDENCIES
------------
    pip install PyQt6
Plus whichever camera SDK you plan to use, see monitor.py for details.
"""

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QLabel,
    QMessageBox,
    QRadioButton,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

import monitor


# ==============================================================================
# PAGE 1 — CAMERA CHOICE
# ==============================================================================

class CameraPage(QWizardPage):
    """
    Mirrors monitor.choose_camera() and monitor.choose_camera_index().

    A QButtonGroup guarantees exactly one radio button is checked at all
    times (including right after the page is built), so there is no
    "nothing selected" state to guard against, unlike the terminal version
    which has to loop until it gets a valid string.
    """

    def __init__(self):
        super().__init__()
        self.setTitle("Step 1 of 3 — Choose your camera")
        self.setSubTitle("Which camera do you want to monitor?")

        layout = QVBoxLayout()

        self._group = QButtonGroup(self)
        self._radios = {}
        for choice, name in monitor.CAMERA_NAMES.items():
            radio = QRadioButton(name)
            self._group.addButton(radio)
            self._radios[choice] = radio
            layout.addWidget(radio)
        self._radios["2"].setChecked(True)  # same default as choose_camera()

        self._index_label = QLabel("Camera index (0 = first device found):")
        self._index_spin = QSpinBox()
        self._index_spin.setRange(0, 10)
        self._index_spin.setValue(0)
        layout.addWidget(self._index_label)
        layout.addWidget(self._index_spin)

        for radio in self._radios.values():
            radio.toggled.connect(self._update_index_visibility)
        self._update_index_visibility()

        self.setLayout(layout)

    def _update_index_visibility(self):
        # Basler always uses index 0 (see monitor.choose_camera_index), so
        # the spin box would be misleading to show for that choice.
        is_basler = self._radios["1"].isChecked()
        self._index_label.setVisible(not is_basler)
        self._index_spin.setVisible(not is_basler)

    def camera_choice(self):
        for choice, radio in self._radios.items():
            if radio.isChecked():
                return choice
        return None

    def camera_index(self):
        if self.camera_choice() == "1":
            return 0
        return self._index_spin.value()


# ==============================================================================
# PAGE 2 — CAMERA SETTINGS
# ==============================================================================

class SettingsPage(QWizardPage):
    """
    Mirrors monitor.choose_camera_settings() and monitor.choose_graph_type().

    The terminal version validates exposure_s and gain_factor after the
    fact, by looping ask_positive_float() until the user types something
    greater than 0. Here a QDoubleSpinBox's minimum makes the same invalid
    values impossible to enter in the first place, there is no "reject and
    retry" step to write because there is no invalid state to reject.
    """

    def __init__(self):
        super().__init__()
        self.setTitle("Step 2 of 3 — Camera settings")
        self.setSubTitle(
            "Exposure is in seconds. gain_factor only affects the on screen "
            "subtraction display, not the raw camera data."
        )

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Exposure (s):"))
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setDecimals(4)
        self.exposure_spin.setRange(0.0001, 10.0)
        self.exposure_spin.setSingleStep(0.01)
        self.exposure_spin.setValue(0.06)
        layout.addWidget(self.exposure_spin)

        layout.addWidget(QLabel("Gain (dB):"))
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setDecimals(2)
        self.gain_spin.setRange(-20.0, 50.0)  # 0 dB and negative values are valid
        self.gain_spin.setValue(1.0)
        layout.addWidget(self.gain_spin)

        layout.addWidget(QLabel("gain_factor (subtraction display amplifier):"))
        self.gain_factor_spin = QDoubleSpinBox()
        self.gain_factor_spin.setDecimals(2)
        self.gain_factor_spin.setRange(0.01, 200.0)
        self.gain_factor_spin.setValue(20.0)
        layout.addWidget(self.gain_factor_spin)

        layout.addWidget(QLabel("Intensity graph:"))
        self._graph_group = QButtonGroup(self)
        self._graph_radios = {}
        graph_labels = {
            "1": "Histogram (updates every frame)",
            "2": "log_histogram (LabVIEW style, updates every frame)",
            "3": "3D surface (updates a few times per second)",
            "4": "None (fastest, default)",
        }
        for choice in monitor.GRAPH_TYPES:
            radio = QRadioButton(graph_labels[choice])
            self._graph_group.addButton(radio)
            self._graph_radios[choice] = radio
            layout.addWidget(radio)
        self._graph_radios["4"].setChecked(True)  # same default as choose_graph_type()

        self.setLayout(layout)

    def settings(self):
        """Returns the same shape dict monitor.choose_camera_settings() does."""
        graph_choice = next(
            choice for choice, radio in self._graph_radios.items() if radio.isChecked()
        )
        graph_name = monitor.GRAPH_TYPES[graph_choice]
        graph_type = None if graph_name == "none" else graph_name

        return dict(
            exposure_s=self.exposure_spin.value(),
            gain_db=self.gain_spin.value(),
            gain_factor=self.gain_factor_spin.value(),
            graph_type=graph_type,
        )


# ==============================================================================
# PAGE 3 — CONFIRM AND LAUNCH
# ==============================================================================

class ConfirmPage(QWizardPage):
    """Mirrors monitor.confirm_settings()'s summary screen."""

    def __init__(self, camera_page, settings_page):
        super().__init__()
        self.setTitle("Step 3 of 3 — Confirm and launch")
        self.setSubTitle("Review your choices, then click Launch Monitor.")

        self._camera_page = camera_page
        self._settings_page = settings_page

        layout = QVBoxLayout()
        self._summary_label = QLabel()
        layout.addWidget(self._summary_label)
        self.setLayout(layout)

    def initializePage(self):
        # Rebuilt every time this page is shown, so clicking Back and
        # changing a setting is reflected without a stale summary.
        camera_choice = self._camera_page.camera_choice()
        camera_index = self._camera_page.camera_index()
        settings = self._settings_page.settings()

        camera_line = monitor.CAMERA_NAMES[camera_choice]
        if camera_choice != "1":
            camera_line += f"  (index {camera_index})"

        self._summary_label.setText(
            f"Camera        :  {camera_line}\n"
            f"Exposure      :  {settings['exposure_s']} s\n"
            f"Gain          :  {settings['gain_db']} dB\n"
            f"gain_factor   :  {settings['gain_factor']}\n"
            f"Graph         :  {settings['graph_type']}"
        )


# ==============================================================================
# THE WIZARD
# ==============================================================================

class MonitorWizard(QWizard):
    """
    Ties the three pages together and, on Finish, hands off to the exact
    same monitor.launch_monitor() the terminal wizard uses.

    launch_monitor() opens OpenCV windows and blocks in a frame grabbing
    loop until 'q' is pressed. That loop is run on the main thread on
    purpose: OpenCV's HighGUI windows are not thread safe on every
    platform (macOS in particular requires GUI work to happen on the main
    thread), so instead of racing it against the Qt event loop in a
    background QThread, this closes the wizard first and only then calls
    launch_monitor(), the same way a terminal script hands the screen over
    to one program at a time.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESPI Camera Monitor")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Launch Monitor")

        self.camera_page = CameraPage()
        self.settings_page = SettingsPage()
        self.confirm_page = ConfirmPage(self.camera_page, self.settings_page)

        self.addPage(self.camera_page)
        self.addPage(self.settings_page)
        self.addPage(self.confirm_page)

    def accept(self):
        camera_choice = self.camera_page.camera_choice()
        camera_index = self.camera_page.camera_index()
        settings = self.settings_page.settings()

        super().accept()  # closes the wizard window before opening cv2 windows
        QApplication.processEvents()

        try:
            success = monitor.launch_monitor(camera_choice, camera_index, settings)
        except Exception as e:
            # launch_monitor() already catches the errors it expects (missing
            # SDK, a bad exposure value, a camera dropping out mid-stream).
            # This is a second, wider net for anything unexpected slipping
            # past that, so a surprise failure shows a dialog instead of
            # crashing the whole application with a raw traceback.
            QMessageBox.critical(
                None,
                "Monitor error",
                f"The monitor stopped unexpectedly: {e}",
            )
            return

        if success:
            QMessageBox.information(
                None, "Monitor finished", "Live monitor closed normally."
            )
        else:
            QMessageBox.warning(
                None,
                "Monitor error",
                "The monitor could not start. Check the terminal for details.",
            )


def main():
    app = QApplication(sys.argv)
    wizard = MonitorWizard()
    wizard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
