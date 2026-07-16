"""
test_run_experiment_gui.py
Tests for run_experiment_gui.py — the PyQt6 dashboard version of run_experiment.py.

QT_QPA_PLATFORM is forced to "offscreen" before PyQt6 is imported, so this
suite (and CI) can run with no real display attached.

Sections covered
----------------
  SetupPage
    Defaults matching run_experiment.py's terminal defaults, camera/mode
    selection, get_params()'s dict shape, output folder browsing.

  EmittingStream
    Buffers partial print() writes into whole lines before emitting.

  CameraPreviewWorker / PreviewPage
    Camera connect/disconnect lifecycle, exposure unit conversion per
    camera choice, every failure path (missing SDK, missing camera, grab
    failure, an unexpected exception) still reaching finished_cleanly.

  SweepWorker / SweepPage
    Progress parsing for both stdout formats (Basler's unindexed
    "--- Sweeping frequency ---" line and the inclusive/allied vision
    "[i/N] ... Hz" line), log line bubbling, and the sweep-finished signal.

  ResultsPage
    Grid + single-image view construction, Prev/Next navigation and the
    visibility guard on arrow-key shortcuts, view toggling.

  MainWindow
    Nav rail gating through the full Setup -> Preview -> Sweep -> Results
    flow, and the closeEvent() guards (preview asks to stop, a running
    sweep is refused outright since there is no safe way to stop it).
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

import camera_control_inclusive as cci
import run_experiment
import run_experiment_gui as reg
from run_experiment_gui import (
    CameraPreviewWorker,
    EmittingStream,
    MainWindow,
    PreviewPage,
    ResultsPage,
    SetupPage,
    SweepPage,
    SweepWorker,
    _total_sweep_steps,
)


@pytest.fixture(autouse=True)
def _stop_leaked_workers(monkeypatch):
    """
    Guarantee no CameraPreviewWorker or SweepWorker keeps running past its
    test, pass or fail — the same defensive fixture test_monitor_gui.py
    uses, after a mocked, instantly-returning grab_single_frame() was
    found to leave a worker spinning forever if a test raised before
    calling stop_and_wait().
    """
    created = []

    for cls in (CameraPreviewWorker, SweepWorker):
        original_init = cls.__init__

        def _tracking_init(self, *args, _orig=original_init, **kwargs):
            created.append(self)
            _orig(self, *args, **kwargs)

        monkeypatch.setattr(cls, "__init__", _tracking_init)

    yield

    for worker in created:
        if hasattr(worker, "stop"):
            worker.stop()
        if worker.isRunning():
            worker.wait(2000)


def _sweep_params(**overrides):
    base = dict(
        start_freq=100.0, end_freq=300.0, step=100.0, n_averages=5,
        exposure=0.01, gain=0.0, gain_factor=1.0, output_dir="output",
    )
    base.update(overrides)
    return base


# ===========================================================================
# SetupPage
# ===========================================================================

class TestSetupPage:
    def test_default_camera_is_webcam(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        assert page.camera_choice() == "2"

    @pytest.mark.parametrize("choice", ["1", "2", "3"])
    def test_selecting_each_camera_choice(self, qtbot, choice):
        page = SetupPage()
        qtbot.addWidget(page)
        page._camera_radios[choice].setChecked(True)
        assert page.camera_choice() == choice

    def test_default_mode_is_pair_subtraction(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        assert page.mode_choice() == "1"

    def test_selecting_reference_mode(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page._mode_radios["2"].setChecked(True)
        assert page.mode_choice() == "2"

    def test_get_params_matches_cli_defaults(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        params = page.get_params()
        assert params["start_freq"] == pytest.approx(100.0)
        assert params["end_freq"] == pytest.approx(1000.0)
        assert params["step"] == pytest.approx(100.0)
        assert params["n_averages"] == 5
        assert params["exposure"] == pytest.approx(0.01)
        assert params["gain"] == pytest.approx(0.0)
        assert params["gain_factor"] == pytest.approx(1.0)
        assert params["output_dir"] == "output"

    def test_get_params_reflects_typed_values(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.start_freq_spin.setValue(50.0)
        page.end_freq_spin.setValue(500.0)
        page.step_spin.setValue(50.0)
        page.n_averages_spin.setValue(10)
        page.exposure_spin.setValue(0.02)
        page.gain_spin.setValue(3.0)
        page.gain_factor_spin.setValue(5.0)
        page.output_dir_edit.setText("my_output")
        params = page.get_params()
        assert params["start_freq"] == pytest.approx(50.0)
        assert params["end_freq"] == pytest.approx(500.0)
        assert params["step"] == pytest.approx(50.0)
        assert params["n_averages"] == 10
        assert params["exposure"] == pytest.approx(0.02)
        assert params["gain"] == pytest.approx(3.0)
        assert params["gain_factor"] == pytest.approx(5.0)
        assert params["output_dir"] == "my_output"

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

    def test_gain_may_be_zero_or_negative(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.gain_spin.setValue(-3.0)
        assert page.get_params()["gain"] == pytest.approx(-3.0)

    def test_browse_button_sets_output_dir_when_a_folder_is_chosen(self, qtbot, tmp_path):
        page = SetupPage()
        qtbot.addWidget(page)
        with patch(
            "run_experiment_gui.QFileDialog.getExistingDirectory",
            return_value=str(tmp_path),
        ):
            page._browse_output_dir()
        assert page.output_dir_edit.text() == str(tmp_path)

    def test_browse_button_leaves_output_dir_unchanged_on_cancel(self, qtbot):
        page = SetupPage()
        qtbot.addWidget(page)
        page.output_dir_edit.setText("output")
        with patch("run_experiment_gui.QFileDialog.getExistingDirectory", return_value=""):
            page._browse_output_dir()
        assert page.output_dir_edit.text() == "output"


# ===========================================================================
# EmittingStream
# ===========================================================================

class TestEmittingStream:
    def test_single_full_line_emits_once(self, qtbot):
        stream = EmittingStream()
        received = []
        stream.text_written.connect(received.append)
        stream.write("hello world\n")
        assert received == ["hello world"]

    def test_split_writes_recombine_into_one_line(self, qtbot):
        # print("x") issues two write() calls: one for the message, one
        # for the trailing newline — this must still yield one line, not
        # a ragged half-line followed by an empty one.
        stream = EmittingStream()
        received = []
        stream.text_written.connect(received.append)
        stream.write("hello world")
        stream.write("\n")
        assert received == ["hello world"]

    def test_multiple_lines_in_one_write_emit_separately(self, qtbot):
        stream = EmittingStream()
        received = []
        stream.text_written.connect(received.append)
        stream.write("line one\nline two\n")
        assert received == ["line one", "line two"]

    def test_incomplete_line_is_not_emitted_until_newline_arrives(self, qtbot):
        stream = EmittingStream()
        received = []
        stream.text_written.connect(received.append)
        stream.write("still buffering")
        assert received == []
        stream.write("\n")
        assert received == ["still buffering"]

    def test_flush_does_not_raise(self, qtbot):
        EmittingStream().flush()  # must be a safe no-op


# ===========================================================================
# CameraPreviewWorker / PreviewPage
# ===========================================================================

class TestCameraPreviewWorker:
    def test_frame_ready_emits_grabbed_frames(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = CameraPreviewWorker("2", 0.05, 1.0)
        received = []
        worker.frame_ready.connect(received.append)

        worker.start()
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)
        worker.stop()
        worker.wait(2000)

        assert received[0] is gray_100x100

    def test_exposure_converted_with_log2_for_usb_camera(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        received_exposure = []
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(
            cci, "set_exposure_manual", lambda cam, value: received_exposure.append(value)
        )
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = CameraPreviewWorker("2", 0.06, 1.0)
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

        worker = CameraPreviewWorker("2", 0.05, 1.0)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.frame_ready.connect(lambda *_: worker.stop())
        worker.start()
        finished_blocker.wait()

        assert disconnect_calls == [mock_camera]

    def test_missing_camera_emits_error_and_still_finishes(self, qtbot, monkeypatch):
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: None)

        worker = CameraPreviewWorker("2", 0.05, 1.0)
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "Could not open the camera" in error_blocker.args[0]

    def test_grab_failure_emits_error_and_finishes(self, qtbot, monkeypatch):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: None)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        worker = CameraPreviewWorker("2", 0.05, 1.0)
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "grab" in error_blocker.args[0].lower()

    def test_missing_sdk_emits_install_instructions(self, qtbot, monkeypatch):
        def _raise_import_error(name):
            raise ImportError("no module named vmbpy")

        monkeypatch.setattr(
            "run_experiment_gui.importlib.import_module", _raise_import_error
        )

        worker = CameraPreviewWorker("3", 0.05, 1.0)
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "vmbpy" in error_blocker.args[0]

    def test_unexpected_exception_still_disconnects(self, qtbot, monkeypatch):
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

        worker = CameraPreviewWorker("2", 0.05, 1.0)
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_cleanly, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "camera unplugged" in error_blocker.args[0]
        assert disconnect_calls == [mock_camera]


class TestPreviewPage:
    def test_start_preview_sets_is_running(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = PreviewPage()
        qtbot.addWidget(page)
        page.start_preview("2", 0.05, 1.0)
        assert page.is_running() is True
        page.stop_and_wait()
        assert page.is_running() is False

    def test_hide_event_stops_a_running_worker(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = PreviewPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.start_preview("2", 0.05, 1.0)
        assert page.is_running() is True

        page.hide()
        assert page.is_running() is False

    def test_continue_button_stops_worker_and_emits_continued(self, qtbot, monkeypatch, gray_100x100):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        page = PreviewPage()
        qtbot.addWidget(page)
        page.start_preview("2", 0.05, 1.0)

        with qtbot.waitSignal(page.continued, timeout=2000):
            page.continue_button.click()

        assert page.is_running() is False


# ===========================================================================
# SweepWorker / SweepPage
# ===========================================================================

class TestTotalSweepSteps:
    def test_matches_complete_pipeline_formula(self):
        assert _total_sweep_steps(_sweep_params(start_freq=100, end_freq=1000, step=100)) == 10
        assert _total_sweep_steps(_sweep_params(start_freq=100, end_freq=100, step=100)) == 1
        assert _total_sweep_steps(_sweep_params(start_freq=0.01, end_freq=1000, step=0.01)) == 100000


class TestSweepWorker:
    def test_basler_format_advances_progress(self, qtbot, monkeypatch):
        def fake_run_pipeline(camera_choice, mode_choice, params, stop_check=None):
            print("\n--- Sweeping frequency: 100.0 Hz ---")
            print("\n--- Sweeping frequency: 200.0 Hz ---")
            return {100.0: np.zeros((5, 5)), 200.0: np.zeros((5, 5))}

        monkeypatch.setattr(run_experiment, "run_pipeline", fake_run_pipeline)

        stream = EmittingStream()
        worker = SweepWorker("1", "1", _sweep_params(start_freq=100, end_freq=200, step=100), stream)
        progress_calls = []
        worker.progress.connect(lambda *args: progress_calls.append(args))

        with qtbot.waitSignal(worker.finished_sweep, timeout=2000):
            worker.start()

        assert progress_calls == [(1, 2, 100.0), (2, 2, 200.0)]

    def test_indexed_format_advances_progress(self, qtbot, monkeypatch):
        def fake_run_pipeline(camera_choice, mode_choice, params, stop_check=None):
            print("[1/2]  100.0 Hz  some detail")
            print("[2/2]  200.0 Hz  some detail")
            return {100.0: np.zeros((5, 5)), 200.0: np.zeros((5, 5))}

        monkeypatch.setattr(run_experiment, "run_pipeline", fake_run_pipeline)

        stream = EmittingStream()
        worker = SweepWorker("2", "1", _sweep_params(start_freq=100, end_freq=200, step=100), stream)
        progress_calls = []
        worker.progress.connect(lambda *args: progress_calls.append(args))

        with qtbot.waitSignal(worker.finished_sweep, timeout=2000):
            worker.start()

        assert progress_calls == [(1, 2, 100.0), (2, 2, 200.0)]

    def test_unrelated_print_lines_are_ignored(self, qtbot, monkeypatch):
        def fake_run_pipeline(camera_choice, mode_choice, params, stop_check=None):
            print("Connecting to signal generator...")
            print("Signal generator identified: SDG,SDG1032X,MOCK,1.0")
            return {}

        monkeypatch.setattr(run_experiment, "run_pipeline", fake_run_pipeline)

        stream = EmittingStream()
        worker = SweepWorker("2", "1", _sweep_params(), stream)
        progress_calls = []
        worker.progress.connect(lambda *args: progress_calls.append(args))

        with qtbot.waitSignal(worker.finished_sweep, timeout=2000):
            worker.start()

        assert progress_calls == []

    def test_finished_sweep_carries_results(self, qtbot, monkeypatch):
        expected = {100.0: np.zeros((5, 5))}
        monkeypatch.setattr(
            run_experiment, "run_pipeline",
            lambda camera_choice, mode_choice, params, stop_check=None: expected,
        )

        stream = EmittingStream()
        worker = SweepWorker("1", "1", _sweep_params(), stream)
        blocker = qtbot.waitSignal(worker.finished_sweep, timeout=2000)
        worker.start()
        blocker.wait()

        assert blocker.args[0] is expected

    def test_run_pipeline_returning_none_carries_none(self, qtbot, monkeypatch):
        monkeypatch.setattr(
            run_experiment, "run_pipeline",
            lambda camera_choice, mode_choice, params, stop_check=None: None,
        )

        stream = EmittingStream()
        worker = SweepWorker("1", "1", _sweep_params(), stream)
        blocker = qtbot.waitSignal(worker.finished_sweep, timeout=2000)
        worker.start()
        blocker.wait()

        assert blocker.args[0] is None

    def test_stop_flips_the_flag_stop_check_reads(self, qtbot):
        stream = EmittingStream()
        worker = SweepWorker("1", "1", _sweep_params(), stream)
        assert worker._is_stop_requested() is False
        worker.stop()
        assert worker._is_stop_requested() is True

    def test_stop_check_reaches_run_pipeline(self, qtbot, monkeypatch):
        received = {}

        def fake_run_pipeline(camera_choice, mode_choice, params, stop_check=None):
            received["stop_check"] = stop_check
            return {}

        monkeypatch.setattr(run_experiment, "run_pipeline", fake_run_pipeline)

        stream = EmittingStream()
        worker = SweepWorker("1", "1", _sweep_params(), stream)
        with qtbot.waitSignal(worker.finished_sweep, timeout=2000):
            worker.start()

        # "is worker._is_stop_requested" would be a false negative here:
        # accessing a bound method twice yields two distinct-but-equal
        # objects, not the same one. Checking the callable's live behavior
        # instead — it must reflect this exact worker's own flag — is both
        # correct and more meaningful than an identity check would be.
        assert received["stop_check"]() is False
        worker._stop_requested = True
        assert received["stop_check"]() is True

    def test_unexpected_exception_emits_error_and_still_finishes(self, qtbot, monkeypatch):
        def _boom(camera_choice, mode_choice, params, stop_check=None):
            raise RuntimeError("signal generator disconnected")

        monkeypatch.setattr(run_experiment, "run_pipeline", _boom)

        stream = EmittingStream()
        worker = SweepWorker("1", "1", _sweep_params(), stream)
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000)
        finished_blocker = qtbot.waitSignal(worker.finished_sweep, timeout=2000)
        worker.start()
        error_blocker.wait()
        finished_blocker.wait()

        assert "signal generator disconnected" in error_blocker.args[0]
        assert finished_blocker.args[0] is None

    def test_cv2_windows_are_suppressed_during_the_sweep(self, qtbot, monkeypatch):
        # Regression test: complete_pipeline_inclusive.py (and the Basler
        # and Allied Vision pipelines) call cv2.imshow()/cv2.waitKey()
        # unconditionally during every frequency's settling period, which
        # crashes with "Unknown C++ exception from OpenCV code" when
        # called from a background thread (SweepWorker's thread) instead
        # of the main thread, especially on macOS. Simulates that exact
        # call pattern via a fake run_pipeline() and asserts it no longer
        # raises, and that cv2.imshow/cv2.waitKey are their real selves
        # again once the sweep finishes.
        original_imshow = cv2.imshow
        original_waitkey = cv2.waitKey
        seen_calls = []

        def fake_run_pipeline(camera_choice, mode_choice, params, stop_check=None):
            cv2.imshow("ESPI Sweep — Live Feed", np.zeros((5, 5), dtype=np.uint8))
            seen_calls.append(cv2.waitKey(1))
            return {}

        monkeypatch.setattr(run_experiment, "run_pipeline", fake_run_pipeline)

        stream = EmittingStream()
        worker = SweepWorker("2", "1", _sweep_params(), stream)
        error_blocker = qtbot.waitSignal(worker.error, timeout=2000, raising=False)
        finished_blocker = qtbot.waitSignal(worker.finished_sweep, timeout=2000)
        worker.start()
        finished_blocker.wait()

        assert not error_blocker.signal_triggered  # fake pipeline must not have raised
        assert seen_calls == [-1]  # the stubbed cv2.waitKey's own sentinel return value
        assert cv2.imshow is original_imshow
        assert cv2.waitKey is original_waitkey


class TestSuppressCv2Windows:
    def test_imshow_and_waitkey_are_stubbed_inside_the_context(self, qtbot):
        with reg._suppress_cv2_windows():
            assert cv2.imshow("title", np.zeros((5, 5))) is None
            assert cv2.waitKey(1) == -1

    def test_originals_are_restored_after_the_context(self, qtbot):
        original_imshow = cv2.imshow
        original_waitkey = cv2.waitKey
        with reg._suppress_cv2_windows():
            pass
        assert cv2.imshow is original_imshow
        assert cv2.waitKey is original_waitkey

    def test_originals_are_restored_even_if_the_body_raises(self, qtbot):
        original_imshow = cv2.imshow
        original_waitkey = cv2.waitKey
        with pytest.raises(RuntimeError):
            with reg._suppress_cv2_windows():
                raise RuntimeError("boom")
        assert cv2.imshow is original_imshow
        assert cv2.waitKey is original_waitkey


class TestSweepPage:
    def test_begin_sets_progress_bar_and_label(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params(start_freq=100, end_freq=1000, step=100))
        assert page.progress_bar.maximum() == 10
        assert page.progress_bar.value() == 0
        assert "10 frequencies" in page.freq_label.text()
        assert page.start_button.isEnabled() is True

    def test_start_sweep_disables_button_and_emits_started(self, qtbot, monkeypatch):
        monkeypatch.setattr(
            run_experiment, "run_pipeline",
            lambda camera_choice, mode_choice, params, stop_check=None: {},
        )
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params())

        with qtbot.waitSignal(page.sweep_started, timeout=2000):
            page.start_button.click()

        assert page.start_button.isEnabled() is False

    def test_stop_button_hidden_until_a_sweep_starts(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.begin("1", "1", _sweep_params())
        assert page.stop_button.isVisible() is False

    def test_start_sweep_shows_the_stop_button(self, qtbot, monkeypatch):
        monkeypatch.setattr(
            run_experiment, "run_pipeline",
            lambda camera_choice, mode_choice, params, stop_check=None: {},
        )
        page = SweepPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.begin("1", "1", _sweep_params())

        # _start_sweep() shows the button and only then starts the worker
        # thread, so this is deterministic regardless of how fast the
        # (instant, faked) pipeline finishes afterward.
        page.start_button.click()
        assert page.stop_button.isVisible() is True

        with qtbot.waitSignal(page.sweep_finished, timeout=2000):
            pass
        assert page.stop_button.isVisible() is False

    def test_confirm_stop_calls_worker_stop_when_user_confirms(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params())
        fake_worker = MagicMock()
        page._worker = fake_worker

        with patch(
            "run_experiment_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            page._confirm_stop()

        fake_worker.stop.assert_called_once()
        assert page._user_stopped is True
        assert page.stop_button.isEnabled() is False

    def test_confirm_stop_does_nothing_when_user_declines(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params())
        fake_worker = MagicMock()
        page._worker = fake_worker

        with patch(
            "run_experiment_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            page._confirm_stop()

        fake_worker.stop.assert_not_called()
        assert page._user_stopped is False
        assert page.stop_button.isEnabled() is True

    def test_stop_and_wait_stops_and_waits_for_the_worker(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        fake_worker = MagicMock()
        page._worker = fake_worker

        page.stop_and_wait()

        fake_worker.stop.assert_called_once()
        fake_worker.wait.assert_called_once()

    def test_on_finished_phrasing_distinguishes_stopped_from_complete(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params())

        page._user_stopped = True
        page._on_finished({100.0: np.zeros((5, 5))})
        assert "stopped" in page.freq_label.text().lower()

    def test_on_finished_phrasing_for_natural_completion(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params())

        page._on_finished({100.0: np.zeros((5, 5))})
        assert "complete" in page.freq_label.text().lower()

    def test_begin_resets_user_stopped_and_hides_stop_button(self, qtbot):
        page = SweepPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page._user_stopped = True
        page.stop_button.setVisible(True)

        page.begin("1", "1", _sweep_params())

        assert page._user_stopped is False
        assert page.stop_button.isVisible() is False

    def test_sweep_finished_bubbles_results_and_output_dir(self, qtbot, monkeypatch):
        expected_results = {100.0: np.zeros((5, 5))}
        monkeypatch.setattr(
            run_experiment, "run_pipeline",
            lambda camera_choice, mode_choice, params, stop_check=None: expected_results,
        )
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("1", "1", _sweep_params(output_dir="my_output"))

        with qtbot.waitSignal(page.sweep_finished, timeout=2000) as blocker:
            page.start_button.click()

        results, output_dir = blocker.args
        assert results is expected_results
        assert output_dir == "my_output"

    def test_on_progress_updates_bar_and_label(self, qtbot):
        # Calls _on_progress() directly rather than racing a real worker
        # thread: TestSweepWorker already covers the regex parsing that
        # produces these arguments, so this test only needs to check the
        # bar/label update logic itself, without a fast fake pipeline's
        # finish overwriting the label before the assertion runs.
        page = SweepPage()
        qtbot.addWidget(page)
        page.begin("2", "1", _sweep_params(start_freq=100, end_freq=200, step=100))

        page._on_progress(1, 2, 100.0)

        assert page.progress_bar.value() == 1
        assert "1 of 2" in page.freq_label.text()
        assert "100" in page.freq_label.text()


# ===========================================================================
# ResultsPage
# ===========================================================================

class TestResultsPage:
    def _results(self):
        return {
            100.0: np.zeros((10, 10), dtype=np.uint8),
            200.0: np.ones((10, 10), dtype=np.uint8),
        }

    def test_show_results_populates_frequencies(self, qtbot, tmp_path):
        page = ResultsPage()
        qtbot.addWidget(page)
        page.show_results(self._results(), str(tmp_path))
        assert page._freqs == [100.0, 200.0]

    def test_navigation_moves_between_images(self, qtbot, tmp_path):
        page = ResultsPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.show_results(self._results(), str(tmp_path))

        assert page._single_index == 0
        page._show_next()
        assert page._single_index == 1
        page._show_next()  # clamped at the last index
        assert page._single_index == 1
        page._show_previous()
        assert page._single_index == 0
        page._show_previous()  # clamped at 0
        assert page._single_index == 0

    def test_navigation_is_a_no_op_when_page_not_visible(self, qtbot, tmp_path):
        page = ResultsPage()
        qtbot.addWidget(page)
        page.show_results(self._results(), str(tmp_path))
        # Page was never shown, so isVisible() is False — arrow-key
        # shortcuts must not silently affect a hidden/inactive page.
        page._show_next()
        assert page._single_index == 0

    def test_toggle_view_switches_visibility(self, qtbot, tmp_path):
        page = ResultsPage()
        qtbot.addWidget(page)
        page.show()
        qtbot.waitExposed(page)
        page.show_results(self._results(), str(tmp_path))

        assert page._grid_canvas.isVisible() is True
        assert page._single_canvas.isVisible() is False
        page._toggle_view()
        assert page._grid_canvas.isVisible() is False
        assert page._single_canvas.isVisible() is True

    def test_open_folder_calls_qdesktopservices(self, qtbot, tmp_path):
        page = ResultsPage()
        qtbot.addWidget(page)
        page.show_results(self._results(), str(tmp_path))
        with patch("run_experiment_gui.QDesktopServices.openUrl") as mock_open:
            page._open_folder()
        mock_open.assert_called_once()

    def test_run_again_button_emits_signal(self, qtbot, tmp_path):
        page = ResultsPage()
        qtbot.addWidget(page)
        page.show_results(self._results(), str(tmp_path))
        with qtbot.waitSignal(page.run_again, timeout=2000):
            page.run_again_button.click()


# ===========================================================================
# MainWindow — full flow
# ===========================================================================

class TestMainWindow:
    def test_only_setup_enabled_at_startup(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        assert bool(window._nav.item(0).flags() & Qt.ItemFlag.ItemIsEnabled)
        for row in (1, 2, 3):
            assert not (window._nav.item(row).flags() & Qt.ItemFlag.ItemIsEnabled)

    def test_continue_to_preview_unlocks_preview(self, qtbot, monkeypatch, gray_100x100):
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: object())
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window.setup_page.continue_button.click()

        assert window._nav.currentRow() == 1
        assert bool(window._nav.item(1).flags() & Qt.ItemFlag.ItemIsEnabled)
        window.preview_page.stop_and_wait()

    def test_full_flow_unlocks_results(self, qtbot, monkeypatch, gray_100x100, tmp_path):
        mock_camera = object()
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: mock_camera)
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        fake_results = {100.0: np.zeros((5, 5))}
        monkeypatch.setattr(
            run_experiment, "run_pipeline",
            lambda camera_choice, mode_choice, params, stop_check=None: fake_results,
        )

        window = MainWindow()
        qtbot.addWidget(window)
        # build_grid_figure() saves into output_dir directly (the real
        # run_pipeline() creates it via os.makedirs() before returning;
        # the fake above skips that, so point it at a directory that
        # already exists instead of the literal default "output").
        window.setup_page.output_dir_edit.setText(str(tmp_path))

        window.setup_page.continue_button.click()  # -> Preview
        window.preview_page.continue_button.click()  # -> Sweep

        assert window._nav.currentRow() == 2

        with qtbot.waitSignal(window.sweep_page.sweep_finished, timeout=2000):
            window.sweep_page.start_button.click()

        assert window._nav.currentRow() == 3
        assert bool(window._nav.item(3).flags() & Qt.ItemFlag.ItemIsEnabled)
        assert window.results_page._results is fake_results

    def test_run_again_returns_to_setup_and_relocks_nav(self, qtbot, monkeypatch, tmp_path):
        window = MainWindow()
        qtbot.addWidget(window)
        window.results_page.show_results({100.0: np.zeros((5, 5))}, str(tmp_path))

        window.results_page.run_again_button.click()

        assert window._nav.currentRow() == 0
        for row in (1, 2, 3):
            assert not (window._nav.item(row).flags() & Qt.ItemFlag.ItemIsEnabled)

    def test_close_event_closes_immediately_when_nothing_running(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        event = MagicMock()
        window.closeEvent(event)
        event.accept.assert_called_once()

    def test_close_event_declines_to_close_during_a_running_sweep(self, qtbot):
        # A fake worker that merely reports isRunning() == True is enough
        # here; the actual stop mechanics are SweepWorker's own concern,
        # already covered by TestSweepWorker.
        window = MainWindow()
        qtbot.addWidget(window)
        fake_worker = MagicMock(isRunning=lambda: True)
        window.sweep_page._worker = fake_worker

        event = MagicMock()
        with patch(
            "run_experiment_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            window.closeEvent(event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        fake_worker.stop.assert_not_called()

        # qtbot.addWidget() auto-closes this window at teardown, which
        # would call closeEvent() again with QMessageBox.question no
        # longer patched — a real, unpatched QMessageBox.question() blocks
        # forever waiting for a click that can never come in offscreen
        # mode. Clearing the fake "still running" state here avoids that
        # hang, the same way other tests in this class end by calling
        # stop_and_wait() to leave things clean for teardown.
        window.sweep_page._worker = None

    def test_close_event_stops_sweep_when_user_confirms(self, qtbot):
        window = MainWindow()
        qtbot.addWidget(window)
        fake_worker = MagicMock(isRunning=lambda: True)
        window.sweep_page._worker = fake_worker

        event = MagicMock()
        with patch(
            "run_experiment_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.closeEvent(event)

        fake_worker.stop.assert_called_once()
        fake_worker.wait.assert_called_once()
        event.accept.assert_called_once()

        # Same teardown-hang concern as above: this fake worker still
        # reports isRunning() == True forever (stop_and_wait() doesn't
        # clear sweep_page._worker itself — that only happens via a real
        # SweepWorker's finished_sweep signal), so clear it explicitly.
        window.sweep_page._worker = None

    def test_close_event_stops_preview_when_user_confirms(self, qtbot, monkeypatch, gray_100x100):
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: object())
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window.setup_page.continue_button.click()
        assert window.preview_page.is_running() is True

        event = MagicMock()
        with patch(
            "run_experiment_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.closeEvent(event)

        event.accept.assert_called_once()
        assert window.preview_page.is_running() is False

    def test_close_event_ignored_when_user_declines_to_stop_preview(self, qtbot, monkeypatch, gray_100x100):
        monkeypatch.setattr(cci, "connect_camera", lambda camera_index=0: object())
        monkeypatch.setattr(cci, "set_exposure_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "set_gain_manual", lambda cam, value: None)
        monkeypatch.setattr(cci, "grab_single_frame", lambda cam: gray_100x100)
        monkeypatch.setattr(cci, "disconnect_camera", lambda cam: None)

        window = MainWindow()
        qtbot.addWidget(window)
        window.setup_page.continue_button.click()

        event = MagicMock()
        with patch(
            "run_experiment_gui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            window.closeEvent(event)

        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        assert window.preview_page.is_running() is True
        window.preview_page.stop_and_wait()
