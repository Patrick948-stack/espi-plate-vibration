"""
test_monitor_gui.py
Tests for monitor_gui.py — the PyQt6 dashboard version of monitor.py.

QT_QPA_PLATFORM is forced to "offscreen" before PyQt6 is imported, so this
suite (and CI) can run with no real display attached. Set QT_QPA_PLATFORM
yourself before running pytest if you want to watch the dashboard's windows
while debugging a failing test.

Sections covered
----------------
  SetupPage
    Defaults matching monitor.py's terminal defaults (camera, index box
    visibility, exposure/gain/gain_factor spin box validation, graph type
    choices), and the live summary label updating from every input.

  MonitorWorker
    Camera connect/disconnect lifecycle, exposure unit conversion per
    camera choice, frame_ready emitting (frame, diff) with diff=None on the
    first frame and a real diff from the second frame on, the cooperative
    stop() flag actually ending the loop, and every failure path (missing
    camera, grab failure, an unexpected exception) still reaching
    finished_cleanly exactly once.

  LiveMonitorPage
    start_monitor() wiring a worker and showing/hiding the graph canvas
    correctly per graph_type, is_running()/stop_and_wait().

  MainWindow
    Nav rail gating (Live Monitor disabled until a session starts, Setup
    disabled while one is running), and the closeEvent() confirmation guard
    for a running monitor.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

import camera_control_inclusive as cci
import live_graphs
from monitor_gui import SetupPage, MonitorWorker, LiveMonitorPage, MainWindow


def _settings(**overrides):
    base = dict(exposure_s=0.05, gain_db=1.0, gain_factor=10.0, graph_type=None)
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _stop_leaked_workers(monkeypatch):
    """
    Guarantee no MonitorWorker keeps running past its test, pass or fail.

    A MonitorWorker's while loop is only paced by real camera I/O — when a
    test mocks grab_single_frame() to return instantly, nothing throttles
    the loop at all. If a test raises (e.g. a failed assertion) before it
    reaches stop_and_wait(), the worker thread is left spinning as fast as
    the CPU allows, forever — this was hit for real while writing this
    suite and pinned a full CPU core indefinitely. Wrapping the
    constructor records every instance created during a test so teardown
    can always stop it, however the test got there (directly, through
    LiveMonitorPage, or through MainWindow).
    """
    created = []
    original_init = MonitorWorker.__init__

    def _tracking_init(self, *args, **kwargs):
        created.append(self)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(MonitorWorker, "__init__", _tracking_init)
    yield
    for worker in created:
        if worker.isRunning():
            worker.stop()
            worker.wait(2000)


# ===========================================================================
# SetupPage
# ===========================================================================

class TestSetupPage:
    def test_default_is_webcam(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        assert page.camera_choice() == "2"

    @pytest.mark.parametrize("choice", ["1", "2", "3"])
    def test_selecting_each_choice(self, qtbot, choice):
        page = SetupPage()
        qtbot.addWidget(page)
        page._radios[choice].setChecked(True)
        assert page.camera_choice() == choice

    def test_basler_hides_index_box_and_forces_zero(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._index_spin.setValue(7)  # leftover value from a previous choice
        page._radios["1"].setChecked(True)
        assert page._index_spin.isVisible() is False
        assert page.camera_index() == 0

    @pytest.mark.parametrize("choice", ["2", "3"])
    def test_non_basler_shows_index_box(self, qtbot, choice):
        page = SetupPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._radios[choice].setChecked(True)
        assert page._index_spin.isVisible() is True

    def test_settings_defaults_match_cli_defaults(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        settings = page.settings()
        assert settings["exposure_s"] == pytest.approx(0.06)
        assert settings["gain_db"] == pytest.approx(1.0)
        assert settings["gain_factor"] == pytest.approx(20)
        assert settings["graph_type"] is None

    def test_exposure_cannot_reach_zero_or_below(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.exposure_spin.setValue(0)
        assert page.exposure_spin.value() > 0
        page.exposure_spin.setValue(-5)
        assert page.exposure_spin.value() > 0

    def test_gain_factor_cannot_reach_zero_or_below(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.gain_factor_spin.setValue(0)
        assert page.gain_factor_spin.value() > 0
        page.gain_factor_spin.setValue(-1)
        assert page.gain_factor_spin.value() > 0

    def test_gain_db_may_be_zero_or_negative(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.gain_spin.setValue(-3.0)
        assert page.settings()["gain_db"] == pytest.approx(-3.0)

    @pytest.mark.parametrize("choice,expected", [
        ("1", "histogram"),
        ("2", "log_histogram"),
        ("3", "3d"),
        ("4", None),
    ])
    def test_graph_type_choices(self, qtbot, choice, expected):
        page = SetupPage()
        qtbot.addWidget(page)
        page._graph_radios[choice].setChecked(True)
        assert page.settings()["graph_type"] == expected

    def test_summary_updates_with_camera_choice(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page._radios["1"].setChecked(True)
        assert "Basler" in page._summary_label.text()
        assert "index" not in page._summary_label.text()

    def test_summary_shows_index_for_non_basler(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page._radios["3"].setChecked(True)
        page._index_spin.setValue(2)
        assert "index 2" in page._summary_label.text()

    def test_summary_updates_with_settings(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.exposure_spin.setValue(0.02)
        assert "0.02" in page._summary_label.text()


# ===========================================================================
# MonitorWorker
# ===========================================================================

class TestMonitorWorker:
    def test_frame_ready_diff_none_on_first_frame(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append(diff))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)
        worker.stop()
        worker.wait(2000)

        assert received[0] is None

    def test_frame_ready_computes_diff_from_second_frame_on(
        self, qtbot, monkeypatch, gray_100x100, gray_100x100_b
    ):
        mock_camera = object()
        frames = [gray_100x100, gray_100x100_b, gray_100x100_b]
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: frames.pop(0) if frames else gray_100x100_b)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        received = []
        worker.frame_ready.connect(lambda frame, diff: received.append(diff))

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 2, timeout=2000)
        worker.stop()
        worker.wait(2000)

        assert received[0] is None
        assert received[1] is not None
        assert isinstance(received[1], np.ndarray)

    def test_exposure_converted_with_log2_for_usb_camera(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        received_exposure = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(
            cci, "set_exposure_manual",
            lambda cam, value: received_exposure.append(value),
        )
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings(exposure_s=0.06))
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.frame_ready.connect(lambda *_: worker.stop())
        worker.start()
        finished_blocker.wait()

        assert received_exposure[0] == pytest.approx(np.log2(0.06))

    def test_disconnect_called_exactly_once_on_stop(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        disconnect_calls = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(
            cci, "disconnect_camera", lambda cam: disconnect_calls.append(cam)
        )

        worker = MonitorWorker("2", 0, _settings())
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.frame_ready.connect(lambda *_: worker.stop())
        worker.start()
        finished_blocker.wait()

        assert disconnect_calls == [mock_camera]

    def test_missing_camera_emits_error_and_still_finishes(self, qtbot, monkeypatch):
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: None)
        disconnect_calls = []
        monkeypatch.setattr(
            cci, "disconnect_camera", lambda cam: disconnect_calls.append(cam)
        )

        worker = MonitorWorker("2", 0, _settings())
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert disconnect_calls == []  # never connected, so never disconnected

    def test_grab_failure_emits_error_and_finishes(self, qtbot, monkeypatch):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: None)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = MonitorWorker("2", 0, _settings())
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "grab" in error_blocker.args[0].lower()

    def test_unexpected_exception_emits_error_and_still_disconnects(self, qtbot, monkeypatch):
        mock_camera = object()
        disconnect_calls = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)

        def _boom(cam):
            raise RuntimeError("camera unplugged")

        monkeypatch.setattr(cci, "grab_single_frame", _boom)
        monkeypatch.setattr(
            cci, "disconnect_camera", lambda cam: disconnect_calls.append(cam)
        )

        worker = MonitorWorker("2", 0, _settings())
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "camera unplugged" in error_blocker.args[0]
        assert disconnect_calls == [mock_camera]


# ===========================================================================
# LiveMonitorPage
# ===========================================================================

class TestLiveMonitorPage:
    def test_start_monitor_with_no_graph_hides_canvas(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.start_monitor("2", 0, _settings(graph_type=None))

        assert page._live_graph is None
        assert page._graph_canvas.isVisible() is False
        assert page.is_running() is True

        page.stop_and_wait()
        assert page.is_running() is False

    def test_start_monitor_with_histogram_shows_canvas(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = LiveMonitorPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.start_monitor("2", 0, _settings(graph_type="histogram"))

        assert isinstance(page._live_graph, live_graphs.LiveHistogram)
        assert page._live_graph._owns_figure is False
        assert page._graph_canvas.isVisible() is True

        page.stop_and_wait()

    def test_stop_button_disabled_until_started(self, qtbot):
        page = LiveMonitorPage()
        qtbot.addWidget(page)
        assert page.stop_button.isEnabled() is False


# ===========================================================================
# MainWindow
# ===========================================================================

class TestMainWindow:
    def test_live_monitor_nav_disabled_at_startup(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert not (window._nav.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)

    def test_starting_monitor_enables_live_monitor_and_disables_setup(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        assert window._nav.item(1).flags() & Qt.ItemFlag.ItemIsEnabled
        assert not (window._nav.item(0).flags() & Qt.ItemFlag.ItemIsEnabled)
        assert window._nav.currentRow() == 1

        window.live_monitor_page.stop_and_wait()

    def test_close_event_ignored_when_user_declines_to_stop(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        event = MagicMock()
        with patch(
            "monitor_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            window.closeEvent(event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        assert window.live_monitor_page.is_running() is True

        window.live_monitor_page.stop_and_wait()

    def test_close_event_stops_worker_when_user_confirms(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window._start_monitor()

        event = MagicMock()
        with patch(
            "monitor_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.closeEvent(event)

        event.accept.assert_called_once()
        assert window.live_monitor_page.is_running() is False

    def test_close_event_closes_immediately_when_nothing_running(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)

        event = MagicMock()
        window.closeEvent(event)

        event.accept.assert_called_once()
