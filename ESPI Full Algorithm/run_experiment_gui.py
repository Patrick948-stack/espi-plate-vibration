"""
run_experiment_gui.py
Author: Patrick Mulikuza

A PyQt6 dashboard version of run_experiment.py: one QMainWindow with a
left-hand navigation rail (Setup, Preview, Sweep, Results) instead of
run_experiment.py's four typed terminal questions, an embedded live camera
preview, a real progress bar for the frequency sweep, and an embedded
results viewer — instead of the terminal version's separate OpenCV preview
window and separate matplotlib results windows.

WHAT THIS FILE OWNS, AND WHAT IT DOESN'T
-----------------------------------------
Every rule about what a valid exposure is, what a camera choice means, how
to dispatch to the right pipeline, or how to build the results grid
already lives in run_experiment.py (fully tested by tests/test_run_experiment.py)
and in camera_control*.py / complete_pipeline*.py (fully tested by their own
test files). This file only turns those same rules into widgets and wires
the preview + sweep + results flow together with Qt signals — it
introduces no new business logic.

WHY THIS DOES NOT CALL _show_preview_feed() OR reconfigure_if_needed()
------------------------------------------------------------------------
_show_preview_feed() opens a blocking OpenCV window ("press 'e' to
continue") and reconfigure_if_needed() is a terminal input loop — neither
has a seam to redirect into Qt widgets. Embedding the preview here instead
means composing the same lower-level, already-tested building blocks
_show_preview_feed() itself uses — camera_control*.py's connect_camera(),
grab_single_frame(), disconnect_camera() — inside a QThread that emits each
frame through a signal instead of showing it in a cv2 window.

WHY THE SWEEP'S PROGRESS BAR PARSES STDOUT INSTEAD OF A CALLBACK
--------------------------------------------------------------------
Adding an on_progress() callback parameter to frequency_sweep() and
reference_frequency_sweep() in all three complete_pipeline*.py files would
touch six tested call sites in the sweep logic itself. Parsing the print()
output those functions already produce needs no changes there at all.
Trade-off: complete_pipeline.py's Basler sweep prints
"--- Sweeping frequency: X Hz ---" (no index), while
complete_pipeline_inclusive.py and complete_pipeline_allied_vision.py print
"[i/N]  X Hz  ..." (index built in) — SweepWorker below matches both
formats so the bar advances correctly no matter which camera is running.

HOW TO RUN
----------
    python3 run_experiment_gui.py

DEPENDENCIES
------------
    pip install PyQt6 matplotlib
Plus whichever camera SDK you plan to use, see run_experiment.py for details.
"""

import contextlib
import importlib
import io
import math
import os
import re
import sys

import cv2
import numpy as np
import qtawesome as qta

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from typing import Optional, Tuple

import run_experiment
from settings_dialog import SettingsPage
from settings_manager import load_settings, save_settings


# ==============================================================================
# FRAME -> QPIXMAP CONVERSION
# ==============================================================================

