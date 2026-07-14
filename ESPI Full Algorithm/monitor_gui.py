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

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
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
# run_experiment.py already dispatches to as _CAMERA_LIBRARY.

_CAMERA_CONTROL_MODULES = {
    "1": "camera_control",
    "2": "camera_control_inclusive",
    "3": "camera_control_allied_vision",
}


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
        settings_group = QGroupBox("Settings")
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
        self.gain_factor_spin.setValue(20.0)
        settings_layout.addWidget(self.gain_factor_spin)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # ---- Graph group (mirrors monitor.choose_graph_type()) ----
        graph_group = QGroupBox("Intensity graph")
        graph_layout = QVBoxLayout()

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
            graph_layout.addWidget(radio)
        self._graph_radios["4"].setChecked(True)  # same default as choose_graph_type()

        graph_group.setLayout(graph_layout)
        layout.addWidget(graph_group)

        # ---- Live summary + start button ----
        self._summary_label = QLabel()
        layout.addWidget(self._summary_label)

        self.start_button = QPushButton("Start Monitor")
        layout.addWidget(self.start_button)
        layout.addStretch()
        self.setLayout(layout)

        # Wire every input that can change the summary to _update_summary().
        # Connected after all the widgets above exist and after each
        # group's own default has already been set, so this never fires
        # against not-yet-created widgets.
        for radio in self._radios.values():
            radio.toggled.connect(self._update_summary)
        for radio in self._graph_radios.values():
            radio.toggled.connect(self._update_summary)
        self._index_spin.valueChanged.connect(self._update_summary)
        self.exposure_spin.valueChanged.connect(self._update_summary)
        self.gain_spin.valueChanged.connect(self._update_summary)
        self.gain_factor_spin.valueChanged.connect(self._update_summary)

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
            f"Graph         :  {settings['graph_type']}"
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
    error = pyqtSignal(str)
    finished_cleanly = pyqtSignal()

    def __init__(self, camera_choice, camera_index, settings):
        super().__init__()
        self._camera_choice = camera_choice
        self._camera_index = camera_index
        self._settings = settings
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
            # Camera 2 (USB/webcam) takes a log2 scale, not seconds — the
            # same conversion monitor.launch_monitor() applies.
            exposure_value = math.log2(exposure_s) if self._camera_choice == "2" \
                else exposure_s * 1_000_000
            cam_lib.set_exposure_manual(camera, exposure_value)
            cam_lib.set_gain_manual(camera, self._settings["gain_db"])

            gain_factor = self._settings["gain_factor"]
            prev_frame = None

            while not self._stop:
                frame = cam_lib.grab_single_frame(camera)
                if frame is None:
                    self.error.emit("Failed to grab frame — check camera connection.")
                    break

                diff = None
                if prev_frame is not None:
                    raw_diff = cam_lib.substract_frames(prev_frame, frame)
                    diff = cv2.convertScaleAbs(raw_diff, alpha=gain_factor)
                prev_frame = frame

                self.frame_ready.emit(frame, diff)
        except Exception as e:
            self.error.emit(f"The monitor stopped unexpectedly: {e}")
        finally:
            if camera is not None:
                cam_lib.disconnect_camera(camera)
            self.finished_cleanly.emit()


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

        layout = QVBoxLayout()

        feeds_layout = QHBoxLayout()
        self.live_feed_label = QLabel("Live Feed")
        self.live_feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_feed_label.setMinimumSize(320, 240)
        self.live_feed_label.setStyleSheet("border: 1px solid palette(mid);")
        self.diff_label = QLabel("Frame Subtraction")
        self.diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.diff_label.setMinimumSize(320, 240)
        self.diff_label.setStyleSheet("border: 1px solid palette(mid);")
        feeds_layout.addWidget(self.live_feed_label)
        feeds_layout.addWidget(self.diff_label)
        layout.addLayout(feeds_layout)

        self._graph_canvas = FigureCanvasQTAgg(Figure(figsize=(6, 3)))
        self._graph_canvas.setVisible(False)
        layout.addWidget(self._graph_canvas)

        self.stop_button = QPushButton("Stop Monitor")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_monitor)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)

    def start_monitor(self, camera_choice, camera_index, settings):
        graph_type = settings["graph_type"]
        if graph_type is not None:
            self._graph_canvas.figure.clear()
            projection = "3d" if graph_type == "3d" else None
            ax = self._graph_canvas.figure.add_subplot(111, projection=projection)
            self._live_graph = live_graphs.create_live_graph(graph_type, ax=ax)
            self._graph_canvas.setVisible(True)
        else:
            self._live_graph = None
            self._graph_canvas.setVisible(False)

        self._worker = MonitorWorker(camera_choice, camera_index, settings)
        self._worker.frame_ready.connect(self._on_frame)
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

    def _stop_monitor(self):
        if self._worker is not None:
            self._worker.stop()
        self.stop_button.setEnabled(False)

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
        if self._live_graph is not None:
            self._live_graph.update(frame)

    def _on_error(self, message):
        QMessageBox.critical(self, "Monitor error", message)

    def _on_finished(self):
        self._worker = None
        self.stop_button.setEnabled(False)
        self.stopped.emit()


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
        self.setWindowTitle("ESPI Camera Monitor")
        self.resize(900, 700)

        self._nav = QListWidget()
        self._nav.addItems(["Setup", "Live Monitor"])
        self._nav.setFixedWidth(160)
        self._nav.setCurrentRow(0)
        # "Live Monitor" isn't reachable until a monitor session starts —
        # mirrors run_experiment_gui.py's nav gating (can't jump to Results
        # before a sweep finishes).
        self._nav.item(1).setFlags(self._nav.item(1).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.currentRowChanged.connect(self._stack_to)

        self.setup_page = SetupPage()
        self.live_monitor_page = LiveMonitorPage()

        self._stack = QStackedWidget()
        self._stack.addWidget(self.setup_page)
        self._stack.addWidget(self.live_monitor_page)

        central = QWidget()
        central_layout = QHBoxLayout()
        central_layout.addWidget(self._nav)
        central_layout.addWidget(self._stack)
        central.setLayout(central_layout)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Idle")

        self.setup_page.start_button.clicked.connect(self._start_monitor)
        self.live_monitor_page.stopped.connect(self._on_monitor_stopped)

    def _stack_to(self, row):
        self._stack.setCurrentIndex(row)

    def _start_monitor(self):
        camera_choice = self.setup_page.camera_choice()
        camera_index = self.setup_page.camera_index()
        settings = self.setup_page.settings()

        self.live_monitor_page.start_monitor(camera_choice, camera_index, settings)

        self._nav.item(1).setFlags(self._nav.item(1).flags() | Qt.ItemFlag.ItemIsEnabled)
        self._nav.item(0).setFlags(self._nav.item(0).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.setCurrentRow(1)
        self.statusBar().showMessage("Monitoring")

    def _on_monitor_stopped(self):
        self._nav.item(0).setFlags(self._nav.item(0).flags() | Qt.ItemFlag.ItemIsEnabled)
        self._nav.item(1).setFlags(self._nav.item(1).flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nav.setCurrentRow(0)
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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
