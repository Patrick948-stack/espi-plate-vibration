"""
monitor_gui.py
Author: Patrick Mulikuza

A PyQt6 dashboard version of monitor.py: one QMainWindow with a left-hand
navigation rail ("Setup", "Live Monitor") instead of monitor.py's three
typed terminal questions, and every live view embedded directly in the
window instead of the terminal version's separate OpenCV/matplotlib
windows.

WHAT THIS FILE OWNS, AND WHAT IT DOESN'T
-----------------------------------------
Every rule about what a valid exposure is, what a camera choice means, or
what CAMERA_NAMES / GRAPH_TYPES map to already lives in monitor.py (fully
tested by tests/test_monitor.py) and in camera_control*.py / live_graphs.py
(fully tested by their own test files). This file only turns those same
rules into widgets and wires the live camera + frame-subtraction + graph
loop together with Qt signals — it introduces no new business logic.

WHY THIS DOES NOT CALL monitor.launch_monitor()
-------------------------------------------------
launch_monitor() dispatches to capture_and_display*.py's main(), which is a
single, monolithic, blocking function: it opens the camera, loops grabbing
frames, calls cv2.imshow() directly inline, and closes the camera, all in
one function with no seam to redirect its display calls into Qt widgets
instead of separate OS windows. Embedding the live view here instead means
composing the same lower-level, already-tested building blocks
capture_and_display*.py itself is built from — camera_control*.py's
connect_camera(), grab_single_frame(), substract_frames(),
disconnect_camera() — inside a QThread that emits each frame through a
signal instead of showing it in a cv2 window.

HOW TO RUN
----------
    python3 monitor_gui.py

DEPENDENCIES
------------
    pip install PyQt6 matplotlib
Plus whichever camera SDK you plan to use, see monitor.py for details.
"""

import importlib
import math
import sys
import time

import cv2
import numpy as np
import qtawesome as qta
from PIL import Image

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import live_graphs
import monitor
import settings_manager
import theme


# ==============================================================================
# CAMERA MODULE LOOKUP — camera_control*.py, not capture_and_display*.py
# ==============================================================================
# monitor.py's own _CAPTURE_MODULES dict points at capture_and_display*.py,
# whose main() functions are monolithic and can't be embedded (see the
# module docstring above). This dashboard instead talks directly to the
# lower-level camera_control*.py modules — the same three files
# run_experiment.py already dispatches to as CAMERA_LIBRARY.

_CAMERA_CONTROL_MODULES = {
    "1": "camera_control",
    "2": "camera_control_inclusive",
    "3": "camera_control_allied_vision",
}


# ==============================================================================
# FRAME GRAB RETRY BUDGET
# ==============================================================================
# Real hardware measurement: a diagnostic that mirrored MonitorWorker's exact
# startup sequence (connect_camera(), THEN set_exposure_manual(), THEN
# set_gain_manual(), THEN start reading) showed a real USB webcam's first
# successful read() only arriving after about 3.4 seconds. The old retry
# budget (3 attempts, 0.3s apart) totaled 0.6 seconds and gave up long before
# that. The same diagnostic also showed the camera dropping frames again,
# briefly, well after that initial warm-up succeeded -- so this budget is
# given to every frame grab, not just the first one after connecting.
#
# DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S is a reasoned default (roughly 1.75x
# the measured 3.4s stall, for margin), not a guess: it is also exposed as
# a settings key (frame_grab_max_total_wait_s) so it can be tuned without a
# code change if real hardware needs a different number. If a mid-session
# drop ever turns out to last longer than this, that is real data worth
# collecting (see camera_diagnostic2.py) rather than another blind guess.
DEFAULT_FRAME_GRAB_RETRY_DELAY_S = 0.3
DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S = 6.0


# ==============================================================================
# GRAYSCALE CONVERSION ALGORITHMS — SINGLE-CHANNEL EXTRACTION
# ==============================================================================

def _grayscale_pillow(bgr_frame: np.ndarray, color_code: str) -> np.ndarray:
    """
    Extract single color channel using Pillow and merge across all channels.
    Returns a grayscale array with all channels equal to the selected color intensity.
    """
    # Convert BGR to RGB for Pillow
    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb_frame, mode='RGB')

    # Extract the target channel and get as numpy array
    channel = np.array(pil_img.getchannel(color_code))

    # Return the single-channel grayscale (2D array)
    return channel


def _grayscale_numpy(bgr_frame: np.ndarray, color_code: str) -> np.ndarray:
    """
    Extract single color channel using NumPy slicing (BGR layout).
    Color map: B=0, G=1, R=2 (OpenCV BGR convention).
    Returns a 2D grayscale numpy array.
    """
    channel_map = {"B": 0, "G": 1, "R": 2}
    channel_idx = channel_map[color_code]
    return bgr_frame[:, :, channel_idx].copy()