def _frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    """
    Convert a 2D uint8 greyscale numpy array (the same shape
    grab_single_frame() already returns) into a QPixmap a QLabel can
    display. See monitor_gui.py's identical helper for why .copy() matters:
    QImage() only wraps frame's existing memory buffer rather than copying
    it, and the next grabbed frame may reuse that same buffer.
    """
    frame = np.ascontiguousarray(frame)
    height, width = frame.shape
    image = QImage(frame.data, width, height, width, QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(image.copy())


def _total_sweep_steps(params):
    """
    Same frequency-count formula every complete_pipeline*.py sweep loop
    uses internally. Needed here because SweepWorker tracks progress by
    reading stdout rather than calling into the pipeline modules'
    internals directly (see the module docstring above) — Basler's sweep
    never prints a running total of its own, so this is the one place that
    total has to be computed independently instead of read off a log line.
    """
    start, end, step = params["start_freq"], params["end_freq"], params["step"]
    return math.floor((end - start) / step + 1e-9) + 1


# ==============================================================================
# STDOUT -> QT SIGNAL BRIDGE
# ==============================================================================

class EmittingStream(QObject):
    """
    A minimal stand-in for sys.stdout that emits each complete line through
    a Qt signal instead of printing it. contextlib.redirect_stdout only
    ever calls .write() and .flush(), so subclassing QObject to also carry
    a pyqtSignal costs nothing here — there's no real conflict between
    "is a valid stdout replacement" and "is a QObject."

    print() typically calls write() twice per line (once for the message,
    once for the trailing newline), so raw text is buffered here and only
    emitted once a full line (up to a "\\n") has accumulated — otherwise a
    single print() call could emit two ragged half-lines instead of one
    whole one.
    """

    text_written = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._buffer = ""

    def write(self, text):
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self.text_written.emit(line)

    def flush(self):
        pass


# ==============================================================================
# SETUP PAGE
# ==============================================================================

class SetupPage(QWidget):
    """
    Mirrors run_experiment.py's first three terminal questions —
    choose_camera(), choose_mode(), choose_sweep_params() — as one page
    with four QGroupBox sections, arranged two-by-two. No separate confirm
    step: the Preview stage that follows is the confirmation, the same way
    run_experiment.py's own live preview comes right after the settings are
    typed in.
    """

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout()
        grid = QGridLayout()
        grid.setSpacing(16)

        # ---- Camera group (mirrors choose_camera()) ----
        camera_group = QGroupBox("Camera")
        camera_layout = QVBoxLayout()
        self._camera_group = QButtonGroup(self)
        self._camera_radios = {}
        for choice, name in run_experiment.CAMERA_NAMES.items():
            radio = QRadioButton(name)
            self._camera_group.addButton(radio)
            self._camera_radios[choice] = radio
            camera_layout.addWidget(radio)
        # Load default camera from settings
        settings = load_settings()
        default_camera = settings.get("default_camera_choice", "2")
        self._camera_radios[default_camera].setChecked(True)
        camera_layout.addStretch()
        camera_group.setLayout(camera_layout)
        grid.addWidget(camera_group, 0, 0)

        # ---- Mode group (mirrors choose_mode()) ----
        mode_group = QGroupBox("Subtraction mode")
        mode_layout = QVBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._mode_radios = {}
        mode_labels = {
            "1": "Pair subtraction\n(two frames subtracted at each frequency)",
            "2": "Reference subtraction\n(every frame compared to one resting baseline)",
        }
        for choice, label in mode_labels.items():
            radio = QRadioButton(label)
            self._mode_group.addButton(radio)
            self._mode_radios[choice] = radio
            mode_layout.addWidget(radio)
        self._mode_radios["1"].setChecked(True)  # Pair subtraction is default mode
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        grid.addWidget(mode_group, 0, 1)

        # ---- Frequency sweep group (mirrors choose_sweep_params(), part 1) ----
        freq_group = QGroupBox("Frequency sweep")
        freq_layout = QGridLayout()
        freq_layout.addWidget(QLabel("Start frequency:"), 0, 0)
        self.start_freq_spin = QDoubleSpinBox()
        self.start_freq_spin.setRange(0.01, 1_000_000.0)
        self.start_freq_spin.setValue(settings.get("default_start_freq", 100.0))
        self.start_freq_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.start_freq_spin, 0, 1)

        freq_layout.addWidget(QLabel("End frequency:"), 1, 0)
        self.end_freq_spin = QDoubleSpinBox()
        self.end_freq_spin.setRange(0.01, 1_000_000.0)
        self.end_freq_spin.setValue(settings.get("default_end_freq", 1000.0))
        self.end_freq_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.end_freq_spin, 1, 1)

        freq_layout.addWidget(QLabel("Step size:"), 2, 0)
        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.01, 1_000_000.0)
        self.step_spin.setValue(settings.get("default_step_size", 100.0))
        self.step_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.step_spin, 2, 1)

        freq_layout.addWidget(QLabel("Frames per frequency:"), 3, 0)
        self.n_averages_spin = QSpinBox()
        self.n_averages_spin.setRange(1, 1000)
        self.n_averages_spin.setValue(settings.get("default_n_averages", 5))
        freq_layout.addWidget(self.n_averages_spin, 3, 1)
        freq_group.setLayout(freq_layout)
        grid.addWidget(freq_group, 1, 0)

        # ---- Capture settings group (mirrors choose_sweep_params(), part 2) ----
        capture_group = QGroupBox("Capture settings")
        capture_layout = QGridLayout()
        capture_layout.addWidget(QLabel("Exposure (s):"), 0, 0)
        self.exposure_spin = QDoubleSpinBox()
        self.exposure_spin.setDecimals(4)
        self.exposure_spin.setRange(0.0001, 10.0)
        self.exposure_spin.setSingleStep(0.01)
        self.exposure_spin.setValue(settings.get("default_exposure", 0.01))
        capture_layout.addWidget(self.exposure_spin, 0, 1)

        capture_layout.addWidget(QLabel("Gain (dB):"), 1, 0)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setDecimals(2)
        self.gain_spin.setRange(-20.0, 50.0)  # 0 dB and negative values are valid
        self.gain_spin.setValue(settings.get("default_gain", 0.0))
        capture_layout.addWidget(self.gain_spin, 1, 1)

        capture_layout.addWidget(QLabel("gain_factor:"), 2, 0)
        self.gain_factor_spin = QDoubleSpinBox()
        self.gain_factor_spin.setDecimals(2)
        self.gain_factor_spin.setRange(0.01, 200.0)
        self.gain_factor_spin.setValue(settings.get("default_gain_factor", 1.0))
        capture_layout.addWidget(self.gain_factor_spin, 2, 1)

        capture_layout.addWidget(QLabel("Output folder:"), 3, 0)
        output_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit("output")
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(self.browse_button)
        capture_layout.addLayout(output_row, 3, 1)
        capture_group.setLayout(capture_layout)
        grid.addWidget(capture_group, 1, 1)

        outer.addLayout(grid)

        self.continue_button = QPushButton("Continue to Preview")
        self.continue_button.setObjectName("PrimaryButton")
        self.continue_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        )
        outer.addWidget(self.continue_button)

        self.setLayout(outer)

    def _browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.output_dir_edit.text()
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def camera_choice(self):
        for choice, radio in self._camera_radios.items():
            if radio.isChecked():
                return choice
        return None

    def mode_choice(self):
        for choice, radio in self._mode_radios.items():
            if radio.isChecked():
                return choice
        return None

    def get_params(self):
        """Returns the same shape dict choose_sweep_params() does."""
        return dict(
            start_freq=self.start_freq_spin.value(),
            end_freq=self.end_freq_spin.value(),
            step=self.step_spin.value(),
            n_averages=self.n_averages_spin.value(),
            exposure=self.exposure_spin.value(),
            gain=self.gain_spin.value(),
            gain_factor=self.gain_factor_spin.value(),
            output_dir=self.output_dir_edit.text(),
        )

    def reload_settings(self):
        """Reload settings from disk and update all UI controls."""
        settings = load_settings()
        
        # Update camera choice
        camera_choice = settings.get("default_camera_choice", "2")
        if camera_choice in self._camera_radios:
            self._camera_radios[camera_choice].setChecked(True)
        
        # Update mode (default to pair subtraction if not in settings)
        mode_choice = settings.get("default_mode_choice", "1")
        if mode_choice in self._mode_radios:
            self._mode_radios[mode_choice].setChecked(True)
        
        # Update frequency sweep parameters
        self.start_freq_spin.setValue(settings.get("default_start_freq", 100.0))
        self.end_freq_spin.setValue(settings.get("default_end_freq", 1000.0))
        self.step_spin.setValue(settings.get("default_step_size", 100.0))
        self.n_averages_spin.setValue(settings.get("default_n_averages", 5))
        
        # Update capture parameters
        self.exposure_spin.setValue(settings.get("default_exposure", 0.01))
        self.gain_spin.setValue(settings.get("default_gain", 0.0))
        self.gain_factor_spin.setValue(settings.get("default_gain_factor", 1.0))


# ==============================================================================
# PREVIEW WORKER + PAGE
# ==============================================================================

