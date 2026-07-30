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
# GRAYSCALE CONVERSION ALGORITHMS — SINGLE-CHANNEL EXTRACTION
# ==============================================================================

def _grayscale_pillow(bgr_frame: np.ndarray, color_code: str) -> np.ndarray:
    """
    Extract single color channel using Pillow and merge across all channels.
    Returns a grayscale array with all channels equal to the selected color intensity.
    Time: O(width * height), Space: O(width * height) for the output.
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
    Time: O(width * height), Space: O(width * height) for the output.
    """
    channel_map = {"B": 0, "G": 1, "R": 2}
    channel_idx = channel_map[color_code]
    return bgr_frame[:, :, channel_idx].copy()


def _grayscale_opencv_split(bgr_frame: np.ndarray, color_code: str) -> np.ndarray:
    """
    Extract single color channel using cv2.split (OpenCV's channel-splitting
    function, BGR layout).
    Color map: B=0, G=1, R=2 (OpenCV BGR convention), the same as the numpy
    backend, so all three backends return identical channel intensities and
    differ only in which library performs the split.
    Time: O(width * height), Space: O(width * height) per split channel.
    """
    channel_map = {"B": 0, "G": 1, "R": 2}
    channels = cv2.split(bgr_frame)  # (B, G, R) as separate 2D arrays
    return channels[channel_map[color_code]]


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
        elif backend == "opencv_split":
            return _grayscale_opencv_split(frame, color)
        else:
            raise ValueError(f"Invalid backend: {backend}")
    else:
        raise ValueError(f"Invalid method: {method}")


_GRAYSCALE_COMPARISON_METHODS = ("standard", "numpy", "pillow", "opencv_split")


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


# ==============================================================================
# DIFFERENCE AMPLIFICATION ALGORITHMS
# ==============================================================================
# Every function below is only ever called on the post-averaging diff array
# (raw_diff / raw_change in MonitorWorker), never on the live feed frame. See
# _apply_diff_amplification's docstring for why that split matters.

def _apply_clahe(gray: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple = (8, 8)) -> np.ndarray:
    """
    Contrast Limited Adaptive Histogram Equalization.

    Equalizes contrast within local tiles instead of over the whole image, so
    faint fringes in a dim region get boosted without blowing out a bright
    region elsewhere in the same frame. clip_limit caps how much any single
    tile's histogram can be stretched, which is what keeps sensor noise in
    dark tiles from being amplified into speckle.

    Args:
        gray: 2D uint8 array (the diff frame)
        clip_limit: contrast limiting threshold, 0.5-10.0 (higher = more contrast, more noise)
        tile_grid_size: (rows, cols) of tiles to equalize independently

    Time: O(width * height), Space: O(width * height) for the output.
    """
    gray = np.ascontiguousarray(gray).astype(np.uint8, copy=False)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(gray)


def _apply_gamma_correction(gray: np.ndarray, gamma: float = 0.5) -> np.ndarray:
    """
    Non-linear brightness remapping via a precomputed lookup table (LUT).

    Uses the standard power-law form output = 255 * (input / 255) ** gamma.
    gamma < 1 brightens dark and mid-tone pixels (a fractional power pulls
    values up towards 255) without touching pixels already at 0 or 255,
    which is what lets faint fringes in a mostly-dark diff image become
    visible without clipping the few bright pixels that are already at full
    contrast. gamma > 1 does the opposite and darkens.

    NOTE: a common version of this snippet (e.g. the widely copied
    pyimagesearch "adjust_gamma") instead raises to the power of 1/gamma.
    That inverts the direction above, so gamma=0.5 would darken instead of
    brighten, which contradicts its own docstring in every copy of it found
    while building this. Verified numerically before picking a direction:
    only the un-inverted exponent used here brightens at the gamma=0.5
    default this project asked for.

    Args:
        gray: 2D uint8 array (the diff frame)
        gamma: 0.1-3.0. Values below 1.0 brighten, above 1.0 darken.

    Time: O(256) to build the LUT + O(width * height) for cv2.LUT's pass over
    every pixel, Space: O(width * height) for the output.
    """
    gray = np.ascontiguousarray(gray).astype(np.uint8, copy=False)
    lut = np.array(
        [((i / 255.0) ** gamma) * 255 for i in range(256)]
    ).astype(np.uint8)
    return cv2.LUT(gray, lut)