def _grayscale_opencv_hsv(bgr_frame: np.ndarray, color_code: str) -> np.ndarray:
    """
    Extract single color channel using HSV-based hue masking.
    Converts BGR to HSV, creates a mask for the target color's hue range,
    and returns the brightness (Value channel) of only those pixels.

    This approach isolates pixels of a specific hue and returns their true
    brightness, which is cleaner than raw channel extraction for
    monochromatic light sources (e.g. a red laser).

    Hue ranges (OpenCV HSV: H 0-180):
    - Red: 0-10 and 170-180 (wraps around)
    - Green: 35-85
    - Blue: 100-140

    Time: O(width * height), Space: O(width * height) for the output.
    """
    hsv_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)

    if color_code == "R":
        # Red wraps around in hue space
        mask1 = cv2.inRange(hsv_frame, np.array([0, 50, 50]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv_frame, np.array([170, 50, 50]), np.array([180, 255, 255]))
        color_mask = cv2.bitwise_or(mask1, mask2)
    elif color_code == "G":
        # Green hue range
        color_mask = cv2.inRange(hsv_frame, np.array([35, 50, 50]), np.array([85, 255, 255]))
    elif color_code == "B":
        # Blue hue range
        color_mask = cv2.inRange(hsv_frame, np.array([100, 50, 50]), np.array([140, 255, 255]))
    else:
        raise ValueError(f"Invalid color code: {color_code}")

    # Extract the V (Value/Brightness) channel from HSV
    v_channel = hsv_frame[:, :, 2]

    # Apply mask to get brightness of only target color pixels
    return cv2.bitwise_and(v_channel, v_channel, mask=color_mask)


def _apply_grayscale_conversion(
    frame: np.ndarray,
    method: str = "standard",
    color: str = "R",
    backend: str = "numpy",
) -> np.ndarray:
    """
    Apply grayscale conversion to a frame based on the selected method.

    Parameters:
        frame: numpy array — either BGR (H, W, 3) or grayscale (H, W), uint8
        method: "standard" (full RGB) or "single_channel"
        color: "R", "G", or "B" (used only when method="single_channel")
        backend: "numpy", "pillow", or "opencv_split" (used only when method="single_channel")

    Returns:
        2D grayscale numpy array (H, W) uint8
    """
    # If frame is already grayscale: either 2D (H, W) or 3D single-channel (H, W, 1)
    if len(frame.shape) == 2:
        return frame
    if len(frame.shape) == 3 and frame.shape[2] == 1:
        return frame.reshape(frame.shape[:2])

    # Frame is 3D (BGR), apply conversion
    if method == "standard":
        # Standard full-RGB grayscale conversion
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif method == "single_channel":
        if backend == "numpy":
            return _grayscale_numpy(frame, color)
        elif backend == "pillow":
            return _grayscale_pillow(frame, color)
        elif backend == "opencv_hsv":
            return _grayscale_opencv_hsv(frame, color)
        else:
            raise ValueError(f"Invalid backend: {backend}")
    else:
        raise ValueError(f"Invalid method: {method}")


_GRAYSCALE_COMPARISON_METHODS = ("standard", "numpy", "pillow", "opencv_hsv")


def _compare_grayscale_methods(frame: np.ndarray, color: str = "R") -> dict:
    """
    Run Standard Full-RGB and all three single-channel extraction backends
    on the same raw frame, so their effect can be compared side by side
    instead of switching settings and restarting the monitor to see each
    one. Backs the Compare Grayscale Methods button.

    Returns a dict: method name -> (result_array, elapsed_seconds, mean_brightness).
    mean_brightness is the result's average pixel value, a quick way to see
    which method actually reads brighter on screen.

    Time: O(k * width * height) for k = len(_GRAYSCALE_COMPARISON_METHODS),
    Space: O(k * width * height) for the k result arrays.
    """
    results = {}
    for method in _GRAYSCALE_COMPARISON_METHODS:
        start = time.perf_counter()
        if method == "standard":
            result = _apply_grayscale_conversion(frame, method="standard")
        else:
            result = _apply_grayscale_conversion(
                frame, method="single_channel", color=color, backend=method
            )
        elapsed = time.perf_counter() - start
        results[method] = (result, elapsed, float(np.mean(result)))
    return results


def _compare_grayscale_difference_methods(
    frame1: np.ndarray,
    frame2: np.ndarray,
    color: str = "R",
    cam_lib=None,
    amplification_method: str = "none",
    gain_factor: float = 1.0,
) -> dict:
    """
    Take two raw frames, apply each grayscale conversion method to both,
    compute the absolute difference between them, apply amplification,
    and compare the results side by side. Shows how the choice of grayscale
    method affects the quality of the difference visualization.

    Returns a dict: method name -> (difference_array, elapsed_seconds, mean_intensity).
    mean_intensity is the average pixel value of the difference (higher = more change detected).

    Time: O(k * width * height) for k = len(_GRAYSCALE_COMPARISON_METHODS),
    Space: O(k * width * height) for the k difference arrays.
    """
    results = {}
    for method in _GRAYSCALE_COMPARISON_METHODS:
        start = time.perf_counter()
        # Convert both frames using the same method
        if method == "standard":
            gray1 = _apply_grayscale_conversion(frame1, method="standard")
            gray2 = _apply_grayscale_conversion(frame2, method="standard")
        else:
            gray1 = _apply_grayscale_conversion(
                frame1, method="single_channel", color=color, backend=method
            )
            gray2 = _apply_grayscale_conversion(
                frame2, method="single_channel", color=color, backend=method
            )
        # Compute absolute difference between the grayscale frames
        diff = cv2.absdiff(gray1, gray2)
        # Apply amplification to make difference visible
        if cam_lib and amplification_method != "none":
            diff = _apply_diff_amplification(diff, amplification_method, gain_factor)
        elapsed = time.perf_counter() - start
        results[method] = (diff, elapsed, float(np.mean(diff)))
    return results


# ==============================================================================
# DIFFERENCE AMPLIFICATION ALGORITHMS
# ==============================================================================
# Every function below is only ever called on the post-averaging diff array
# (raw_diff / raw_change in MonitorWorker), never on the live feed frame. See
# _apply_diff_amplification's docstring for why that split matters.

_AMPLIFICATION_METHODS = ("none", "gain_factor")


def _apply_diff_amplification(
    raw_diff: np.ndarray,
    method: str,
    gain_factor: float,
) -> np.ndarray:
    """
    Apply the selected amplification to a raw difference frame.

    Callers must only ever pass the post-averaging diff array here (see
    MonitorWorker._run_frame_averaging / _run_averaged_differences), never
    the raw or averaged live feed frame, since amplification is meant to make
    the subtracted fringe pattern visible, not to alter what the live feed
    shows the operator.
    """
    if method == "gain_factor":
        return cv2.convertScaleAbs(raw_diff, alpha=gain_factor)
    else:  # "none"
        return raw_diff


def _compare_amplification_methods(
    raw_diff: np.ndarray,
    gain_factor: float,
) -> dict:
    """
    Run every amplification method on the same raw diff frame, so their
    effect can be compared side by side instead of one at a time by
    restarting the monitor with a different setting.

    Returns a dict: method name -> (result_array, elapsed_seconds, contrast_std).
    contrast_std (the result's standard deviation) is a quick proxy for how
    much a method spread out the pixel values; it is not a substitute for
    looking at the images, just a number to sort by.

    Time: O(k * width * height) for k = len(_AMPLIFICATION_METHODS),
    Space: O(k * width * height) for the k result arrays.
    """
    results = {}
    for method in _AMPLIFICATION_METHODS:
        start = time.perf_counter()
        result = _apply_diff_amplification(raw_diff, method, gain_factor)
        elapsed = time.perf_counter() - start
        results[method] = (result, elapsed, float(np.std(result)))
    return results


# ==============================================================================
# FRAME -> QPIXMAP CONVERSION
# ==============================================================================

def _frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    """
    Convert a 2D uint8 greyscale numpy array (the same shape
    grab_single_frame() and substract_frames() already return) into a
    QPixmap a QLabel can display.

    QImage.copy() is required here: QImage() only wraps frame's existing
    memory buffer, it does not copy it. Without copying, the pixmap would
    still be pointing at that buffer after frame goes out of scope, and the
    next grabbed frame (which may reuse the same underlying camera buffer)
    could silently corrupt an image already on screen.
    """
    frame = np.ascontiguousarray(frame)
    height, width = frame.shape
    image = QImage(frame.data, width, height, width, QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(image.copy())


# ==============================================================================
# SETUP PAGE
# ==============================================================================

class SetupPage(QWidget):
    """
    Combines monitor.py's three terminal steps (camera + index, settings,
    graph choice) into three QGroupBox sections on one page, plus an
    always-updating summary — no separate confirm step, since starting or
    stopping the monitor is cheap and reversible, unlike a multi-minute
    frequency sweep.
    """

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # Defaults come from the same settings file run_experiment_gui.py's
        # SetupPage reads (~/.espi/settings.json via settings_manager). This
        # is also where espi_app writes its own hardware defaults, when the
        # user has "Use Last Settings as Default" checked, so opening
        # Monitor Mode from espi_app starts from the same values.
        settings = settings_manager.load_settings()

        # ---- Camera group (mirrors monitor.choose_camera() / choose_camera_index()) ----
        camera_group = QGroupBox("Camera")
        camera_layout = QVBoxLayout()

        self._camera_group = QButtonGroup(self)
        self._radios = {}
        for choice, name in monitor.CAMERA_NAMES.items():
            radio = QRadioButton(name)
            self._camera_group.addButton(radio)
            self._radios[choice] = radio
            camera_layout.addWidget(radio)
        default_camera = settings.get("default_camera_choice", "2")
        self._radios[default_camera].setChecked(True)

        self._index_label = QLabel("Camera index (0 = first device found):")
        self._index_spin = QSpinBox()
        self._index_spin.setRange(0, 10)
        self._index_spin.setValue(0)
        camera_layout.addWidget(self._index_label)
        camera_layout.addWidget(self._index_spin)

        for radio in self._radios.values():
            radio.toggled.connect(self._update_index_visibility)
        self._update_index_visibility()

        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)

        # ---- Settings group (mirrors monitor.choose_camera_settings()) ----
        settings_group = QGroupBox("Capture Settings")
        settings_layout = QVBoxLayout()

        settings_layout.addWidget(QLabel("Exposure (s):"))
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setDecimals(4)
        self.exposure_spin.setRange(0.0001, 10.0)
        self.exposure_spin.setSingleStep(0.01)
        self.exposure_spin.setValue(settings.get("monitor_default_exposure", 0.06))
        settings_layout.addWidget(self.exposure_spin)

        # Gain (dB) is an advanced control most users leave alone; hidden by
        # default until "Show Gain (dB) control" is checked on the Settings
        # page (mirrors run_experiment_gui.py's own checkbox of the same
        # name, sharing the same show_gain settings key so the choice is
        # remembered, and shared, across both dashboards).
        self._gain_label = QLabel("Gain (dB):")
        settings_layout.addWidget(self._gain_label)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setDecimals(2)
        self.gain_spin.setRange(-20.0, 50.0)  # 0 dB and negative values are valid
        self.gain_spin.setValue(settings.get("monitor_default_gain", 1.0))
        settings_layout.addWidget(self.gain_spin)
        self.set_gain_visible(settings.get("show_gain", False))

        settings_layout.addWidget(QLabel("gain_factor (subtraction display amplifier):"))
        self.gain_factor_spin = QDoubleSpinBox()
        self.gain_factor_spin.setDecimals(2)
        self.gain_factor_spin.setRange(0.01, 200.0)
        self.gain_factor_spin.setValue(settings.get("monitor_default_gain_factor", 10.0))
        settings_layout.addWidget(self.gain_factor_spin)

        settings_layout.addWidget(QLabel("Frames to average:"))
        self.n_averages_spin = QSpinBox()
        self.n_averages_spin.setRange(1, 50)
        self.n_averages_spin.setValue(1)  # default: no averaging
        settings_layout.addWidget(self.n_averages_spin)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # ---- Live summary + start button ----
        self._summary_label = QLabel()
        self._summary_label.setObjectName("SummaryLabel")
        layout.addWidget(self._summary_label)

        self.start_button = QPushButton("Start Monitor")
        self.start_button.setObjectName("PrimaryButton")
        layout.addWidget(self.start_button)
        layout.addStretch()

        # Wrap in a scroll area so the page is scrollable when it gets tall
        scroll_widget = QWidget()
        scroll_widget.setLayout(layout)
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

        # Wire every input that can change the summary to _update_summary().
        # Connected after all the widgets above exist and after each
        # group's own default has already been set, so this never fires
        # against not-yet-created widgets.
        for radio in self._radios.values():
            radio.toggled.connect(self._update_summary)
        self._index_spin.valueChanged.connect(self._update_summary)
        self.exposure_spin.valueChanged.connect(self._update_summary)
        self.gain_spin.valueChanged.connect(self._update_summary)
        self.gain_factor_spin.valueChanged.connect(self._update_summary)
        self.n_averages_spin.valueChanged.connect(self._update_summary)

        self._update_summary()

        # "Use Last Settings as Default" (set from espi_app's Settings
        # dialog, bridged into this same settings file) means camera,
        # index, exposure, gain, and gain_factor are now auto-managed from
        # whatever was actually last used to start a session — not typed
        # in by hand — so those fields are locked. n_averages is not a
        # tracked default and always stays editable.
        if settings.get("use_last_settings_as_default", False):
            for radio in self._radios.values():
                radio.setEnabled(False)
            self._index_spin.setEnabled(False)
            self.exposure_spin.setEnabled(False)
            self.gain_spin.setEnabled(False)
            self.gain_factor_spin.setEnabled(False)

    def _update_index_visibility(self):
        # Basler always uses index 0 (see monitor.choose_camera_index), so
        # the spin box would be misleading to show for that choice.
        is_basler = self._radios["1"].isChecked()
        self._index_label.setVisible(not is_basler)
        self._index_spin.setVisible(not is_basler)

    def set_gain_visible(self, visible: bool):
        """
        Show or hide the Gain (dB) control. Called once at construction with
        whatever show_gain was saved, and again live by SettingsPage's own
        "Show Gain (dB) control" checkbox whenever it is toggled.
        """
        self._gain_label.setVisible(visible)
        self.gain_spin.setVisible(visible)

    def camera_choice(self):
        for choice, radio in self._radios.items():
            if radio.isChecked():
                return choice
        return None

    def camera_index(self):
        if self.camera_choice() == "1":
            return 0
        return self._index_spin.value()

    def settings(self):
        """Returns capture hardware settings (exposure, gain, averaging)."""
        return dict(
            exposure_s=self.exposure_spin.value(),
            gain_db=self.gain_spin.value(),
            gain_factor=self.gain_factor_spin.value(),
            n_averages=self.n_averages_spin.value(),
        )

    def _update_summary(self):
        camera_choice = self.camera_choice()
        camera_index = self.camera_index()
        settings = self.settings()

        camera_line = monitor.CAMERA_NAMES[camera_choice]
        if camera_choice != "1":
            camera_line += f"  (index {camera_index})"

        self._summary_label.setText(
            f"Camera        :  {camera_line}\n"
            f"Exposure      :  {settings['exposure_s']} s\n"
            f"Gain          :  {settings['gain_db']} dB\n"
            f"gain_factor   :  {settings['gain_factor']}\n"
            f"n_averages    :  {settings['n_averages']}"
        )


# ==============================================================================
# LIVE MONITOR WORKER
# ==============================================================================

class MonitorWorker(QThread):
    """
    Runs the live camera + frame-subtraction loop on a background thread,
    composing the same camera_control*.py building blocks
    capture_and_display*.py itself uses, but emitting each frame through a
    signal instead of calling cv2.imshow().

    Stopping is cooperative: stop() just sets a flag, which this loop checks
    once per iteration — the same role monitor.py's cv2.waitKey('q') plays
    in the terminal version. That makes Stop safe here in a way the
    multi-minute frequency sweep in run_experiment_gui.py's SweepWorker is
    not: this loop never does anything that can't be interrupted between
    one frame and the next.
    """

    frame_ready = pyqtSignal(np.ndarray, object)  # (raw frame, diff-or-None)
    raw_diff_ready = pyqtSignal(np.ndarray)  # pre-amplification diff, for the Compare dialog
    raw_frame_ready = pyqtSignal(np.ndarray)  # pre-grayscale-conversion frame, for the Compare Grayscale dialog
    error = pyqtSignal(str)
    finished_cleanly = pyqtSignal()

    def __init__(self, camera_choice, camera_index, settings):
        super().__init__()
        self._camera_choice = camera_choice
        self._camera_index = camera_index
        self._settings = settings
        self._diff_amplification = settings.get("diff_amplification", "gain_factor")
        self._n_averages = settings.get("n_averages", 1)
        self._averaging_method = settings.get("averaging_method", "averaged_differences")
        self._grayscale_method = settings.get("grayscale_method", "standard")
        self._grayscale_color = settings.get("grayscale_color", "R")
        self._grayscale_backend = settings.get("grayscale_backend", "numpy")
        self._frame_grab_retry_delay_s = settings.get(
            "frame_grab_retry_delay_s", DEFAULT_FRAME_GRAB_RETRY_DELAY_S
        )
        self._frame_grab_max_total_wait_s = settings.get(
            "frame_grab_max_total_wait_s", DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S
        )
        self._stop = False


    def stop(self):
        self._stop = True

    def run(self):
        module_name = _CAMERA_CONTROL_MODULES[self._camera_choice]
        try:
            cam_lib = importlib.import_module(module_name)
        except ImportError as e:
            self.error.emit(f"Could not load {module_name}: {e}")
            self.finished_cleanly.emit()
            return

        camera = None
        format_info = {}
        try:
            if self._camera_choice == "1":
                camera, format_info = cam_lib.connect_camera(grayscale_method=self._grayscale_method)
            else:
                camera, format_info = cam_lib.connect_camera(self._camera_index, self._grayscale_method)

            if camera is None:
                self.error.emit(
                    "Could not open the camera. Check it is plugged in and try again."
                )
                return

            # Store format_info so _grab_frame() and _apply_grayscale_conversion() can use it
            self._format_info = format_info

            exposure_s = self._settings["exposure_s"]
            exposure_value = math.log2(exposure_s) if self._camera_choice == "2" \
                else exposure_s * 1_000_000
            cam_lib.set_exposure_manual(camera, exposure_value)
            cam_lib.set_gain_manual(camera, self._settings["gain_db"])

            gain_factor = self._settings["gain_factor"]
            n_averages = self._n_averages

            if self._averaging_method == "averaged_differences":
                self._run_averaged_differences(cam_lib, camera, gain_factor, n_averages)
            else:
                self._run_frame_averaging(cam_lib, camera, gain_factor, n_averages)

        except Exception as e:
            self.error.emit(f"The monitor stopped unexpectedly: {e}")
        finally:
            if camera is not None:
                cam_lib.disconnect_camera(camera)
            self.finished_cleanly.emit()

    def _grab_frame(self, cam_lib, camera):
        """
        Wraps grab_single_frame_color_with_retry() with defensive validation.

        Configured retry budget (see DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S
        above for the real hardware measurement this is based on), so
        every frame grab in either loop below gets the same, single place
        to tune retry behavior.

        Also validates frame format and applies corrections (e.g., RGB→BGR swap).
        """
        frame = cam_lib.grab_single_frame_color_with_retry(
            camera,
            retry_delay_s=self._frame_grab_retry_delay_s,
            max_total_wait_s=self._frame_grab_max_total_wait_s,
        )

        if frame is None:
            return None

        # Defensive check 1: Validate shape
        if len(frame.shape) == 2:
            # Grayscale (H, W) - OK for Mono8 cameras
            pass
        elif len(frame.shape) == 3:
            if frame.shape[2] != 3:
                print(f"❌ ERROR: Frame has {frame.shape[2]} channels, expected 1 or 3. Shape: {frame.shape}")
                return None
        else:
            print(f"❌ ERROR: Unexpected frame shape {frame.shape}. Expected (H, W) or (H, W, 3)")
            return None

        # Defensive check 2: Validate dtype
        if frame.dtype != np.uint8:
            print(f"❌ ERROR: Frame dtype is {frame.dtype}, expected uint8")
            return None

        # Defensive check 3: Apply channel swap if RGB→BGR mismatch detected
        format_info = getattr(self, '_format_info', {})
        if format_info.get("needs_channel_swap", False):
            if len(frame.shape) == 3:
                frame = frame[:, :, ::-1]  # Swap R and B channels

        return frame

    def _run_frame_averaging(self, cam_lib, camera, gain_factor, n_averages):
        """
        Frame averaging (classic method):
        1. Collect n_averages raw frames
        2. Average them together
        3. Subtract from previous average to get difference
        """
        frame_buffer = []
        prev_averaged = None

        while not self._stop:
            # grab_single_frame_color_with_retry(), not grab_single_frame():
            # the plain version already reduces a color frame to greyscale
            # before returning it, which would make single-channel R/G/B
            # extraction below a no-op no matter what color or backend was
            # picked. The _with_retry version also gives a flaky USB
            # webcam a couple of extra chances before this loop gives up,
            # instead of failing on the very first dropped frame.
            frame = self._grab_frame(cam_lib, camera)
            if frame is None:
                self.error.emit("Failed to grab frame — check camera connection.")
                break

            self.raw_frame_ready.emit(frame)

            # Apply grayscale conversion (standard or single-channel)
            frame = _apply_grayscale_conversion(
                frame, self._grayscale_method, self._grayscale_color, self._grayscale_backend
            )

            frame_buffer.append(frame)

            if len(frame_buffer) == n_averages:
                # Defensive check: ensure all frames in buffer have same shape
                first_shape = frame_buffer[0].shape
                for i, f in enumerate(frame_buffer[1:], 1):
                    if f.shape != first_shape:
                        print(f"❌ ERROR: Frame {i} has shape {f.shape}, expected {first_shape}")
                        self.error.emit("Frame shapes are inconsistent — aborting.")
                        break

                # Compute average with clipping to prevent data loss
                averaged_float = np.mean(frame_buffer, axis=0)
                averaged = np.clip(averaged_float, 0, 255).astype(np.uint8)
                frame_buffer = []

                diff = None
                if prev_averaged is not None:
                    raw_diff = cam_lib.substract_frames(prev_averaged, averaged)
                    self.raw_diff_ready.emit(raw_diff)
                    diff = _apply_diff_amplification(
                        raw_diff, self._diff_amplification, gain_factor,
                    )

                prev_averaged = averaged
                self.frame_ready.emit(averaged, diff)

    def _run_averaged_differences(self, cam_lib, camera, gain_factor, n_averages):
        """
        Average of differences (new method):
        1. Grab pairs of consecutive frames
        2. Subtract each pair to get a difference image
        3. Collect n_averages differences in a buffer
        4. Average all differences together
        This produces a more stable difference image by averaging noise out of the differences themselves.
        Live feed updates every frame pair; difference window updates every n_averages.
        """
        diff_buffer = []
        prev_averaged_diff = None
        current_diff = None

        while not self._stop:
            # grab_single_frame_color_with_retry(), see _run_frame_averaging() above for why.
            frame1 = self._grab_frame(cam_lib, camera)
            if frame1 is None:
                self.error.emit("Failed to grab frame — check camera connection.")
                break

            frame2 = self._grab_frame(cam_lib, camera)
            if frame2 is None:
                self.error.emit("Failed to grab frame — check camera connection.")
                break

            self.raw_frame_ready.emit(frame2)

            # Apply grayscale conversion (standard or single-channel)
            frame1 = _apply_grayscale_conversion(
                frame1, self._grayscale_method, self._grayscale_color, self._grayscale_backend
            )
            frame2 = _apply_grayscale_conversion(
                frame2, self._grayscale_method, self._grayscale_color, self._grayscale_backend
            )

            raw_diff = cam_lib.substract_frames(frame1, frame2)
            diff_buffer.append(raw_diff)

            # Emit every frame pair for live feed display
            self.frame_ready.emit(frame2, current_diff)

            if len(diff_buffer) == n_averages:
                # Defensive check: ensure all diffs in buffer have same shape
                first_shape = diff_buffer[0].shape
                for i, d in enumerate(diff_buffer[1:], 1):
                    if d.shape != first_shape:
                        print(f"❌ ERROR: Diff {i} has shape {d.shape}, expected {first_shape}")
                        self.error.emit("Difference shapes are inconsistent — aborting.")
                        break

                # Compute average with clipping to prevent data loss
                averaged_diff_float = np.mean(diff_buffer, axis=0)
                averaged_diff = np.clip(averaged_diff_float, 0, 255).astype(np.uint8)
                diff_buffer = []

                if prev_averaged_diff is not None:
                    raw_change = cam_lib.substract_frames(prev_averaged_diff, averaged_diff)
                    self.raw_diff_ready.emit(raw_change)
                    current_diff = _apply_diff_amplification(
                        raw_change, self._diff_amplification, gain_factor,
                    )

                prev_averaged_diff = averaged_diff


# ==============================================================================
# AMPLIFICATION COMPARISON DIALOG
# ==============================================================================

class AmplificationComparisonDialog(QDialog):
    """
    Shows every diff amplification method (none, gain_factor) applied to the
    same raw diff frame, side by side, so their effect can be compared
    visually without restarting the monitor with a different setting.
    """

    _LABELS = {
        "none": "No amplification",
        "gain_factor": "Gain factor",
    }

    def __init__(
        self,
        raw_diff,
        gain_factor,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Compare Amplification Methods")

        results = _compare_amplification_methods(raw_diff, gain_factor)

        grid = QGridLayout()
        for column, method in enumerate(_AMPLIFICATION_METHODS):
            result, elapsed, contrast = results[method]

            image_label = QLabel()
            image_label.setPixmap(
                _frame_to_pixmap(result).scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio
                )
            )

            caption = QLabel(
                f"{self._LABELS[method]}\n{elapsed * 1000:.2f} ms, contrast {contrast:.1f}"
            )
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

            column_layout = QVBoxLayout()
            column_layout.addWidget(image_label)
            column_layout.addWidget(caption)
            grid.addLayout(column_layout, 0, column)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        outer = QVBoxLayout()
        outer.addLayout(grid)
        outer.addWidget(close_button)
        self.setLayout(outer)


class GrayscaleComparisonDialog(QDialog):
    """
    Shows Standard Full-RGB and all three single-channel extraction
    backends (NumPy, Pillow, OpenCV HSV) applied to the same raw frame,
    side by side, using whichever color channel is currently selected in
    Settings. Answers "does switching to single-channel extraction actually
    make a visible difference" by letting the operator look at the results
    instead of guessing.
    """

    _LABELS = {
        "standard": "Standard Full-RGB",
        "numpy": "Single-Channel (NumPy)",
        "pillow": "Single-Channel (Pillow)",
        "opencv_hsv": "Single-Channel (OpenCV HSV)",
    }

    def __init__(self, frame, color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Grayscale Methods")

        results = _compare_grayscale_methods(frame, color)

        grid = QGridLayout()
        for column, method in enumerate(_GRAYSCALE_COMPARISON_METHODS):
            result, elapsed, brightness = results[method]

            image_label = QLabel()
            image_label.setPixmap(
                _frame_to_pixmap(result).scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio
                )
            )

            caption = QLabel(
                f"{self._LABELS[method]}\n{elapsed * 1000:.2f} ms, avg brightness {brightness:.1f}"
            )
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

            column_layout = QVBoxLayout()
            column_layout.addWidget(image_label)
            column_layout.addWidget(caption)
            grid.addLayout(column_layout, 0, column)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        outer = QVBoxLayout()
        outer.addLayout(grid)
        outer.addWidget(close_button)
        self.setLayout(outer)


class GrayscaleDifferenceComparisonDialog(QDialog):
    """
    Shows how each grayscale conversion method affects the difference between
    two consecutive frames. Takes two raw frames, applies each grayscale method
    to both, computes the difference, and displays all four results side by side.
    Answers "which grayscale method produces the clearest difference visualization"
    without restarting the monitor.
    """

    _LABELS = {
        "standard": "Standard Full-RGB",
        "numpy": "Single-Channel (NumPy)",
        "pillow": "Single-Channel (Pillow)",
        "opencv_hsv": "Single-Channel (OpenCV HSV)",
    }

    def __init__(self, frame1, frame2, color, cam_lib=None, amplification_method="none", gain_factor=1.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Grayscale Methods (Difference)")

        results = _compare_grayscale_difference_methods(
            frame1, frame2, color, cam_lib, amplification_method, gain_factor
        )

        grid = QGridLayout()
        for column, method in enumerate(_GRAYSCALE_COMPARISON_METHODS):
            result, elapsed, mean_intensity = results[method]

            image_label = QLabel()
            image_label.setPixmap(
                _frame_to_pixmap(result).scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio
                )
            )

            caption = QLabel(
                f"{self._LABELS[method]}\n{elapsed * 1000:.2f} ms, avg intensity {mean_intensity:.1f}"
            )
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

            column_layout = QVBoxLayout()
            column_layout.addWidget(image_label)
            column_layout.addWidget(caption)
            grid.addLayout(column_layout, 0, column)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        outer = QVBoxLayout()
        outer.addLayout(grid)
        outer.addWidget(close_button)
        self.setLayout(outer)


# ==============================================================================
# LIVE MONITOR PAGE
# ==============================================================================

class LiveMonitorPage(QWidget):
    """
    Two QLabels ("Live Feed", "Frame Subtraction") plus an optional embedded
    matplotlib graph, all fed by MonitorWorker's frame_ready signal.

    THREADING RULE: MonitorWorker only touches the camera and does numpy
    math off the main thread. Every Qt widget update below — the QLabel
    pixmaps and the live_graph.update() call (which redraws a
    FigureCanvasQTAgg) — happens here, in a slot connected to a signal,
    which Qt always runs on the main thread. Never call these directly
    from MonitorWorker.run().
    """

    stopped = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._worker = None
        self._live_graph = None
        self._settings = None
        self._last_raw_diff = None
        self._last_two_raw_frames = []  # Store last 2 raw frames for difference comparison

        layout = QVBoxLayout()

        feeds_layout = QHBoxLayout()
        self.live_feed_label = QLabel("Live Feed")
        self.live_feed_label.setObjectName("FeedFrame")
        self.live_feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_feed_label.setMinimumSize(320, 240)
        self.diff_label = QLabel("Frame Subtraction")
        self.diff_label.setObjectName("FeedFrame")
        self.diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diff_label.setMinimumSize(320, 240)
        feeds_layout.addWidget(self.live_feed_label)
        feeds_layout.addWidget(self.diff_label)
        layout.addLayout(feeds_layout)

        self._graph_card = QWidget()
        self._graph_card.setObjectName("CanvasCard")
        graph_card_layout = QVBoxLayout()
        graph_card_layout.setContentsMargins(12, 12, 12, 12)
        self._graph_canvas = FigureCanvasQTAgg(Figure(figsize=(6, 3)))
        graph_card_layout.addWidget(self._graph_canvas)
        self._graph_card.setLayout(graph_card_layout)
        self._graph_card.setVisible(False)
        layout.addWidget(self._graph_card)

        controls_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop Monitor")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_monitor)
        controls_layout.addWidget(self.stop_button)

        self.compare_button = QPushButton("Compare Amplification Methods")
        self.compare_button.setEnabled(False)
        self.compare_button.setToolTip(
            "Run every amplification method on the current diff frame, side by side."
        )
        self.compare_button.clicked.connect(self._open_comparison_dialog)
        controls_layout.addWidget(self.compare_button)

        self.compare_grayscale_button = QPushButton("Compare Grayscale Methods")
        self.compare_grayscale_button.setEnabled(False)
        self.compare_grayscale_button.setToolTip(
            "Show how each grayscale method affects the latest frame difference."
        )
        self.compare_grayscale_button.clicked.connect(self._open_grayscale_comparison_dialog)
        controls_layout.addWidget(self.compare_grayscale_button)

        layout.addLayout(controls_layout)

        self.setLayout(layout)

    def start_monitor(self, camera_choice, camera_index, settings):
        graph_type = settings["graph_type"]
        if graph_type is not None:
            self._graph_canvas.figure.clear()
            projection = "3d" if graph_type == "3d" else None
            ax = self._graph_canvas.figure.add_subplot(111, projection=projection)
            self._live_graph = live_graphs.create_live_graph(graph_type, ax=ax)
            self._graph_card.setVisible(True)
        else:
            self._live_graph = None
            self._graph_card.setVisible(False)

        self._settings = settings
        self._last_raw_diff = None
        self._last_two_raw_frames = []
        self.compare_button.setEnabled(False)
        self.compare_grayscale_button.setEnabled(False)

        self._worker = MonitorWorker(camera_choice, camera_index, settings)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.raw_diff_ready.connect(self._on_raw_diff)
        self._worker.raw_frame_ready.connect(self._on_raw_frame)
        self._worker.error.connect(self._on_error)
        self._worker.finished_cleanly.connect(self._on_finished)
        self._worker.start()
        self.stop_button.setEnabled(True)

    def is_running(self):
        return self._worker is not None and self._worker.isRunning()

    def stop_and_wait(self):
        """Used by MainWindow.closeEvent() to shut the worker down before exit."""
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait()
        self.compare_button.setEnabled(False)
        self.compare_grayscale_button.setEnabled(False)
        self._last_raw_diff = None
        self._last_two_raw_frames = []

    def _stop_monitor(self):
        if self._worker is not None:
            self._worker.stop()
        self.stop_button.setEnabled(False)
        self.compare_button.setEnabled(False)
        self.compare_grayscale_button.setEnabled(False)
        self._last_raw_diff = None
        self._last_two_raw_frames = []

    def _on_raw_diff(self, raw_diff):
        self._last_raw_diff = raw_diff
        self.compare_button.setEnabled(True)

    def _on_raw_frame(self, raw_frame):
        # Store the last 2 raw frames for difference comparison
        self._last_two_raw_frames.append(raw_frame)
        if len(self._last_two_raw_frames) > 2:
            self._last_two_raw_frames.pop(0)
        # Enable button once we have at least 2 frames to compare
        if len(self._last_two_raw_frames) >= 2:
            self.compare_grayscale_button.setEnabled(True)

    def _open_grayscale_comparison_dialog(self):
        if len(self._last_two_raw_frames) < 2 or self._worker is None:
            return

        frame1, frame2 = self._last_two_raw_frames[0], self._last_two_raw_frames[1]
        color = self._settings.get("grayscale_color", "R") if self._settings else "R"
        amplification_method = self._settings.get("diff_amplification", "gain_factor") if self._settings else "gain_factor"
        gain_factor = self._settings.get("gain_factor", 10.0) if self._settings else 10.0

        module_name = _CAMERA_CONTROL_MODULES[self._worker._camera_choice]
        cam_lib = importlib.import_module(module_name)

        dialog = GrayscaleDifferenceComparisonDialog(
            frame1, frame2, color, cam_lib, amplification_method, gain_factor, parent=self
        )
        dialog.exec()

    def _open_comparison_dialog(self):
        if self._last_raw_diff is None or self._worker is None:
            return

        dialog = AmplificationComparisonDialog(
            self._last_raw_diff,
            self._settings["gain_factor"],
            parent=self,
        )
        dialog.exec()

    def _on_frame(self, frame, diff):
        self.live_feed_label.setPixmap(
            _frame_to_pixmap(frame).scaled(
                self.live_feed_label.size(), Qt.AspectRatioMode.KeepAspectRatio
            )
        )
        if diff is not None:
            self.diff_label.setPixmap(
                _frame_to_pixmap(diff).scaled(
                    self.diff_label.size(), Qt.AspectRatioMode.KeepAspectRatio
                )
            )
        else:
            # On first frame, show blank diff (no difference yet)
            blank = np.zeros_like(frame, dtype=np.uint8)
            self.diff_label.setPixmap(
                _frame_to_pixmap(blank).scaled(
                    self.diff_label.size(), Qt.AspectRatioMode.KeepAspectRatio
                )
            )
        if self._live_graph is not None:
            self._live_graph.update(frame)

    def _on_error(self, message):
        QMessageBox.critical(self, "Monitor error", message)

    def _on_finished(self):
        self._worker = None
        self.stop_button.setEnabled(False)
        self.stopped.emit()


# ==============================================================================
# LEARN MORE HELP CONTENT
# ==============================================================================
# Plain language explanations of each processing method, written for whoever
# is operating the monitor rather than for someone reading the source code.
# Shown in a LearnMoreDialog when a Learn More button is clicked.

class LearnMoreDialog(QDialog):
    """
    A small popup that shows a plain language explanation of a group of
    settings. QTextBrowser (not QLabel) is used because the explanations are
    long enough to need scrolling, and because it can render simple HTML
    (headings, bold text, bullet lists) without needing a layout manager to
    arrange separate widgets for each paragraph.
    """

    def __init__(self, title, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 460)

        self.browser = QTextBrowser()
        self.browser.setObjectName("LearnMoreBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(html_content)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(self.browser)
        layout.addWidget(close_button)
        self.setLayout(layout)


_GRAYSCALE_HELP_HTML = """
<h3>About Grayscale Conversion</h3>
<p>Your camera captures red, green, and blue light in every pixel, but an
ESPI fringe pattern is about brightness changes, not color. Before two frames
can be compared, the color information has to be reduced down to one
brightness value per pixel. These options control how that reduction
happens.</p>

<p><b>Standard Full-RGB</b> blends all three color channels into one
brightness value using the same weighting the human eye uses (green
contributes more to perceived brightness than red or blue at the same
intensity). This is the safe, general purpose default and works well
regardless of what color your laser is.</p>

<p><b>Single-Channel Extraction</b> keeps only one color channel (Red, Green,
or Blue) and throws the other two away entirely, instead of blending them.
This is useful if your laser's color lines up strongly with one of the
camera's three channels: the other two channels mostly contain noise for a
single color light source, so dropping them can give a cleaner, higher
contrast signal than blending everything together.</p>

<p>When Single-Channel is selected, you also pick a processing algorithm:
<b>NumPy</b>, <b>Pillow</b>, or <b>OpenCV Split</b>. All three do the exact
same job, pulling out the one channel you picked, using three different
underlying code libraries. They will always give you the same picture.
NumPy is the fastest and is the recommended default; the other two exist so
the option can be checked against different libraries.</p>
"""

_AVERAGING_HELP_HTML = """
<h3>About Frame Averaging</h3>
<p>Every camera frame has some random pixel to pixel noise from the laser
light, usually called speckle noise. Comparing two noisy frames directly
makes that noise show up in the difference image right alongside the real
vibration pattern you are trying to see. Both strategies here exist to
reduce that noise before you have to look at it.</p>

<p><b>Difference of averages</b> collects several raw frames, averages them
together first, then compares that averaged frame to the previous averaged
frame. Averaging the raw frames cancels out a lot of the random noise before
any comparison happens.</p>

<p><b>Average of differences</b> does the two steps in the opposite order:
compare frame pairs first to get a difference image, collect several of
those difference images, then average the differences together. This tends
to produce a cleaner result for ESPI specifically, since it averages the
noise out of exactly the image you care about (the difference), rather than
averaging noise out of the inputs and hoping it stays gone after
subtraction.</p>

<p>There is no wrong choice here. Average of differences is the recommended
starting point, but trying both on your own setup is the only way to know
which looks cleaner for your particular camera and lighting.</p>
"""

_GRAPH_HELP_HTML = """
<h3>About the Intensity Graphs</h3>
<p>All of these graphs show the same underlying thing: for the current
frame, how many pixels have each possible brightness value, from 0 (fully
black) to 255 (fully white).</p>

<p><b>Histogram</b> is a simple bar chart of that count, redrawn every
frame. It is the most familiar view and a good default if you want a graph
at all.</p>

<p><b>Log histogram</b> shows the same counts, but the vertical axis uses a
logarithmic scale instead of a plain linear one, matching the look of the
original LabVIEW software. A linear scale squashes rare, very bright or very
dark pixels down to almost nothing next to the large cluster of mid range
pixels; the log scale keeps those rare values visible.</p>

<p><b>3D surface</b> plots brightness as a rolling landscape across the
whole frame instead of a single count, updated a few times a second rather
than every frame since it takes more work to redraw. It is useful for
spotting patterns across the whole image rather than just overall pixel
counts.</p>

<p><b>None</b> skips the graph entirely, which is the fastest option if you
do not need it running live.</p>
"""

_AMPLIFICATION_HELP_HTML = """
<h3>About Difference Amplification</h3>
<p>The raw difference between two frames is usually very dark, because most
pixels only changed by a tiny amount. Amplification reshapes those small
differences so the fringe pattern is actually visible on screen. It only
changes what you see in the Frame Subtraction display, never the Live Feed
or the raw camera data.</p>

<p><b>No amplification</b> shows the raw difference exactly as measured,
tiny changes and all. Useful as a baseline, but usually too dark to read at
a glance.</p>

<p><b>Gain factor</b> multiplies every pixel by a fixed number you choose in
the capture settings. Straightforward and predictable, but pick a number too
large and bright areas get clipped to solid white, losing detail there.</p>

<p>Not sure which to pick? The <b>Compare Amplification Methods</b> button
on the Live Monitor page runs both side by side on the same frame, so you
can look at the results instead of guessing.</p>
"""


# ==============================================================================
# SETTINGS PAGE
# ==============================================================================

class SettingsPage(QWidget):
    """
    Live monitor settings configuration page.
    Lets users choose frame-averaging strategy, grayscale conversion method, intensity graph type,
    and difference amplification.
    """
    def __init__(self, setup_page):
        super().__init__()
        self._setup_page = setup_page
        layout = QVBoxLayout()

        # Grayscale conversion method group
        grayscale_group = QGroupBox("Grayscale Conversion Method")
        grayscale_layout = QVBoxLayout()

        self._grayscale_learn_more_button = self._make_learn_more_button(
            "About Grayscale Conversion", _GRAYSCALE_HELP_HTML
        )
        grayscale_layout.addLayout(self._learn_more_row(self._grayscale_learn_more_button))

        self._grayscale_group = QButtonGroup(self)
        self._grayscale_radios = {}
        grayscale_tooltips = {
            "standard": "Standard full-RGB grayscale conversion (luminosity method).",
            "single_channel": "Extract a single color channel as grayscale.",
        }
        grayscale_labels = {
            "standard": "Standard Full-RGB",
            "single_channel": "Single-Channel Extraction",
        }
        for choice in grayscale_tooltips.keys():
            radio = QRadioButton(grayscale_labels[choice])
            radio.setToolTip(grayscale_tooltips[choice])
            self._grayscale_group.addButton(radio)
            self._grayscale_radios[choice] = radio
            grayscale_layout.addWidget(radio)

        # Color channel selection (only shown when single_channel is selected)
        self._color_label = QLabel("Target Color Channel:")
        self._color_combo = QComboBox()
        self._color_combo.addItems(["Red (R)", "Green (G)", "Blue (B)"])
        self._color_combo.setCurrentIndex(0)  # Default to Red

        color_layout = QHBoxLayout()
        color_layout.addWidget(self._color_label)
        color_layout.addWidget(self._color_combo)
        color_layout.addStretch()
        grayscale_layout.addLayout(color_layout)

        # Algorithm backend selection (only shown when single_channel is selected)
        self._backend_label = QLabel("Processing Algorithm:")
        self._backend_combo = QComboBox()
        backend_tooltips = {
            "numpy": "Fast NumPy slicing (recommended)",
            "pillow": "Pillow Image library extraction",
            "opencv_hsv": "OpenCV HSV hue masking (isolates specific light color)",
        }
        for backend, tooltip in backend_tooltips.items():
            self._backend_combo.addItem(backend.replace("_", " ").title(), backend)
        self._backend_combo.setCurrentIndex(0)  # Default to NumPy

        backend_layout = QHBoxLayout()
        backend_layout.addWidget(self._backend_label)
        backend_layout.addWidget(self._backend_combo)
        backend_layout.addStretch()
        grayscale_layout.addLayout(backend_layout)

        grayscale_layout.addStretch()
        grayscale_group.setLayout(grayscale_layout)
        layout.addWidget(grayscale_group)

        # Wire grayscale method radio button changes to update visibility
        # (Must be connected before setting initial state to ensure visibility is correct)
        for radio in self._grayscale_radios.values():
            radio.toggled.connect(self._update_grayscale_ui_visibility)

        # Set initial state: single_channel is default, then update visibility
        self._grayscale_radios["single_channel"].setChecked(True)
        self._update_grayscale_ui_visibility()

        # Averaging method group
        avg_group = QGroupBox("Frame Averaging Strategy")
        avg_layout = QVBoxLayout()

        self._averaging_learn_more_button = self._make_learn_more_button(
            "About Frame Averaging", _AVERAGING_HELP_HTML
        )
        avg_layout.addLayout(self._learn_more_row(self._averaging_learn_more_button))

        self._averaging_group = QButtonGroup(self)
        self._averaging_radios = {}
        averaging_tooltips = {
            "averaged_differences": "Subtracts frame pairs first, then averages the differences. Best for reducing speckle noise.",
            "frame_averaging": "Averages raw frames first, then subtracts. Classic approach.",
        }
        averaging_labels = {
            "averaged_differences": "Average of differences",
            "frame_averaging": "Difference of averages",
        }
        for choice in averaging_tooltips.keys():
            radio = QRadioButton(averaging_labels[choice])
            radio.setToolTip(averaging_tooltips[choice])
            self._averaging_group.addButton(radio)
            self._averaging_radios[choice] = radio
            avg_layout.addWidget(radio)

        self._averaging_radios["averaged_differences"].setChecked(True)
        avg_layout.addStretch()
        avg_group.setLayout(avg_layout)
        layout.addWidget(avg_group)

        # Intensity graph group
        graph_group = QGroupBox("Intensity Graph")
        graph_layout = QVBoxLayout()

        self._graph_learn_more_button = self._make_learn_more_button(
            "About the Intensity Graphs", _GRAPH_HELP_HTML
        )
        graph_layout.addLayout(self._learn_more_row(self._graph_learn_more_button))

        self._graph_group = QButtonGroup(self)
        self._graph_radios = {}
        graph_tooltips = {
            "1": "Shows pixel intensity distribution. Updates on every frame.",
            "2": "Log-scale histogram in LabVIEW style. Updates on every frame.",
            "3": "3D surface plot of pixel intensities. Updates a few times per second.",
            "4": "No graph (fastest option).",
        }
        graph_labels = {
            "1": "Histogram",
            "2": "Log histogram",
            "3": "3D surface",
            "4": "None",
        }
        for choice in monitor.GRAPH_TYPES:
            radio = QRadioButton(graph_labels[choice])
            radio.setToolTip(graph_tooltips[choice])
            self._graph_group.addButton(radio)
            self._graph_radios[choice] = radio
            graph_layout.addWidget(radio)

        self._graph_radios["4"].setChecked(True)
        graph_layout.addStretch()
        graph_group.setLayout(graph_layout)
        layout.addWidget(graph_group)

        # Difference amplification group
        amp_group = QGroupBox("Difference Amplification")
        amp_layout = QVBoxLayout()

        self._amplification_learn_more_button = self._make_learn_more_button(
            "About Difference Amplification", _AMPLIFICATION_HELP_HTML
        )
        amp_layout.addLayout(self._learn_more_row(self._amplification_learn_more_button))

        self._amp_group = QButtonGroup(self)
        self._amp_radios = {}
        amp_tooltips = {
            "none": "Display raw pixel differences without any amplification.",
            "gain_factor": "Multiply pixel values by the gain_factor from capture settings.",
        }
        amp_labels = {
            "none": "No amplification",
            "gain_factor": "Gain factor only",
        }
        for choice in amp_tooltips.keys():
            radio = QRadioButton(amp_labels[choice])
            radio.setToolTip(amp_tooltips[choice])
            self._amp_group.addButton(radio)
            self._amp_radios[choice] = radio
            amp_layout.addWidget(radio)

        amp_layout.addStretch()
        amp_group.setLayout(amp_layout)
        layout.addWidget(amp_group)

        self._amp_radios["gain_factor"].setChecked(True)

        # Advanced group: capture-hardware controls a typical user does not
        # need to see. Same idea as run_experiment_gui.py's own "Show Gain
        # (dB) control" checkbox, and the same shared show_gain settings
        # key, so the choice is remembered and shared across both dashboards.
        advanced_group = QGroupBox("Advanced")
        advanced_layout = QVBoxLayout()

        self._show_gain_checkbox = QCheckBox("Show Gain (dB) control")
        self._show_gain_checkbox.setChecked(settings_manager.load_settings().get("show_gain", False))
        self._show_gain_checkbox.toggled.connect(self._on_show_gain_toggled)
        advanced_layout.addWidget(self._show_gain_checkbox)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        layout.addStretch()

        # Wrap in a scroll area so the page is scrollable when it gets tall,
        # the same reasoning as SetupPage's own scroll area: without this, a
        # QStackedWidget must be big enough to show every page it holds, so
        # this page's own minimum height becomes the whole window's minimum
        # height, even while some other page is the one actually visible.
        scroll_widget = QWidget()
        scroll_widget.setLayout(layout)
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)

    def _make_learn_more_button(self, title, html_content):
        """
        Build a Learn More button that opens a LearnMoreDialog with the
        given title and content when clicked. LearnMoreDialog is looked up
        by module name inside the lambda (not imported into a local
        variable) so tests can substitute a fake dialog class without
        needing this method to change.
        """
        button = QPushButton("Learn More")
        button.setObjectName("LearnMoreButton")
        current_theme = settings_manager.load_settings().get("theme", "dark")
        button.setIcon(qta.icon(
            'mdi6.help-circle-outline',
            color=QColor(theme.icon_color_secondary(current_theme)),
        ))
        button.clicked.connect(
            lambda: LearnMoreDialog(title, html_content, self).exec()
        )
        return button

    def _learn_more_row(self, button):
        """Right-align a Learn More button in its own row above a group's options."""
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(button)
        return row

    def _update_grayscale_ui_visibility(self):
        """Show/hide color and backend options based on grayscale method selection."""
        is_single_channel = self._grayscale_radios["single_channel"].isChecked()
        self._color_label.setVisible(is_single_channel)
        self._color_combo.setVisible(is_single_channel)
        self._backend_label.setVisible(is_single_channel)
        self._backend_combo.setVisible(is_single_channel)

    def grayscale_method(self):
        """Get the currently selected grayscale method."""
        for choice, radio in self._grayscale_radios.items():
            if radio.isChecked():
                return choice
        return "single_channel"

    def grayscale_color(self):
        """Get the currently selected color channel (R, G, or B)."""
        text = self._color_combo.currentText()
        return text.split(" ")[0][0]  # Extract 'R', 'G', or 'B' from "Red (R)"

    def grayscale_backend(self):
        """Get the currently selected algorithm backend."""
        return self._backend_combo.currentData()

    def averaging_method(self):
        """Get the currently selected averaging method."""
        for choice, radio in self._averaging_radios.items():
            if radio.isChecked():
                return choice
        return "averaged_differences"

    def graph_type(self):
        """Get the currently selected graph type."""
        for choice, radio in self._graph_radios.items():
            if radio.isChecked():
                graph_name = monitor.GRAPH_TYPES[choice]
                return None if graph_name == "none" else graph_name
        return None

    def diff_amplification(self):
        """Get the currently selected difference amplification method."""
        for choice, radio in self._amp_radios.items():
            if radio.isChecked():
                return choice
        return "gain_factor"

    def _on_show_gain_toggled(self, checked):
        """
        Apply the new visibility immediately on the live Setup page, and
        persist it to the shared settings file so the choice is remembered
        next time, and shared with run_experiment_gui.py's own "Show Gain
        (dB) control" checkbox, which reads and writes this exact same
        show_gain key.
        """
        self._setup_page.set_gain_visible(checked)
        current = settings_manager.load_settings()
        current["show_gain"] = checked
        settings_manager.save_settings(current)


# ==============================================================================
# MAIN WINDOW
# ==============================================================================

class MainWindow(QMainWindow):
    """
    Left nav rail ("Setup", "Live Monitor") + QStackedWidget — the same
    shell run_experiment_gui.py uses, kept for visual and architectural
    consistency between the two dashboards in this project.
    """

    def __init__(self):
        super().__init__()
        # theme defaults to "dark" (this file's original, only look)
        # when run standalone with no theme key saved yet. espi_app
        # writes its own light/dark choice into this same settings file
        # before launching this window, so the two always agree.
        self._current_theme = settings_manager.load_settings().get("theme", "dark")
        QApplication.instance().setStyleSheet(_stylesheet_for(self._current_theme))
        self.setWindowTitle("ESPI Camera Monitor")

        # Clamp the launch size to the actual screen instead of a bare
        # resize(900, 700): on a screen shorter than 700px tall (or if a
        # future page grows past that height again), a fixed resize() can
        # come up partly off screen, cropping whatever is at the bottom
        # (the Settings button, the Live Monitor page's control row). Using
        # the smaller of "our preferred size" and "what actually fits" means
        # the window is always fully visible at launch, on any screen.
        screen = QApplication.instance().primaryScreen()
        preferred_width, preferred_height = settings_manager.PREVIEW_SIZES.get(
            settings_manager.load_settings().get("preview_size", "Medium"), (900, 700)
        )
        if screen is not None:
            available = screen.availableGeometry()
            margin = 40
            preferred_width = min(preferred_width, available.width() - margin)
            preferred_height = min(preferred_height, available.height() - margin)
        self.resize(preferred_width, preferred_height)

        # Create a custom nav widget with layout for bottom-sticking Settings
        nav_widget = QFrame()
        nav_widget.setObjectName("Sidebar")
        nav_widget.setFixedWidth(SIDEBAR_WIDTH)
        nav_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        nav_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(SIDEBAR_MARGIN, SIDEBAR_MARGIN, SIDEBAR_MARGIN, 0)
        nav_layout.setSpacing(0)

        # Brand header: anchors the sidebar with an icon and app name instead
        # of dropping straight into the nav items with no visual identity.
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 6, 6, 18)
        header_layout.setSpacing(10)
        icon_color = QColor(theme.icon_color(self._current_theme))
        self._brand_icon = QLabel()
        self._brand_icon.setPixmap(qta.icon('mdi6.camera-iris', color=icon_color).pixmap(22, 22))
        brand_title = QLabel("ESPI Monitor")
        brand_title.setObjectName("BrandTitle")
        header_layout.addWidget(self._brand_icon)
        header_layout.addWidget(brand_title)
        header_layout.addStretch()
        nav_layout.addLayout(header_layout)

        # Top section: Setup and Live Monitor
        self._nav = QListWidget()
        self._nav.setObjectName("NavRail")
        self._nav.setIconSize(QSize(18, 18))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.tune-variant', color=icon_color), "Setup"
        ))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.video-outline', color=icon_color), "Live Monitor"
        ))
        self._nav.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        nav_layout.addWidget(self._nav)

        # Separator line (using a QFrame)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("NavSeparator")
        nav_layout.addWidget(separator)

        # Stretch pushes Settings button to the bottom
        nav_layout.addStretch()

        # Settings button at bottom
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("SidebarSettings")
        self.settings_button.setIcon(qta.icon('mdi6.cog-outline', color=icon_color))
        self.settings_button.clicked.connect(self._open_settings)
        nav_layout.addWidget(self.settings_button)


        nav_widget.setLayout(nav_layout)

        # Setup nav item gating
        self._nav.setCurrentRow(0)
        # "Live Monitor" isn't reachable until a monitor session starts —
        # mirrors run_experiment_gui.py's nav gating (can't jump to Results
        # before a sweep finishes).
        self._nav.item(1).setFlags(self._nav.item(1).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        # Connect itemClicked (not currentRowChanged) so nav navigation works
        # even when returning from Settings page
        self._nav.itemClicked.connect(self._on_nav_item_clicked)



        self.setup_page = SetupPage()
        self.live_monitor_page = LiveMonitorPage()
        self.settings_page = SettingsPage(self.setup_page)


        self._stack = QStackedWidget()
        self._stack.addWidget(self.setup_page)
        self._stack.addWidget(self.live_monitor_page)
        self._stack.addWidget(self.settings_page)

        central = QWidget()
        central_layout = QHBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(nav_widget, stretch=0)
        central_layout.addWidget(self._stack, stretch=1)
        central.setLayout(central_layout)
        self.setCentralWidget(central)

        # Elevation: every card-style surface gets a real drop shadow (see
        # _apply_card_shadow()'s docstring in run_experiment_gui.py for why
        # this can't just live in the QSS string below).
        for card in self.findChildren(QGroupBox):
            _apply_card_shadow(card)
        for card in self.findChildren(QWidget, "CanvasCard"):
            _apply_card_shadow(card)

        self.statusBar().showMessage("Idle")

        self.setup_page.start_button.clicked.connect(self._start_monitor)
        self.live_monitor_page.stopped.connect(self._on_monitor_stopped)

    def _on_nav_item_clicked(self, item):
        """Navigate to the page corresponding to the clicked nav item."""
        row = self._nav.row(item)
        self._stack.setCurrentIndex(row)

    def _open_settings(self):
        """Open settings page. Nav selection is left unchanged (Settings is not a nav item)."""
        self._stack.setCurrentIndex(2)

    def refresh_theme(self, theme_name):
        """
        Re-apply the app stylesheet and re-color this window's icons for
        a new theme.

        Called by espi_app when the user changes theme in Settings while
        this window is already open. The stylesheet itself restyles every
        widget automatically (Qt re-applies QSS to the whole app the
        moment setStyleSheet() is called again) — only the qtawesome
        icons need to be explicitly re-created, since a QIcon is a static
        bitmap baked at one fixed color and does not follow stylesheet
        changes on its own.
        """
        self._current_theme = theme_name
        QApplication.instance().setStyleSheet(_stylesheet_for(theme_name))

        icon_color = QColor(theme.icon_color(theme_name))
        self._brand_icon.setPixmap(qta.icon('mdi6.camera-iris', color=icon_color).pixmap(22, 22))
        self._nav.item(0).setIcon(qta.icon('mdi6.tune-variant', color=icon_color))
        self._nav.item(1).setIcon(qta.icon('mdi6.video-outline', color=icon_color))
        self.settings_button.setIcon(qta.icon('mdi6.cog-outline', color=icon_color))

    def _save_last_used_settings_if_enabled(self, camera_choice, settings):
        """
        If "Use Last Settings as Default" is on, remember whatever was
        just used to start this monitor session as the new default for
        next time — the counterpart to SetupPage locking those same
        fields so they cannot be typed in by hand while this is active.

        Does nothing if the flag is off, leaving whatever defaults were
        last explicitly configured untouched.
        """
        current = settings_manager.load_settings()
        if not current.get("use_last_settings_as_default", False):
            return

        current["default_camera_choice"] = camera_choice
        current["monitor_default_exposure"] = settings["exposure_s"]
        current["monitor_default_gain"] = settings["gain_db"]
        current["monitor_default_gain_factor"] = settings["gain_factor"]
        current["last_used_dashboard"] = "monitor"
        settings_manager.save_settings(current)

    def _start_monitor(self):
        camera_choice = self.setup_page.camera_choice()
        camera_index = self.setup_page.camera_index()
        settings = self.setup_page.settings()
        self._save_last_used_settings_if_enabled(camera_choice, settings)
        # Merge in the processing strategy settings from settings page
        settings["averaging_method"] = self.settings_page.averaging_method()
        settings["graph_type"] = self.settings_page.graph_type()
        settings["diff_amplification"] = self.settings_page.diff_amplification()
        settings["grayscale_method"] = self.settings_page.grayscale_method()
        settings["grayscale_color"] = self.settings_page.grayscale_color()
        settings["grayscale_backend"] = self.settings_page.grayscale_backend()

        self.live_monitor_page.start_monitor(camera_choice, camera_index, settings)

        self._nav.item(1).setFlags(self._nav.item(1).flags() | Qt.ItemFlag.ItemIsEnabled)
        self._nav.item(0).setFlags(self._nav.item(0).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.setCurrentRow(1)
        # setCurrentRow doesn't fire itemClicked, so switch stack directly
        self._stack.setCurrentIndex(1)
        # setFocus() must come AFTER setCurrentIndex(): switching the
        # stack's visible page can itself move focus onto whatever is
        # focusable there, silently undoing an earlier setFocus() call on
        # the nav rail. setCurrentRow() alone changes which row is current
        # and selected, but does not move actual keyboard focus onto the
        # nav rail, and Qt style sheets can render ::item:selected as a
        # much fainter "inactive" highlight whenever the widget holding
        # the selection isn't the one with real focus, which it never was
        # here since the click that got us here landed on the Start
        # Monitor button, not the nav list. Forcing focus explicitly,
        # last, is what makes the highlight actually show, the same way it
        # already did for Setup, which happened to receive initial focus
        # at construction time.
        self._nav.setFocus(Qt.FocusReason.OtherFocusReason)
        self.statusBar().showMessage("Monitoring")

    def _on_monitor_stopped(self):
        self._nav.item(0).setFlags(self._nav.item(0).flags() | Qt.ItemFlag.ItemIsEnabled)
        self._nav.item(1).setFlags(self._nav.item(1).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.setCurrentRow(0)
        # setCurrentRow doesn't fire itemClicked, so switch stack directly
        self._stack.setCurrentIndex(0)
        # setFocus() after setCurrentIndex(), see _start_monitor() above for why.
        self._nav.setFocus(Qt.FocusReason.OtherFocusReason)
        self.statusBar().showMessage("Idle")

    def closeEvent(self, event):
        # The live-monitor loop is cooperatively stoppable every frame (see
        # MonitorWorker), so closing mid-session is always safe once we
        # wait for it to actually stop — unlike run_experiment_gui.py's
        # sweep, there is no uninterruptible operation to worry about here.
        if self.live_monitor_page.is_running():
            reply = QMessageBox.question(
                self,
                "Monitor running",
                "The live monitor is still running. Stop it and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.live_monitor_page.stop_and_wait()
        event.accept()

    # No resizeEvent() override: the nav list's own Expanding vertical size
    # policy (set in __init__) is what makes it grow with the window. An
    # earlier version forced the nav list's min/max height here from a value
    # computed off the sidebar's own current height, which is stale at the
    # moment resizeEvent() fires. That, combined with a fixed max-height in
    # the QSS below, meant every resize raised the nav list's minimum height
    # a bit further and never lowered it, so growing the window once (e.g.
    # maximizing it) permanently prevented shrinking back down afterward.


# ==============================================================================
# STYLESHEET
# ==============================================================================
# The color tokens and full stylesheet now live in theme.py, shared with
# run_experiment_gui.py (and, via espi_app/styles.py, espi_app's own
# windows) so every window always matches whichever theme is selected.
# Only this file's own nav item height, which the shared stylesheet does
# not know about, is appended on top — see _stylesheet_for() below.

# Sidebar layout constants
SIDEBAR_WIDTH = 176
SIDEBAR_MARGIN = 8
SIDEBAR_ITEM_HEIGHT = 38


def _stylesheet_for(theme_name):
    """Shared stylesheet plus this file's own nav item height rule."""
    return theme.build_stylesheet(theme_name) + (
        f"QListWidget#NavRail::item {{ height: {SIDEBAR_ITEM_HEIGHT}px; }}"
    )


def _apply_card_shadow(widget, blur_radius=28, y_offset=6, alpha=140):
    """
    QSS has no box-shadow — this is the actual mechanism Qt offers for the
    same "elevated card floating above the background" effect, applied
    directly to a widget (a QGroupBox, or the live monitor page's
    CanvasCard) rather than expressed in the stylesheet string above.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def main():
    app = QApplication(sys.argv)
    # MainWindow.__init__ applies the theme stylesheet itself (reading the
    # saved theme from settings_manager), so main() does not need to here.
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