class CameraPreviewWorker(QThread):
    """
    Streams the live camera feed on a background thread, the same
    connect_camera() / grab_single_frame() / disconnect_camera() building
    blocks _show_preview_feed() uses, capped at ~15 fps so it never floods
    the Qt event loop with more frames than the UI can actually draw.
    """

    frame_ready = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    finished_cleanly = pyqtSignal()

    _FRAME_INTERVAL_MS = 66  # ~15 fps

    def __init__(
        self,
        camera_choice: str,
        exposure_s: float,
        gain: float,
        grayscale_method: str = "standard"
    ) -> None:
        """Initialize preview worker with validated parameters."""
        super().__init__()
        
        # Boundary validation: fail early with clear errors
        if camera_choice not in run_experiment.CAMERA_LIBRARY:
            raise ValueError(
                f"Invalid camera_choice: '{camera_choice}'. "
                f"Must be one of {list(run_experiment.CAMERA_LIBRARY.keys())}"
            )
        if exposure_s <= 0:
            raise ValueError(f"exposure_s must be > 0, got {exposure_s}")
        if grayscale_method not in ("standard", "single_channel"):
            raise ValueError(
                f"grayscale_method must be 'standard' or 'single_channel', "
                f"got '{grayscale_method}'"
            )
        
        self._camera_choice = camera_choice
        self._exposure_s = exposure_s
        self._gain = gain
        self._grayscale_method = grayscale_method
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        # Validate camera choice exists
        if self._camera_choice not in run_experiment.CAMERA_LIBRARY:
            self.error.emit(
                f"[ERROR] Invalid camera choice: '{self._camera_choice}'. "
                f"Available options: {list(run_experiment.CAMERA_LIBRARY.keys())}"
            )
            self.finished_cleanly.emit()
            return
        
        module_name = run_experiment.CAMERA_LIBRARY[self._camera_choice]
        
        # Validate module name
        if not isinstance(module_name, str) or not module_name:
            self.error.emit(
                f"[ERROR] Camera module name is invalid: {module_name}"
            )
            self.finished_cleanly.emit()
            return
        
        try:
            cam_lib = importlib.import_module(module_name)
        except ImportError as e:
            # Reuses _missing_sdk_message()'s exact wording instead of a
            # second, differently-worded copy of the same install
            # instructions — captured via redirect_stdout since that
            # function only knows how to print, not return a string.
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_experiment._missing_sdk_message(self._camera_choice, module_name, e)
            self.error.emit(buffer.getvalue().strip())
            self.finished_cleanly.emit()
            return
        
        # Validate module has all required functions
        required_functions = [
            'connect_camera', 'disconnect_camera', 'grab_single_frame',
            'set_exposure_manual', 'set_gain_manual'
        ]
        for func_name in required_functions:
            if not hasattr(cam_lib, func_name):
                self.error.emit(
                    f"[ERROR] Camera module '{module_name}' is missing function: '{func_name}'"
                )
                self.finished_cleanly.emit()
                return

        camera = None
        try:
            result = cam_lib.connect_camera(grayscale_method=self._grayscale_method)

            # Defensive validation: result must be a 2-element tuple
            if not isinstance(result, tuple):
                self.error.emit(
                    f"[ERROR] connect_camera returned invalid type: {type(result).__name__}, expected tuple"
                )
                return
            if len(result) != 2:
                self.error.emit(
                    f"[ERROR] connect_camera returned tuple with {len(result)} elements, expected 2"
                )
                return

            camera, format_info = result

            # Check for camera connection failure
            if camera is None:
                self.error.emit(
                    "Could not open the camera. Check it is plugged in and try again."
                )
                return

            # Camera 2 (USB/webcam) takes a log2 scale, not seconds — the
            # same conversion _show_preview_feed() applies.
            exposure_value = math.log2(self._exposure_s) if self._camera_choice == "2" \
                else self._exposure_s * 1_000_000
            cam_lib.set_exposure_manual(camera, exposure_value)
            cam_lib.set_gain_manual(camera, self._gain)

            while not self._stop:
                frame = cam_lib.grab_single_frame(camera)
                if frame is None:
                    self.error.emit("Failed to grab frame — check camera connection.")
                    break
                self.frame_ready.emit(frame)
                self.msleep(self._FRAME_INTERVAL_MS)
        except AttributeError as e:
            self.error.emit(f"[ERROR] Missing camera function: {e}")
        except RuntimeError as e:
            self.error.emit(f"[ERROR] Camera runtime error: {e}")
        except ValueError as e:
            self.error.emit(f"[ERROR] Invalid camera parameter: {e}")
        except Exception as e:
            self.error.emit(f"The preview stopped unexpectedly: {e}")
        finally:
            print(f"[PREVIEW_CLEANUP_START] camera is None: {camera is None}")
            if camera is not None:
                try:
                    print(f"[PREVIEW_CLEANUP] Calling disconnect_camera...")
                    cam_lib.disconnect_camera(camera)
                    print(f"[PREVIEW_CLEANUP] disconnect_camera succeeded")
                except AttributeError as e:
                    print(f"[PREVIEW_CLEANUP] AttributeError during disconnect: {e}")
                    self.error.emit(f"[ERROR] Failed to disconnect camera: {e}")
                except Exception as e:
                    print(f"[PREVIEW_CLEANUP] Exception during disconnect: {type(e).__name__}: {e}")
                    self.error.emit(f"[ERROR] Unexpected error during disconnect: {e}")
            else:
                print(f"[PREVIEW_CLEANUP] camera is None - not disconnecting")
            print(f"[PREVIEW_CLEANUP] Emitting finished_cleanly signal")
            self.finished_cleanly.emit()