_AMPLIFICATION_METHODS = ("none", "normalize", "gain_factor", "clahe", "gamma")


def _apply_diff_amplification(
    cam_lib,
    raw_diff: np.ndarray,
    method: str,
    gain_factor: float,
    clahe_clip_limit: float = 2.0,
    clahe_tile_grid_size: tuple = (8, 8),
    gamma: float = 0.5,
) -> np.ndarray:
    """
    Apply the selected contrast amplification to a raw difference frame.

    Callers must only ever pass the post-averaging diff array here (see
    MonitorWorker._run_frame_averaging / _run_averaged_differences), never
    the raw or averaged live feed frame, since amplification is meant to make
    the subtracted fringe pattern visible, not to alter what the live feed
    shows the operator.

    "normalize" is delegated to cam_lib.amplify_difference() rather than
    implemented locally, since it is camera-library-specific (each
    camera_control*.py module owns its own copy). CLAHE and gamma are plain
    OpenCV/NumPy operations with no camera-specific behavior, so they live
    here instead.
    """
    if method == "normalize":
        return cam_lib.amplify_difference(raw_diff)
    elif method == "gain_factor":
        return cv2.convertScaleAbs(raw_diff, alpha=gain_factor)
    elif method == "clahe":
        return _apply_clahe(raw_diff, clahe_clip_limit, clahe_tile_grid_size)
    elif method == "gamma":
        return _apply_gamma_correction(raw_diff, gamma)
    else:  # "none"
        return raw_diff


def _compare_amplification_methods(
    cam_lib,
    raw_diff: np.ndarray,
    gain_factor: float,
    clahe_clip_limit: float = 2.0,
    clahe_tile_grid_size: tuple = (8, 8),
    gamma: float = 0.5,
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
        result = _apply_diff_amplification(
            cam_lib, raw_diff, method, gain_factor,
            clahe_clip_limit, clahe_tile_grid_size, gamma,
        )
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
        self._radios["2"].setChecked(True)  # same default as choose_camera()

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
        self.exposure_spin.setValue(0.06)
        settings_layout.addWidget(self.exposure_spin)

        settings_layout.addWidget(QLabel("Gain (dB):"))
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setDecimals(2)
        self.gain_spin.setRange(-20.0, 50.0)  # 0 dB and negative values are valid
        self.gain_spin.setValue(1.0)
        settings_layout.addWidget(self.gain_spin)

        settings_layout.addWidget(QLabel("gain_factor (subtraction display amplifier):"))
        self.gain_factor_spin = QDoubleSpinBox()
        self.gain_factor_spin.setDecimals(2)
        self.gain_factor_spin.setRange(0.01, 200.0)
        self.gain_factor_spin.setValue(10.0)
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
        self._clahe_clip_limit = settings.get("clahe_clip_limit", 2.0)
        self._clahe_tile_grid_size = settings.get("clahe_tile_grid_size", (8, 8))
        self._gamma = settings.get("gamma", 0.5)
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
        try:
            if self._camera_choice == "1":
                camera = cam_lib.connect_camera()
            else:
                camera = cam_lib.connect_camera(self._camera_index)

            if camera is None:
                self.error.emit(
                    "Could not open the camera. Check it is plugged in and try again."
                )
                return

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
            # grab_single_frame_color(), not grab_single_frame(): the plain
            # version already reduces a color frame to greyscale before
            # returning it, which would make single-channel R/G/B extraction
            # below a no-op no matter what color or backend was picked.
            frame = cam_lib.grab_single_frame_color(camera)
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
                averaged = np.mean(frame_buffer, axis=0).astype(np.uint8)
                frame_buffer = []

                diff = None
                if prev_averaged is not None:
                    raw_diff = cam_lib.substract_frames(prev_averaged, averaged)
                    self.raw_diff_ready.emit(raw_diff)
                    diff = _apply_diff_amplification(
                        cam_lib, raw_diff, self._diff_amplification, gain_factor,
                        self._clahe_clip_limit, self._clahe_tile_grid_size, self._gamma,
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
            # grab_single_frame_color(), see _run_frame_averaging() above for why.
            frame1 = cam_lib.grab_single_frame_color(camera)
            if frame1 is None:
                self.error.emit("Failed to grab frame — check camera connection.")
                break

            frame2 = cam_lib.grab_single_frame_color(camera)
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
                averaged_diff = np.mean(diff_buffer, axis=0).astype(np.uint8)
                diff_buffer = []

                if prev_averaged_diff is not None:
                    raw_change = cam_lib.substract_frames(prev_averaged_diff, averaged_diff)
                    self.raw_diff_ready.emit(raw_change)
                    current_diff = _apply_diff_amplification(
                        cam_lib, raw_change, self._diff_amplification, gain_factor,
                        self._clahe_clip_limit, self._clahe_tile_grid_size, self._gamma,
                    )

                prev_averaged_diff = averaged_diff


# ==============================================================================
# AMPLIFICATION COMPARISON DIALOG
# ==============================================================================

class AmplificationComparisonDialog(QDialog):
    """
    Shows every diff amplification method (none, normalize, gain_factor,
    CLAHE, gamma) applied to the same raw diff frame, side by side, so their
    effect can be compared visually without restarting the monitor with a
    different setting each time.
    """

    _LABELS = {
        "none": "No amplification",
        "normalize": "Normalize contrast",
        "gain_factor": "Gain factor",
        "clahe": "CLAHE",
        "gamma": "Gamma correction",
    }

    def __init__(
        self,
        cam_lib,
        raw_diff,
        gain_factor,
        clahe_clip_limit=2.0,
        clahe_tile_grid_size=(8, 8),
        gamma=0.5,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Compare Amplification Methods")

        results = _compare_amplification_methods(
            cam_lib, raw_diff, gain_factor,
            clahe_clip_limit, clahe_tile_grid_size, gamma,
        )

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
    backends (NumPy, Pillow, OpenCV Split) applied to the same raw frame,
    side by side, using whichever color channel is currently selected in
    Settings. Answers "does switching to single-channel extraction actually
    make a visible difference" by letting the operator look at the results
    instead of guessing.
    """

    _LABELS = {
        "standard": "Standard Full-RGB",
        "numpy": "Single-Channel (NumPy)",
        "pillow": "Single-Channel (Pillow)",
        "opencv_split": "Single-Channel (OpenCV Split)",
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
        self._last_raw_frame = None

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
            "Run Standard Full-RGB and all three single-channel backends on the current frame, side by side."
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
        self._last_raw_frame = None
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
        self._last_raw_frame = None

    def _stop_monitor(self):
        if self._worker is not None:
            self._worker.stop()
        self.stop_button.setEnabled(False)
        self.compare_button.setEnabled(False)
        self.compare_grayscale_button.setEnabled(False)
        self._last_raw_diff = None
        self._last_raw_frame = None

    def _on_raw_diff(self, raw_diff):
        self._last_raw_diff = raw_diff
        self.compare_button.setEnabled(True)

    def _on_raw_frame(self, raw_frame):
        self._last_raw_frame = raw_frame
        self.compare_grayscale_button.setEnabled(True)

    def _open_grayscale_comparison_dialog(self):
        if self._last_raw_frame is None:
            return

        color = self._settings.get("grayscale_color", "R") if self._settings else "R"
        dialog = GrayscaleComparisonDialog(self._last_raw_frame, color, parent=self)
        dialog.exec()

    def _open_comparison_dialog(self):
        if self._last_raw_diff is None or self._worker is None:
            return

        module_name = _CAMERA_CONTROL_MODULES[self._worker._camera_choice]
        cam_lib = importlib.import_module(module_name)

        dialog = AmplificationComparisonDialog(
            cam_lib,
            self._last_raw_diff,
            self._settings["gain_factor"],
            self._settings.get("clahe_clip_limit", 2.0),
            self._settings.get("clahe_tile_grid_size", (8, 8)),
            self._settings.get("gamma", 0.5),
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

<p><b>Normalize contrast</b> finds the darkest and brightest pixels
currently in the difference image and stretches everything between them to
fill the full 0 to 255 range. Simple and effective, though one stray very
bright pixel can eat up range that would otherwise go to the real fringe
pattern.</p>

<p><b>Gain factor</b> multiplies every pixel by a fixed number you choose in
the capture settings. Straightforward and predictable, but pick a number too
large and bright areas get clipped to solid white, losing detail there.</p>

<p><b>CLAHE</b> (Contrast Limited Adaptive Histogram Equalization) divides
the image into a grid of small tiles and boosts contrast within each tile
separately, instead of stretching the whole image the same way. A clip limit
controls how aggressively any single tile can be stretched. This helps
bring out faint fringes in dim corners of the image without also amplifying
camera sensor noise into fake looking speckle, which is what tends to happen
if a global stretch is pushed too hard.</p>

<p><b>Gamma correction</b> reshapes brightness using a curve instead of a
straight stretch, brightening dark and mid range pixels more than pixels
that are already bright. A gamma value below 1.0 brightens; above 1.0
darkens. Pixels already at pure black or pure white are left alone either
way, so the brightest fringe detail is never lost to clipping.</p>

<p>Not sure which to pick? The <b>Compare Amplification Methods</b> button
on the Live Monitor page runs all five side by side on the same frame, so
you can look at the results instead of guessing.</p>
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
            "opencv_split": "OpenCV channel splitting (cv2.split)",
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
            "normalize": "Stretch contrast to full 0-255 range using OpenCV NORM_MINMAX.",
            "gain_factor": "Multiply pixel values by the gain_factor from capture settings.",
            "clahe": "Contrast Limited Adaptive Histogram Equalization: boosts faint fringes tile by tile without amplifying noise in dark regions.",
            "gamma": "Non-linear brightness remapping via a lookup table: brightens dark/mid-tones without clipping bright pixels.",
        }
        amp_labels = {
            "none": "No amplification",
            "normalize": "Normalize contrast",
            "gain_factor": "Gain factor only",
            "clahe": "CLAHE",
            "gamma": "Gamma correction",
        }
        for choice in amp_tooltips.keys():
            radio = QRadioButton(amp_labels[choice])
            radio.setToolTip(amp_tooltips[choice])
            self._amp_group.addButton(radio)
            self._amp_radios[choice] = radio
            amp_layout.addWidget(radio)

        # CLAHE parameter controls (only shown when "clahe" is selected)
        self._clahe_clip_label = QLabel("Clip Limit:")
        self._clahe_clip_spin = QDoubleSpinBox()
        self._clahe_clip_spin.setDecimals(2)
        self._clahe_clip_spin.setRange(0.5, 10.0)
        self._clahe_clip_spin.setValue(2.0)

        clip_layout = QHBoxLayout()
        clip_layout.addWidget(self._clahe_clip_label)
        clip_layout.addWidget(self._clahe_clip_spin)
        clip_layout.addStretch()
        amp_layout.addLayout(clip_layout)

        self._tile_grid_label = QLabel("Tile Grid Size (rows x cols):")
        self._tile_rows_spin = QSpinBox()
        self._tile_rows_spin.setRange(2, 64)
        self._tile_rows_spin.setValue(8)
        self._tile_cols_spin = QSpinBox()
        self._tile_cols_spin.setRange(2, 64)
        self._tile_cols_spin.setValue(8)

        tile_layout = QHBoxLayout()
        self._tile_x_label = QLabel("x")

        tile_layout.addWidget(self._tile_grid_label)
        tile_layout.addWidget(self._tile_rows_spin)
        tile_layout.addWidget(self._tile_x_label)
        tile_layout.addWidget(self._tile_cols_spin)
        tile_layout.addStretch()
        amp_layout.addLayout(tile_layout)

        # Gamma parameter control (only shown when "gamma" is selected)
        self._gamma_label = QLabel("Gamma:")
        self._gamma_spin = QDoubleSpinBox()
        self._gamma_spin.setDecimals(2)
        self._gamma_spin.setRange(0.1, 3.0)
        self._gamma_spin.setValue(0.5)

        gamma_layout = QHBoxLayout()
        gamma_layout.addWidget(self._gamma_label)
        gamma_layout.addWidget(self._gamma_spin)
        gamma_layout.addStretch()
        amp_layout.addLayout(gamma_layout)

        amp_layout.addStretch()
        amp_group.setLayout(amp_layout)
        layout.addWidget(amp_group)

        # Wire amplification radio changes to update CLAHE/gamma param visibility
        # (must be connected before setting the default, same reasoning as grayscale above)
        for radio in self._amp_radios.values():
            radio.toggled.connect(self._update_amplification_ui_visibility)

        self._amp_radios["gain_factor"].setChecked(True)
        self._update_amplification_ui_visibility()

        layout.addStretch()
        self.setLayout(layout)

    def _update_amplification_ui_visibility(self):
        """Show/hide CLAHE and gamma param controls based on amplification method selection."""
        is_clahe = self._amp_radios["clahe"].isChecked()
        is_gamma = self._amp_radios["gamma"].isChecked()

        self._clahe_clip_label.setVisible(is_clahe)
        self._clahe_clip_spin.setVisible(is_clahe)
        self._tile_grid_label.setVisible(is_clahe)
        self._tile_rows_spin.setVisible(is_clahe)
        self._tile_x_label.setVisible(is_clahe)
        self._tile_cols_spin.setVisible(is_clahe)

        self._gamma_label.setVisible(is_gamma)
        self._gamma_spin.setVisible(is_gamma)

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
        button.setIcon(qta.icon('mdi6.help-circle-outline', color=QColor(_TEXT_SECONDARY)))
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

    def clahe_clip_limit(self):
        """Get the configured CLAHE clip limit (0.5-10.0)."""
        return self._clahe_clip_spin.value()

    def clahe_tile_grid_size(self):
        """Get the configured CLAHE tile grid size as (rows, cols)."""
        return (self._tile_rows_spin.value(), self._tile_cols_spin.value())

    def gamma_value(self):
        """Get the configured gamma correction value (0.1-3.0)."""
        return self._gamma_spin.value()

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
        QApplication.instance().setStyleSheet(_STYLESHEET)
        self.setWindowTitle("ESPI Camera Monitor")
        self.resize(900, 700)

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
        brand_icon = QLabel()
        brand_icon.setPixmap(qta.icon('mdi6.camera-iris', color=QColor(_TEXT_PRIMARY)).pixmap(22, 22))
        brand_title = QLabel("ESPI Monitor")
        brand_title.setObjectName("BrandTitle")
        header_layout.addWidget(brand_icon)
        header_layout.addWidget(brand_title)
        header_layout.addStretch()
        nav_layout.addLayout(header_layout)

        # Top section: Setup and Live Monitor
        self._nav = QListWidget()
        self._nav.setObjectName("NavRail")
        self._nav.setIconSize(QSize(18, 18))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.tune-variant', color=QColor(_TEXT_SECONDARY)), "Setup"
        ))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.video-outline', color=QColor(_TEXT_SECONDARY)), "Live Monitor"
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
        self.settings_button.setIcon(qta.icon('mdi6.cog-outline'))
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

    def _start_monitor(self):
        camera_choice = self.setup_page.camera_choice()
        camera_index = self.setup_page.camera_index()
        settings = self.setup_page.settings()
        # Merge in the processing strategy settings from settings page
        settings["averaging_method"] = self.settings_page.averaging_method()
        settings["graph_type"] = self.settings_page.graph_type()
        settings["diff_amplification"] = self.settings_page.diff_amplification()
        settings["grayscale_method"] = self.settings_page.grayscale_method()
        settings["grayscale_color"] = self.settings_page.grayscale_color()
        settings["grayscale_backend"] = self.settings_page.grayscale_backend()
        settings["clahe_clip_limit"] = self.settings_page.clahe_clip_limit()
        settings["clahe_tile_grid_size"] = self.settings_page.clahe_tile_grid_size()
        settings["gamma"] = self.settings_page.gamma_value()

        self.live_monitor_page.start_monitor(camera_choice, camera_index, settings)

        self._nav.item(1).setFlags(self._nav.item(1).flags() | Qt.ItemFlag.ItemIsEnabled)
        self._nav.item(0).setFlags(self._nav.item(0).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.setCurrentRow(1)
        # setCurrentRow doesn't fire itemClicked, so switch stack directly
        self._stack.setCurrentIndex(1)
        self.statusBar().showMessage("Monitoring")

    def _on_monitor_stopped(self):
        self._nav.item(0).setFlags(self._nav.item(0).flags() | Qt.ItemFlag.ItemIsEnabled)
        self._nav.item(1).setFlags(self._nav.item(1).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.setCurrentRow(0)
        # setCurrentRow doesn't fire itemClicked, so switch stack directly
        self._stack.setCurrentIndex(0)
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # When window is resized, update nav list height to fill available space
        if self._nav:
            sidebar_height = self._nav.parent().height() if self._nav.parent() else self.height()
            # Calculate available height: sidebar height minus margins and other items
            # margins(top) + separator(~17px) + button(~40px) = 65px
            available_height = max(76, sidebar_height - 65)  # min 76px for 2 items
            self._nav.setMinimumHeight(available_height)
            self._nav.setMaximumHeight(available_height)


# ==============================================================================
# STYLESHEET
# ==============================================================================
# The same strictly monochrome dark theme as run_experiment_gui.py (no color
# accents — off-blacks and grays only), for visual consistency between the
# two dashboards in this project. See that file's _STYLESHEET for the full
# rationale behind each choice.

_BASE_BG = "#1e1e1e"
_SURFACE_BG = "#292929"
_BORDER = "#383838"
_TEXT_SECONDARY = "#8a8a8a"
_TEXT_PRIMARY = "#e0e0e0"
_RAIL_BG = "#171717"

# Sidebar layout constants
SIDEBAR_WIDTH = 176
SIDEBAR_MARGIN = 8
SIDEBAR_ITEM_HEIGHT = 38


_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {_BASE_BG};
    color: {_TEXT_PRIMARY};
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QFrame#Sidebar {{
    background-color: {_RAIL_BG};
    border: none;
}}

QLabel#BrandTitle {{
    color: {_TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 600;
    background-color: transparent;
}}

QListWidget#NavRail {{
    background-color: {_RAIL_BG};
    border: none;
    border-right: 1px solid {_BORDER};
    padding: 12px 0px;
    outline: 0;
    max-height: {SIDEBAR_ITEM_HEIGHT * 2 + 24}px;
}}
QListWidget#NavRail::item {{
    color: {_TEXT_SECONDARY};
    padding: 14px 22px;
    border-left: 3px solid transparent;
    height: {SIDEBAR_ITEM_HEIGHT}px;
}}
QListWidget#NavRail::item:hover {{
    background-color: #202020;
    color: {_TEXT_PRIMARY};
}}
QListWidget#NavRail::item:selected {{
    background-color: {_SURFACE_BG};
    color: {_TEXT_PRIMARY};
    border-left: 3px solid {_TEXT_PRIMARY};
}}
QListWidget#NavRail::item:disabled {{
    color: #4a4a4a;
}}


QFrame#NavSeparator {{
    background-color: {_BORDER};
    margin: 8px 12px;
}}
QPushButton#SidebarSettings {{
    background-color: transparent;
    color: {_TEXT_SECONDARY};
    text-align: left;
    padding-left: 22px;
    padding: 8px 8px;
    border: none;
    outline: 0;
}}
QPushButton#SidebarSettings:hover {{
    background-color: {_SURFACE_BG};
    color: {_TEXT_PRIMARY};
}}
QPushButton#SidebarSettings:pressed {{
    background-color: {_BORDER};
}}

QGroupBox {{
    background-color: {_SURFACE_BG};
    border: 1px solid {_BORDER};
    border-radius: 12px;
    margin-top: 18px;
    padding: 20px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {_TEXT_SECONDARY};
}}

QLabel {{
    color: {_TEXT_PRIMARY};
    background-color: transparent;
}}
QLabel#SummaryLabel {{
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
    background-color: #232323;
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 12px;
}}
QLabel#FeedFrame {{
    background-color: #141414;
    border: 1px solid {_BORDER};
    border-radius: 12px;
    color: {_TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#InfoLabel {{
    color: {_TEXT_SECONDARY};
    font-size: 12px;
    background-color: transparent;
}}

QPushButton {{
    background-color: {_SURFACE_BG};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 9px 18px;
    color: {_TEXT_PRIMARY};
}}
QPushButton:hover {{ background-color: #333333; border-color: #4a4a4a; }}
QPushButton:pressed {{ background-color: #202020; }}
QPushButton:disabled {{ color: #5a5a5a; background-color: #232323; border-color: #2e2e2e; }}

QPushButton#PrimaryButton {{
    background-color: {_TEXT_PRIMARY};
    border: 1px solid {_TEXT_PRIMARY};
    color: #181818;
    font-weight: 600;
}}
QPushButton#PrimaryButton:hover {{ background-color: #cfcfcf; border-color: #cfcfcf; }}
QPushButton#PrimaryButton:pressed {{ background-color: #b0b0b0; border-color: #b0b0b0; }}
QPushButton#PrimaryButton:disabled {{
    background-color: #4a4a4a; border-color: #4a4a4a; color: #7a7a7a;
}}

QDoubleSpinBox, QSpinBox, QLineEdit {{
    background-color: {_SURFACE_BG};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    color: {_TEXT_PRIMARY};
    selection-background-color: #4a4a4a;
    selection-color: {_TEXT_PRIMARY};
}}
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{
    border: 1px solid {_TEXT_PRIMARY};
}}

QRadioButton {{
    spacing: 8px;
    padding: 4px 0px;
    background-color: transparent;
    outline: none;
}}

QPushButton#LearnMoreButton {{
    background-color: transparent;
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 4px 10px;
    color: {_TEXT_SECONDARY};
    font-size: 12px;
}}
QPushButton#LearnMoreButton:hover {{
    background-color: {_SURFACE_BG};
    color: {_TEXT_PRIMARY};
    border-color: #4a4a4a;
}}

QTextBrowser#LearnMoreBrowser {{
    background-color: #232323;
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 14px;
    color: {_TEXT_PRIMARY};
    font-size: 13px;
}}

QWidget#CanvasCard {{
    background-color: {_SURFACE_BG};
    border: 1px solid {_BORDER};
    border-radius: 12px;
}}

QStatusBar {{
    background-color: {_BASE_BG};
    border-top: 1px solid {_BORDER};
    color: {_TEXT_SECONDARY};
}}
"""


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
    app.setStyleSheet(_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