class PreviewPage(QWidget):
    """
    Embedded live feed replacing _show_preview_feed()'s separate cv2
    window. "Lock in settings & continue" stops the worker and hands off
    to the Sweep stage, the same moment _run()'s terminal flow moves from
    the preview into reconfigure_if_needed().
    """

    continued = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._worker = None

        layout = QVBoxLayout()

        self.feed_label = QLabel("Camera preview will appear here once started.")
        self.feed_label.setObjectName("FeedFrame")
        self.feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feed_label.setMinimumSize(480, 360)
        layout.addWidget(self.feed_label, stretch=1)

        hint = QLabel(
            "Aim and focus the camera at the plate. These exposure and gain "
            "values are exactly what the sweep will use."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.continue_button = QPushButton("Lock in settings && continue")
        self.continue_button.setObjectName("PrimaryButton")
        self.continue_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.continue_button.clicked.connect(self._stop_and_continue)
        layout.addWidget(self.continue_button)

        self.setLayout(layout)

    def start_preview(self, camera_choice, exposure_s, gain, grayscale_method="standard"):
        self.feed_label.setText("Connecting to camera…")
        self._worker = CameraPreviewWorker(camera_choice, exposure_s, gain, grayscale_method)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.error.connect(self._on_error)
        self._worker.finished_cleanly.connect(self._on_finished)
        self._worker.start()

    def is_running(self):
        return self._worker is not None and self._worker.isRunning()

    def stop_and_wait(self):
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait()

    def hideEvent(self, event):
        # Safety net: leaving this page (nav click, programmatic page
        # switch) must never leave the camera connected in the background,
        # even if the user never clicked "Lock in settings & continue".
        self.stop_and_wait()
        super().hideEvent(event)

    def _stop_and_continue(self):
        self.stop_and_wait()
        self.continued.emit()

    def _on_frame(self, frame):
        pixmap = _frame_to_pixmap(frame).scaled(
            self.feed_label.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        self.feed_label.setPixmap(pixmap)

    def _on_error(self, message):
        QMessageBox.warning(self, "Preview error", message)

    def _on_finished(self):
        self._worker = None


# ==============================================================================
# SWEEP WORKER + PAGE
# ==============================================================================

@contextlib.contextmanager
def _suppress_cv2_windows():
    """
    complete_pipeline*.py's sweep loops call cv2.imshow()/cv2.waitKey()
    unconditionally on every frequency step — once during each
    frequency's settling period (a live "watch the plate settle" feed)
    and again to show that frequency's just-computed result. This is
    intentional, useful terminal-mode behavior and skip_live_feed does
    NOT gate it (skip_live_feed only skips the earlier, one-time "aim the
    camera" step) — so it is not a bug in complete_pipeline*.py, only a
    genuine incompatibility with running the sweep on a background
    thread here.

    Calling HighGUI window functions off the main thread is unsafe —
    on macOS in particular it reliably crashes with an opaque "Unknown
    C++ exception from OpenCV code" instead of a clear error, which is
    exactly what happens if SweepWorker runs a sweep without this. Since
    the whole point of this dashboard is to embed everything and never
    pop up a separate window, and since complete_pipeline*.py's tested
    sweep logic is deliberately left untouched everywhere else in this
    project, these two functions are stubbed out for the duration of the
    sweep instead of being changed at the source — the same "compose,
    don't modify" approach already used for progress via stdout
    redirection below. cv2.waitKey's stub returns -1 (its own "no key
    was pressed" sentinel) since nothing in the sweep loop checks that
    return value for anything but a keypress that will now never come.
    """
    original_imshow = cv2.imshow
    original_waitkey = cv2.waitKey
    cv2.imshow = lambda *args, **kwargs: None
    cv2.waitKey = lambda *args, **kwargs: -1
    try:
        yield
    finally:
        cv2.imshow = original_imshow
        cv2.waitKey = original_waitkey


class SweepWorker(QThread):
    """
    Runs run_pipeline() on a background thread with stdout redirected into
    an EmittingStream, so the sweep's own print() calls both drive the
    progress bar and fill the log console live — without run_pipeline() or
    any complete_pipeline*.py file needing to know a GUI exists.

    STOPPING: stop() sets a cooperative flag that run_pipeline() (via its
    stop_check parameter) checks once per frequency, before any signal
    generator or camera command for that frequency is issued — see
    complete_pipeline.py's frequency_sweep() docstring for the full
    explanation of why that specific point is safe. This is the same shape
    as monitor_gui.py's MonitorWorker checking a stop flag every frame, just
    checked once per frequency here instead of once per frame, since a
    frequency step (settle + several frame grabs) can't safely be
    interrupted partway through the way a single frame grab can.
    QThread.terminate() is still never used — it could stop mid frame-grab
    or mid signal-generator command and leave hardware connections open.

    CAVEAT: contextlib.redirect_stdout replaces the process-wide
    sys.stdout for as long as this runs, not just this thread's — safe
    here because nothing else in this single-purpose app prints
    concurrently while a sweep is running (the whole nav rail, including
    the Preview page's own camera thread, is locked out during a sweep).
    The same is true of _suppress_cv2_windows()'s process-wide cv2 patch.
    """

    progress = pyqtSignal(int, int, float)  # (current_index, total_steps, freq_hz)
    finished_sweep = pyqtSignal(object)     # results dict, or None on failure

    # Basler's complete_pipeline.py prints "--- Sweeping frequency: X Hz ---"
    # with no index of its own; complete_pipeline_inclusive.py and
    # complete_pipeline_allied_vision.py instead print "[i/N]  X Hz  ..."
    # with the index and total already built in. Matching both formats is
    # what lets one progress bar work correctly for all three cameras.
    _INDEXED_RE = re.compile(r"^\[(\d+)/(\d+)\]\s+([\d.]+)\s*Hz")
    _BASLER_RE = re.compile(r"--- Sweeping frequency: ([\d.]+) Hz ---")

    error = pyqtSignal(str)

    def __init__(self, camera_choice, mode_choice, params, stream):
        super().__init__()
        self._camera_choice = camera_choice
        self._mode_choice = mode_choice
        self._params = params
        self._stream = stream
        self._basler_index = 0
        self._total_steps = _total_sweep_steps(params)
        self._stream.text_written.connect(self._handle_line)
        self._stop_requested = False

    def stop(self):
        """
        Cooperative stop: just sets a flag. The sweep itself (via
        stop_check below) decides when it is safe to actually notice it —
        between frequencies, never mid-measurement.
        """
        self._stop_requested = True

    def _is_stop_requested(self):
        return self._stop_requested

    def _handle_line(self, line):
        match = self._INDEXED_RE.match(line)
        if match:
            self.progress.emit(int(match.group(1)), int(match.group(2)), float(match.group(3)))
            return
        match = self._BASLER_RE.search(line)
        if match:
            self._basler_index += 1
            self.progress.emit(self._basler_index, self._total_steps, float(match.group(1)))

    def run(self):
        results = None
        try:
            with _suppress_cv2_windows(), contextlib.redirect_stdout(self._stream):
                results = run_experiment.run_pipeline(
                    self._camera_choice, self._mode_choice, self._params,
                    stop_check=self._is_stop_requested,
                )
        except Exception as e:
            self.error.emit(f"The experiment stopped unexpectedly: {e}")
        finally:
            self.finished_sweep.emit(results)


class LiveMonitoringWorker(QThread):
    """
    Captures and displays live monitoring windows during sweep if enabled.
    Shows: (1) Live feed, (2) Captured frame, (3) Difference image, (4) Averaged result.
    """
    
    frame_update = pyqtSignal(dict)  # {'live': frame, 'captured': frame, 'diff': frame, 'avg': frame}
    error = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(
        self,
        camera_choice: str,
        exposure_s: float,
        gain: float,
        grayscale_method: str
    ) -> None:
        """Initialize monitoring worker with validated parameters."""
        super().__init__()
        
        # Boundary validation
        if camera_choice not in run_experiment.CAMERA_LIBRARY:
            raise ValueError(
                f"Invalid camera_choice: '{camera_choice}'. "
                f"Must be one of {list(run_experiment.CAMERA_LIBRARY.keys())}"
            )
        if exposure_s <= 0:
            raise ValueError(f"exposure_s must be > 0, got {exposure_s}")
        if grayscale_method not in ("standard", "single_channel"):
            raise ValueError(
                f"grayscale_method must be 'standard' or 'single_channel', "
                f"got '{grayscale_method}'"
            )
        
        self._camera_choice = camera_choice
        self._exposure_s = exposure_s
        self._gain = gain
        self._grayscale_method = grayscale_method
        self._stop = False
        self._last_frame = None
        self._reference_frame = None
    
    def stop(self):
        self._stop = True
    
    def set_reference_frame(self, frame):
        self._reference_frame = frame
    
    def run(self):
        module_name = run_experiment.CAMERA_LIBRARY[self._camera_choice]
        try:
            cam_lib = importlib.import_module(module_name)
        except ImportError as e:
            self.error.emit(f"Could not load camera module: {e}")
            self.finished.emit()
            return
        
        camera = None
        try:
            result = cam_lib.connect_camera(grayscale_method=self._grayscale_method)
            
            # Defensive: validate return type before unpacking
            if not isinstance(result, tuple):
                self.error.emit(
                    f"[ERROR] Camera module returned invalid type: {type(result).__name__}. "
                    f"Expected tuple (camera, format_info)."
                )
                self.finished.emit()
                return
            
            if len(result) != 2:
                self.error.emit(
                    f"[ERROR] Camera module returned tuple with {len(result)} elements. "
                    f"Expected 2 (camera, format_info)."
                )
                self.finished.emit()
                return
            
            camera, format_info = result
            
            # Single check: camera is None
            if camera is None:
                self.error.emit(
                    "Could not connect to camera for live monitoring. "
                    "Check camera is plugged in and not in use by another application."
                )
                self.finished.emit()
                return
            
            exposure_value = math.log2(self._exposure_s) if self._camera_choice == "2" else self._exposure_s * 1_000_000
            cam_lib.set_exposure_manual(camera, exposure_value)
            cam_lib.set_gain_manual(camera, self._gain)
            
            while not self._stop:
                frame = cam_lib.grab_single_frame(camera)
                if frame is None:
                    continue
                
                self._last_frame = frame
                
                # Compute difference if we have a reference
                diff_frame = None
                if self._reference_frame is not None:
                    diff_frame = cv2.absdiff(frame, self._reference_frame)
                
                # Emit all frames (some may be None)
                self.frame_update.emit({
                    'live': frame,
                    'captured': frame,
                    'diff': diff_frame,
                    'avg': frame
                })
                
                self.msleep(66)  # ~15 fps
        except AttributeError as e:
            self.error.emit(
                f"[ERROR] Camera object missing method: {e}. "
                f"This may indicate wrong camera type or SDK not installed."
            )
        except RuntimeError as e:
            self.error.emit(f"[HARDWARE] Camera error: {e}")
        except ValueError as e:
            self.error.emit(f"[PARAM] Invalid parameter: {e}")
        except Exception as e:
            self.error.emit(f"[UNEXPECTED] Monitoring stopped: {e}")
        finally:
            if camera is not None:
                try:
                    cam_lib.disconnect_camera(camera)
                except AttributeError as e:
                    print(f"[WARNING] Failed to disconnect camera: {e}")
                except Exception as e:
                    print(f"[ERROR] Unexpected error during disconnect: {e}")
            
            self.finished.emit()

class SweepPage(QWidget):
    """
    A determinate progress bar plus a "Frequency i of N" label, driven
    entirely by SweepWorker's parsed stdout. The log_line signal bubbles
    every raw line up to MainWindow's shared log console.
    """

    log_line = pyqtSignal(str)
    sweep_started = pyqtSignal()
    sweep_finished = pyqtSignal(object, str)  # (results, output_dir)

    _MODE_NAMES = {"1": "Pair subtraction", "2": "Reference subtraction"}

    def __init__(self):
        super().__init__()
        self._worker = None
        self._monitoring_worker = None
        self._camera_choice = None
        self._mode_choice = None
        self._params = None
        self._user_stopped = False
        self._show_live_monitoring = False

        outer = QVBoxLayout()

        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()
        self.summary_label = QLabel(
            "Complete the Setup and Preview stages to see a summary here."
        )
        self.summary_label.setObjectName("SummaryLabel")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        summary_group.setLayout(summary_layout)
        outer.addWidget(summary_group)

        progress_group = QGroupBox("Sweep progress")
        progress_layout = QVBoxLayout()

        self.freq_label = QLabel("Ready to start the sweep.")
        self.freq_label.setObjectName("FreqLabel")
        progress_layout.addWidget(self.freq_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        progress_layout.addWidget(self.progress_bar)

        self.start_button = QPushButton("Start Sweep")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.start_button.clicked.connect(self._start_sweep)
        progress_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Sweep")
        self.stop_button.clicked.connect(self._confirm_stop)
        self.stop_button.setVisible(False)
        progress_layout.addWidget(self.stop_button)

        warning = QLabel(
            "Stopping finishes measuring the current frequency first, then "
            "stops safely — it never interrupts hardware mid-measurement. "
            "Do not unplug any cables while the sweep is running."
        )
        warning.setWordWrap(True)
        warning.setObjectName("WarningLabel")
        progress_layout.addWidget(warning)

        progress_group.setLayout(progress_layout)
        outer.addWidget(progress_group)

        # Live monitoring group (shown if enabled in settings)
        monitoring_group = QGroupBox("Live Monitoring")
        monitoring_layout = QGridLayout()
        
        self._live_label = QLabel("Live Feed")
        self._live_label.setObjectName("MonitoringLabel")
        self._live_display = QLabel()
        self._live_display.setMinimumSize(160, 120)
        self._live_display.setObjectName("MonitoringDisplay")
        monitoring_layout.addWidget(self._live_label, 0, 0)
        monitoring_layout.addWidget(self._live_display, 1, 0)
        
        self._captured_label = QLabel("Captured Frame")
        self._captured_label.setObjectName("MonitoringLabel")
        self._captured_display = QLabel()
        self._captured_display.setMinimumSize(160, 120)
        self._captured_display.setObjectName("MonitoringDisplay")
        monitoring_layout.addWidget(self._captured_label, 0, 1)
        monitoring_layout.addWidget(self._captured_display, 1, 1)
        
        self._diff_label = QLabel("Difference")
        self._diff_label.setObjectName("MonitoringLabel")
        self._diff_display = QLabel()
        self._diff_display.setMinimumSize(160, 120)
        self._diff_display.setObjectName("MonitoringDisplay")
        monitoring_layout.addWidget(self._diff_label, 0, 2)
        monitoring_layout.addWidget(self._diff_display, 1, 2)
        
        self._avg_label = QLabel("Averaged Result")
        self._avg_label.setObjectName("MonitoringLabel")
        self._avg_display = QLabel()
        self._avg_display.setMinimumSize(160, 120)
        self._avg_display.setObjectName("MonitoringDisplay")
        monitoring_layout.addWidget(self._avg_label, 0, 3)
        monitoring_layout.addWidget(self._avg_display, 1, 3)
        
        monitoring_group.setLayout(monitoring_layout)
        monitoring_group.setVisible(False)  # Hidden until sweep starts with monitoring enabled
        self._monitoring_group = monitoring_group
        outer.addWidget(monitoring_group)

        outer.addStretch()
        self.setLayout(outer)

    def begin(self, camera_choice, mode_choice, params):
        """Called by MainWindow once the Preview stage hands off."""
        self._camera_choice = camera_choice
        self._mode_choice = mode_choice
        self._params = params
        self._user_stopped = False

        total = _total_sweep_steps(params)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.freq_label.setText(f"Ready to start the sweep. (0 / {total} frequencies)")
        self.start_button.setEnabled(True)
        self.stop_button.setVisible(False)

        self.summary_label.setText(
            f"Camera        :  {run_experiment.CAMERA_NAMES[camera_choice]}\n"
            f"Mode          :  {self._MODE_NAMES[mode_choice]}\n"
            f"Frequency     :  {params['start_freq']:g} – {params['end_freq']:g} Hz "
            f"(step {params['step']:g} Hz)\n"
            f"Frames/freq   :  {params['n_averages']}\n"
            f"Exposure      :  {params['exposure']} s\n"
            f"Gain          :  {params['gain']} dB\n"
            f"gain_factor   :  {params['gain_factor']}\n"
            f"Output folder :  {params['output_dir']}"
        )

    def is_running(self):
        return self._worker is not None and self._worker.isRunning()

    def stop_and_wait(self):
        """Used by MainWindow.closeEvent() once the user confirms stopping."""
        if self._monitoring_worker is not None:
            self._monitoring_worker.stop()
            self._monitoring_worker.wait()
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait()

    def _start_sweep(self):
        self.start_button.setEnabled(False)
        self.stop_button.setVisible(True)
        self.stop_button.setEnabled(True)
        self.sweep_started.emit()

        # Note: Live monitoring disabled for now because it requires a separate camera connection,
        # which conflicts with SweepWorker holding the camera exclusively.
        # TODO: Future enhancement - support dual-camera setups or display-only monitoring
        self._monitoring_group.setVisible(False)

        stream = EmittingStream()
        stream.text_written.connect(self.log_line)

        self._worker = SweepWorker(self._camera_choice, self._mode_choice, self._params, stream)
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished_sweep.connect(self._on_finished)
        self._worker.start()

    def _confirm_stop(self):
        reply = QMessageBox.question(
            self,
            "Stop sweep",
            "Stop the sweep? It will finish measuring the current frequency, "
            "then stop safely. Frequencies not yet measured will be skipped, "
            "but everything collected so far will still be saved and shown.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._user_stopped = True
        self.stop_button.setEnabled(False)
        self.freq_label.setText(self.freq_label.text() + "  (stopping after this frequency…)")
        if self._worker is not None:
            self._worker.stop()

    def _on_progress(self, current, total, freq):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.freq_label.setText(f"Sweeping frequency {current} of {total} — {freq:g} Hz")

    def _on_error(self, message):
        QMessageBox.critical(self, "Sweep error", message)

    def _on_finished(self, results):
        if self._monitoring_worker is not None:
            self._monitoring_worker.stop()
            self._monitoring_worker.wait()
            self._monitoring_worker = None
        self._monitoring_group.setVisible(False)
        self._worker = None
        self.stop_button.setVisible(False)
        self.start_button.setEnabled(True)
        if results and self._user_stopped:
            self.freq_label.setText(f"Sweep stopped — {len(results)} frequencies measured.")
        elif results:
            self.freq_label.setText(f"Sweep complete — {len(results)} frequencies measured.")
        else:
            self.freq_label.setText("Sweep finished with no results — check the log below.")
        output_dir = self._params["output_dir"] if self._params else ""
        self.sweep_finished.emit(results, output_dir)

    def _on_monitor_frames(self, frames):
        """Update the monitoring displays with new frames."""
        for key, display_widget in [
            ('live', self._live_display),
            ('captured', self._captured_display),
            ('diff', self._diff_display),
            ('avg', self._avg_display)
        ]:
            frame = frames.get(key)
            if frame is not None:
                pixmap = _frame_to_pixmap(frame)
                if pixmap.width() > 0:
                    scaled = pixmap.scaledToWidth(160, Qt.TransformationMode.SmoothTransformation)
                    display_widget.setPixmap(scaled)
    
    def _on_monitor_error(self, error_msg):
        """Handle monitoring errors."""
        print(f"Live monitoring error: {error_msg}")


# ==============================================================================
# RESULTS PAGE
# ==============================================================================

class ResultsPage(QWidget):
    """
    Embeds build_grid_figure()'s Figure directly (default view), plus a
    second, GUI-owned single-image view with Prev/Next paging — a separate
    canvas rather than reusing show_results()'s
    fig.canvas.mpl_connect("key_press_event", ...) viewer, since that
    relies on matplotlib's own blocking plt.show() event loop, which would
    conflict with Qt's event loop already running here.
    """

    run_again = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._results = None
        self._output_dir = None
        self._freqs = []
        self._fmt = lambda f: f"{f:g}"
        self._single_index = 0

        self._layout = QVBoxLayout()

        # Both canvases live inside their own "card" container (matching
        # the QGroupBox card styling used everywhere else in this app),
        # since a bare FigureCanvasQTAgg paints its entire own rect and
        # would otherwise ignore a border/background applied directly to
        # it.
        self._grid_card, self._grid_canvas = self._make_canvas_card()
        self._layout.addWidget(self._grid_card, stretch=1)

        self._single_card, self._single_canvas = self._make_canvas_card()
        self._single_ax = self._single_canvas.figure.add_subplot(111)
        self._single_card.setVisible(False)
        self._layout.addWidget(self._single_card, stretch=1)

        nav_row = QHBoxLayout()
        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self._show_previous)
        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self._show_next)
        self.prev_button.setVisible(False)
        self.next_button.setVisible(False)
        nav_row.addWidget(self.prev_button)
        nav_row.addWidget(self.next_button)
        self._layout.addLayout(nav_row)

        button_row = QHBoxLayout()
        self.toggle_view_button = QPushButton("Switch to single-image view")
        self.toggle_view_button.clicked.connect(self._toggle_view)
        self.open_folder_button = QPushButton("Open output folder")
        self.open_folder_button.clicked.connect(self._open_folder)
        self.run_again_button = QPushButton("Run another sweep")
        self.run_again_button.setObjectName("PrimaryButton")
        self.run_again_button.clicked.connect(self.run_again.emit)
        button_row.addWidget(self.toggle_view_button)
        button_row.addWidget(self.open_folder_button)
        button_row.addWidget(self.run_again_button)
        self._layout.addLayout(button_row)

        self.setLayout(self._layout)

        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=self._show_previous)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=self._show_next)

    @staticmethod
    def _make_canvas_card(figure=None):
        """Build one 'card' container (matching this app's QGroupBox
        styling) holding a single FigureCanvasQTAgg, and return both."""
        card = QWidget()
        card.setObjectName("CanvasCard")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(12, 12, 12, 12)
        canvas = FigureCanvasQTAgg(figure if figure is not None else Figure(figsize=(6, 6)))
        card_layout.addWidget(canvas)
        card.setLayout(card_layout)
        return card, canvas

    def show_results(self, results, output_dir):
        self._results = results
        self._output_dir = output_dir
        self._freqs = sorted(results.keys())
        self._fmt = run_experiment._format_freq_label(self._freqs)
        self._single_index = 0

        grid_fig, _ = run_experiment.build_grid_figure(results, output_dir)
        new_canvas = FigureCanvasQTAgg(grid_fig)
        self._grid_card.layout().replaceWidget(self._grid_canvas, new_canvas)
        # replaceWidget() does not automatically show its replacement the
        # way adding a widget to an already-visible layout normally does.
        new_canvas.setVisible(True)
        self._grid_canvas.deleteLater()
        self._grid_canvas = new_canvas
        self._grid_card.setVisible(not self._single_card.isVisible())

        self._draw_single(0)
        self.prev_button.setVisible(True)
        self.next_button.setVisible(True)

    def _draw_single(self, index):
        if not self._freqs:
            return
        self._single_index = index
        freq = self._freqs[index]
        ax = self._single_ax
        ax.clear()
        ax.imshow(self._results[freq], cmap="gray", interpolation="nearest")
        ax.set_title(f"{self._fmt(freq)} Hz   ({index + 1} / {len(self._freqs)})")
        ax.axis("off")
        self._single_canvas.draw_idle()

    def _show_previous(self):
        if not self.isVisible() or not self._freqs:
            return
        self._draw_single(max(0, self._single_index - 1))

    def _show_next(self):
        if not self.isVisible() or not self._freqs:
            return
        self._draw_single(min(len(self._freqs) - 1, self._single_index + 1))

    def _toggle_view(self):
        grid_was_visible = self._grid_card.isVisible()
        self._grid_card.setVisible(not grid_was_visible)
        self._single_card.setVisible(grid_was_visible)
        self.toggle_view_button.setText(
            "Switch to grid view" if grid_was_visible else "Switch to single-image view"
        )

    def _open_folder(self):
        if self._output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(self._output_dir)))


# ==============================================================================
# MAIN WINDOW
# ==============================================================================

class MainWindow(QMainWindow):
    """
    Left nav rail (Setup, Preview, Sweep, Results) + QStackedWidget, the
    same shell shape as monitor_gui.py's dashboard, kept for visual and
    architectural consistency between the two apps in this project.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESPI Plate Vibration — Run Experiment")
        self.resize(1150, 820)

        # Brand header with sidebar
        nav_widget = QWidget()
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(0)

        # Brand header: icon + "ESPI Scan Mode"
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 6, 6, 18)
        header_layout.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setPixmap(qta.icon('mdi6.radar', color=QColor("#e0e0e0")).pixmap(22, 22))
        brand_title = QLabel("ESPI Scan Mode")
        brand_title.setObjectName("BrandTitle")
        header_layout.addWidget(brand_icon)
        header_layout.addWidget(brand_title)
        header_layout.addStretch()
        nav_layout.addLayout(header_layout)

        # Navigation items with icons
        self._nav = QListWidget()
        self._nav.setObjectName("NavRail")
        self._nav.setIconSize(QSize(18, 18))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.tune-variant', color=QColor("#e0e0e0")), "Setup"
        ))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.eye-outline', color=QColor("#e0e0e0")), "Preview"
        ))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.radar', color=QColor("#e0e0e0")), "Sweep"
        ))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.chart-line', color=QColor("#e0e0e0")), "Results"
        ))
        self._nav.addItem(QListWidgetItem(
            qta.icon('mdi6.cog-outline', color=QColor("#e0e0e0")), "Settings"
        ))
        self._nav.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        nav_layout.addWidget(self._nav)

        nav_widget.setLayout(nav_layout)
        
        self._nav.setFixedWidth(180)
        self._nav.setCurrentRow(0)
        for row in (1, 2, 3, 4):
            self._set_nav_enabled(row, False)
        # Settings is always available
        self._set_nav_enabled(4, True)
        self._nav.currentRowChanged.connect(self._on_nav_changed)

        self.setup_page = SetupPage()
        self.preview_page = PreviewPage()
        self.sweep_page = SweepPage()
        self.results_page = ResultsPage()
        self.settings_page = SettingsPage()

        self._stack = QStackedWidget()
        self._stack.addWidget(self.setup_page)
        self._stack.addWidget(self.preview_page)
        self._stack.addWidget(self.sweep_page)
        self._stack.addWidget(self.results_page)
        self._stack.addWidget(self.settings_page)

        self.log_console = QPlainTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(2000)
        self.log_console.setFixedHeight(140)
        self.log_console.setPlaceholderText(
            "Sweep progress will be logged here once it starts…"
        )

        right_side = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.addWidget(self._stack, stretch=1)
        right_layout.addWidget(self.log_console)
        right_side.setLayout(right_layout)

        central = QWidget()
        central_layout = QHBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(nav_widget)
        central_layout.addWidget(right_side, stretch=1)
        central.setLayout(central_layout)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Idle")

        self.setup_page.continue_button.clicked.connect(self._start_preview)
        self.preview_page.continued.connect(self._start_sweep_stage)
        self.sweep_page.log_line.connect(self.log_console.appendPlainText)
        self.sweep_page.sweep_started.connect(self._on_sweep_started)
        self.sweep_page.sweep_finished.connect(self._on_sweep_finished)
        self.results_page.run_again.connect(self._on_run_again)

        # Elevation: every card-style surface gets a real drop shadow (see
        # _apply_card_shadow()'s docstring for why this can't just live in
        # the QSS string above). The two ResultsPage canvas cards keep
        # this same shadow-carrying container instance even after
        # show_results() swaps the FigureCanvasQTAgg inside them.
        for card in self.findChildren(QGroupBox):
            _apply_card_shadow(card)
        for card in self.findChildren(QWidget, "CanvasCard"):
            _apply_card_shadow(card)

    def _set_nav_enabled(self, row, enabled):
        item = self._nav.item(row)
        if enabled:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _on_nav_changed(self, row):
        self._stack.setCurrentIndex(row)
        # Reload settings when returning to Setup page
        if row == 0:
            self.setup_page.reload_settings()

    def _start_preview(self):
        params = self.setup_page.get_params()
        camera_choice = self.setup_page.camera_choice()
        grayscale_method = load_settings().get("grayscale_method", "standard")
        
        # Save current settings before proceeding
        current_settings = load_settings()
        current_settings.update({
            "default_camera_choice": camera_choice,
            "default_start_freq": params["start_freq"],
            "default_end_freq": params["end_freq"],
            "default_step_size": params["step"],
            "default_n_averages": params["n_averages"],
            "default_exposure": params["exposure"],
            "default_gain": params["gain"],
            "default_gain_factor": params["gain_factor"],
            "grayscale_method": grayscale_method,
        })
        save_settings(current_settings)
        
        self._set_nav_enabled(1, True)
        self._nav.setCurrentRow(1)
        self.statusBar().showMessage("Previewing camera feed")
        self.preview_page.start_preview(camera_choice, params["exposure"], params["gain"], grayscale_method)

    def _start_sweep_stage(self):
        camera_choice = self.setup_page.camera_choice()
        mode_choice = self.setup_page.mode_choice()
        params = self.setup_page.get_params()
        
        # Save current settings before proceeding
        current_settings = load_settings()
        current_settings.update({
            "default_camera_choice": camera_choice,
            "default_start_freq": params["start_freq"],
            "default_end_freq": params["end_freq"],
            "default_step_size": params["step"],
            "default_n_averages": params["n_averages"],
            "default_exposure": params["exposure"],
            "default_gain": params["gain"],
            "default_gain_factor": params["gain_factor"],
        })
        save_settings(current_settings)
        
        self.sweep_page.begin(camera_choice, mode_choice, params)
        self._set_nav_enabled(2, True)
        self._nav.setCurrentRow(2)
        self.statusBar().showMessage("Ready to sweep")

    def _on_sweep_started(self):
        for row in range(4):
            self._set_nav_enabled(row, False)
        self.statusBar().showMessage("Running sweep — do not unplug any cables")

    def _on_sweep_finished(self, results, output_dir):
        self._set_nav_enabled(0, True)
        self._set_nav_enabled(1, True)
        self._set_nav_enabled(2, True)
        if results:
            self._set_nav_enabled(3, True)
            self.results_page.show_results(results, output_dir)
            self._nav.setCurrentRow(3)
            self.statusBar().showMessage(f"Done — {len(results)} frequencies measured")
        else:
            self.statusBar().showMessage("Sweep finished with no results — check the log below")

    def _on_run_again(self):
        # Reload settings from disk when returning to setup
        self.setup_page.reload_settings()
        self._set_nav_enabled(1, False)
        self._set_nav_enabled(2, False)
        self._set_nav_enabled(3, False)
        self._nav.setCurrentRow(0)
        self.statusBar().showMessage("Idle")

    def closeEvent(self, event):
        if self.sweep_page.is_running():
            # Same confirm-then-stop-and-wait pattern as the preview below,
            # now that SweepWorker has a safe stop mechanism (see its
            # docstring) — stopping still waits for the current frequency
            # to finish measuring before the thread actually exits.
            reply = QMessageBox.question(
                self,
                "Sweep running",
                "The sweep is still running. Stop it and close? It will finish "
                "measuring the current frequency first, then stop safely.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.sweep_page.stop_and_wait()

        if self.preview_page.is_running():
            reply = QMessageBox.question(
                self,
                "Preview running",
                "The camera preview is still running. Stop it and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.preview_page.stop_and_wait()

        event.accept()


# ==============================================================================
# STYLESHEET
# ==============================================================================
# A dark, strictly monochrome theme (no color accents at all — off-blacks
# and grays only) applied to the whole QApplication. "Elevated" surfaces
# (QGroupBox cards, the results canvases, the nav rail's selected row) use
# a lighter gray than the base background plus a real drop shadow (added
# separately below via QGraphicsDropShadowEffect, since QSS itself has no
# box-shadow) so cards read as floating panels rather than flat rectangles.
# Primary actions and the progress bar use a near-white fill instead of a
# color accent — the only way to signal "emphasis" without introducing a
# hue. Kept as one embedded string (not a separate .qss file) so the app
# has no extra non-Python asset to ship.

_BASE_BG = "#1e1e1e"
_SURFACE_BG = "#292929"
_BORDER = "#383838"
_TEXT_SECONDARY = "#8a8a8a"
_TEXT_PRIMARY = "#e0e0e0"

_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {_BASE_BG};
    color: {_TEXT_PRIMARY};
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QListWidget#NavRail {{
    background-color: #171717;
    border: none;
    border-right: 1px solid {_BORDER};
    padding: 12px 0px;
    outline: 0;
}}
QListWidget#NavRail::item {{
    color: {_TEXT_SECONDARY};
    padding: 14px 22px;
    border-left: 3px solid transparent;
}}
QListWidget#NavRail::item:selected {{
    background-color: {_SURFACE_BG};
    color: {_TEXT_PRIMARY};
    border-left: 3px solid {_TEXT_PRIMARY};
}}
QListWidget#NavRail::item:disabled {{
    color: #4a4a4a;
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
QLabel#FreqLabel {{ font-weight: 600; font-size: 14px; }}
QLabel#WarningLabel {{
    color: {_TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 600;
    background-color: {_SURFACE_BG};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 10px;
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

QLabel#SummaryLabel {{
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
    background-color: #232323;
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 12px;
}}

QWidget#CanvasCard {{
    background-color: {_SURFACE_BG};
    border: 1px solid {_BORDER};
    border-radius: 12px;
}}

QProgressBar {{
    border: 1px solid {_BORDER};
    border-radius: 8px;
    background-color: #232323;
    text-align: center;
    height: 22px;
    font-weight: 600;
    color: {_TEXT_PRIMARY};
}}
QProgressBar::chunk {{
    background-color: {_TEXT_PRIMARY};
    border-radius: 7px;
}}

QPlainTextEdit#LogConsole {{
    background-color: #141414;
    color: #cfcfcf;
    border: 1px solid {_BORDER};
    border-radius: 10px;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
    padding: 12px;
}}

QStatusBar {{
    background-color: {_BASE_BG};
    border-top: 1px solid {_BORDER};
    color: {_TEXT_SECONDARY};
}}

QLabel#FeedFrame {{
    background-color: #141414;
    border: 1px solid {_BORDER};
    border-radius: 12px;
    color: {_TEXT_SECONDARY};
    font-size: 13px;
}}
"""


def _apply_card_shadow(widget, blur_radius=28, y_offset=6, alpha=140):
    """
    QSS has no box-shadow — this is the actual mechanism Qt offers for the
    same "elevated card floating above the background" effect, applied
    directly to a widget (a QGroupBox, or a results-page CanvasCard)
    rather than expressed in the stylesheet string above.
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
