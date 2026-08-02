"""
test_run_experiment.py
Tests for run_experiment.py — the interactive entry point for all ESPI sweeps.

Sections covered
----------------
  ask()
    Prompt helper that wraps input().  Tests cover: default values, type
    casting, allowlist validation, and rejection of bad input.

  run_pipeline()
    Exposure unit conversion.  The user always enters seconds; the function
    must convert to microseconds (camera 1/3) or log2 scale (camera 2) before
    forwarding the value to the pipeline.  All pipeline imports are replaced
    with in-memory mock modules so no hardware is needed.

  confirm_settings()
    Smoke-test that the confirmation screen runs without error and emits the
    expected exposure unit label.
"""

import io
import math
import sys
import os
import types
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import run_experiment

_SENTINEL = object()  # distinguishes "key was absent" from "key was None"


# ===========================================================================
# HELPERS
# ===========================================================================

def _default_params(**overrides):
    """Return a minimal valid params dict, optionally overriding fields."""
    base = dict(
        start_freq  = 100.0,
        end_freq    = 200.0,
        step        = 100.0,
        n_averages  = 5,
        exposure    = 0.01,     # 10 ms in seconds
        gain        = 0.0,
        gain_factor = 1,
        output_dir  = "out",
    )
    base.update(overrides)
    return base


def _mock_pipeline_module(name):
    """
    Inject a mock module into sys.modules so that the local imports inside
    run_pipeline() resolve to our mocks instead of the real hardware modules.
    Returns the mock module so tests can inspect what was called.
    """
    mod = types.ModuleType(name)
    mod.frequency_sweep                        = MagicMock(return_value={100.0: None})
    mod.reference_frequency_sweep              = MagicMock(return_value={100.0: None})
    mod.frequency_sweep_inclusive              = MagicMock(return_value={100.0: None})
    mod.reference_frequency_sweep_inclusive    = MagicMock(return_value={100.0: None})
    mod.frequency_sweep_allied_vision          = MagicMock(return_value={100.0: None})
    mod.reference_frequency_sweep_allied_vision = MagicMock(return_value={100.0: None})
    sys.modules[name] = mod
    return mod


# ===========================================================================
# ask() — interactive input helper
# ===========================================================================

class TestAsk:
    def test_returns_default_on_empty_input(self):
        with patch("builtins.input", return_value=""):
            result = run_experiment.ask("prompt", default="hello")
        assert result == "hello"

    def test_default_is_cast_to_requested_type(self):
        with patch("builtins.input", return_value=""):
            result = run_experiment.ask("prompt", default="3.14", cast=float)
        assert result == pytest.approx(3.14)
        assert isinstance(result, float)

    def test_typed_value_is_cast(self):
        with patch("builtins.input", return_value="42"):
            result = run_experiment.ask("prompt", cast=int)
        assert result == 42

    def test_typed_float_is_cast(self):
        with patch("builtins.input", return_value="1000.5"):
            result = run_experiment.ask("prompt", cast=float)
        assert result == pytest.approx(1000.5)

    def test_accepts_value_in_valid_list(self):
        with patch("builtins.input", return_value="2"):
            result = run_experiment.ask("prompt", valid=["1", "2", "3"])
        assert result == "2"

    def test_rejects_then_accepts_valid_value(self):
        # First call returns an invalid value, second returns a valid one.
        with patch("builtins.input", side_effect=["9", "1"]):
            result = run_experiment.ask("prompt", valid=["1", "2"])
        assert result == "1"

    def test_rejects_bad_cast_then_accepts_good_value(self):
        with patch("builtins.input", side_effect=["not_a_number", "5"]):
            result = run_experiment.ask("prompt", cast=int)
        assert result == 5

    def test_empty_with_no_default_re_prompts(self):
        # Empty input with no default should loop; provide a valid answer second.
        with patch("builtins.input", side_effect=["", "yes"]):
            result = run_experiment.ask("prompt")
        assert result == "yes"

    def test_returns_string_by_default(self):
        with patch("builtins.input", return_value="abc"):
            result = run_experiment.ask("prompt")
        assert isinstance(result, str)


# ===========================================================================
# run_pipeline() — exposure unit conversion
# ===========================================================================

class TestRunPipelineExposureConversion:

    def setup_method(self):
        """Inject mock pipeline modules before each test."""
        self._basler_mod = _mock_pipeline_module("complete_pipeline")
        self._cv_mod     = _mock_pipeline_module("complete_pipeline_inclusive")
        self._av_mod     = _mock_pipeline_module("complete_pipeline_allied_vision")

    def teardown_method(self):
        """Remove injected modules after each test."""
        for name in ("complete_pipeline",
                     "complete_pipeline_inclusive",
                     "complete_pipeline_allied_vision"):
            sys.modules.pop(name, None)

    # --- Camera 1 (Basler) ---

    def test_basler_converts_seconds_to_microseconds(self):
        run_experiment.run_pipeline("1", "1", _default_params(exposure=0.01))
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(10_000.0)

    def test_basler_reference_mode_converts_seconds_to_microseconds(self):
        run_experiment.run_pipeline("1", "2", _default_params(exposure=0.005))
        kwargs = self._basler_mod.reference_frequency_sweep.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(5_000.0)

    def test_basler_longer_exposure_converts_correctly(self):
        run_experiment.run_pipeline("1", "1", _default_params(exposure=0.1))
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(100_000.0)

    # --- Camera 2 (OpenCV / USB) ---

    def test_opencv_converts_seconds_to_log2_scale(self):
        # 0.015625 s = 2^(-6) → log2 value of -6
        run_experiment.run_pipeline("2", "1", _default_params(exposure=0.015625))
        kwargs = self._cv_mod.frequency_sweep_inclusive.call_args[1]
        assert kwargs["exposure"] == pytest.approx(-6.0, abs=0.01)

    def test_opencv_10ms_gives_correct_log2(self):
        # 0.01 s → log2(0.01) ≈ -6.64
        run_experiment.run_pipeline("2", "1", _default_params(exposure=0.01))
        kwargs = self._cv_mod.frequency_sweep_inclusive.call_args[1]
        assert kwargs["exposure"] == pytest.approx(math.log2(0.01), abs=1e-9)

    def test_opencv_reference_mode_converts_correctly(self):
        run_experiment.run_pipeline("2", "2", _default_params(exposure=0.015625))
        kwargs = self._cv_mod.reference_frequency_sweep_inclusive.call_args[1]
        assert kwargs["exposure"] == pytest.approx(-6.0, abs=0.01)

    # --- Camera 3 (Allied Vision) ---

    def test_allied_converts_seconds_to_microseconds(self):
        run_experiment.run_pipeline("3", "1", _default_params(exposure=0.01))
        kwargs = self._av_mod.frequency_sweep_allied_vision.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(10_000.0)

    def test_allied_reference_mode_converts_correctly(self):
        run_experiment.run_pipeline("3", "2", _default_params(exposure=0.02))
        kwargs = self._av_mod.reference_frequency_sweep_allied_vision.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(20_000.0)

    # --- Symmetry check: cameras 1 and 3 use the same formula ---

    def test_basler_and_allied_produce_identical_exposure_us(self):
        params = _default_params(exposure=0.03)
        run_experiment.run_pipeline("1", "1", params)
        run_experiment.run_pipeline("3", "1", params)
        basler_us = self._basler_mod.frequency_sweep.call_args[1]["exposure_us"]
        allied_us = self._av_mod.frequency_sweep_allied_vision.call_args[1]["exposure_us"]
        assert basler_us == pytest.approx(allied_us)


# ===========================================================================
# run_pipeline() — amplitude/offset propagation
# ===========================================================================
# run_experiment_gui.py's SetupPage now includes amplitude/offset in
# get_params(), so run_pipeline()'s base_params must forward them to
# whichever sweep function is chosen, for all three cameras and both
# subtraction modes. Read with .get(key, default) rather than indexed
# directly, so run_experiment.py's own terminal CLI (whose
# choose_sweep_params() does not collect these yet) keeps working
# unchanged, falling back to the same 1.0/0.0 every pipeline function
# already defaults to.

class TestRunPipelineAmplitudeOffset:

    def setup_method(self):
        self._basler_mod = _mock_pipeline_module("complete_pipeline")
        self._cv_mod     = _mock_pipeline_module("complete_pipeline_inclusive")
        self._av_mod     = _mock_pipeline_module("complete_pipeline_allied_vision")

    def teardown_method(self):
        for name in ("complete_pipeline",
                     "complete_pipeline_inclusive",
                     "complete_pipeline_allied_vision"):
            sys.modules.pop(name, None)

    def test_basler_forwards_amplitude_and_offset(self):
        run_experiment.run_pipeline("1", "1", _default_params(amplitude=3.3, offset=-2.0))
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(3.3)
        assert kwargs["offset"] == pytest.approx(-2.0)

    def test_basler_reference_mode_forwards_amplitude_and_offset(self):
        run_experiment.run_pipeline("1", "2", _default_params(amplitude=4.0, offset=1.0))
        kwargs = self._basler_mod.reference_frequency_sweep.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(4.0)
        assert kwargs["offset"] == pytest.approx(1.0)

    def test_opencv_forwards_amplitude_and_offset(self):
        run_experiment.run_pipeline("2", "1", _default_params(amplitude=2.5, offset=0.5))
        kwargs = self._cv_mod.frequency_sweep_inclusive.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(2.5)
        assert kwargs["offset"] == pytest.approx(0.5)

    def test_opencv_reference_mode_forwards_amplitude_and_offset(self):
        run_experiment.run_pipeline("2", "2", _default_params(amplitude=2.5, offset=0.5))
        kwargs = self._cv_mod.reference_frequency_sweep_inclusive.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(2.5)
        assert kwargs["offset"] == pytest.approx(0.5)

    def test_allied_forwards_amplitude_and_offset(self):
        run_experiment.run_pipeline("3", "1", _default_params(amplitude=5.0, offset=1.5))
        kwargs = self._av_mod.frequency_sweep_allied_vision.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(5.0)
        assert kwargs["offset"] == pytest.approx(1.5)

    def test_allied_reference_mode_forwards_amplitude_and_offset(self):
        run_experiment.run_pipeline("3", "2", _default_params(amplitude=5.0, offset=1.5))
        kwargs = self._av_mod.reference_frequency_sweep_allied_vision.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(5.0)
        assert kwargs["offset"] == pytest.approx(1.5)

    def test_missing_amplitude_and_offset_default_to_1v_and_0v(self):
        """Terminal CLI callers whose params dict has no amplitude/offset keys yet."""
        run_experiment.run_pipeline("1", "1", _default_params())
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["amplitude"] == pytest.approx(1.0)
        assert kwargs["offset"] == pytest.approx(0.0)


# ===========================================================================
# run_pipeline() — stop_check propagation
# ===========================================================================
# run_experiment_gui.py's SweepWorker passes its own stop_check through
# run_pipeline() so the Stop Sweep button can end a running sweep safely —
# these tests confirm it actually reaches whichever sweep function is
# chosen, for all three cameras and both subtraction modes.

class TestRunPipelineStopCheck:

    def setup_method(self):
        self._basler_mod = _mock_pipeline_module("complete_pipeline")
        self._cv_mod     = _mock_pipeline_module("complete_pipeline_inclusive")
        self._av_mod     = _mock_pipeline_module("complete_pipeline_allied_vision")

    def teardown_method(self):
        for name in ("complete_pipeline",
                     "complete_pipeline_inclusive",
                     "complete_pipeline_allied_vision"):
            sys.modules.pop(name, None)

    def test_default_is_none(self):
        run_experiment.run_pipeline("1", "1", _default_params())
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["stop_check"] is None

    def test_basler_pair_mode_forwards_stop_check(self):
        marker = lambda: False
        run_experiment.run_pipeline("1", "1", _default_params(), stop_check=marker)
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["stop_check"] is marker

    def test_basler_reference_mode_forwards_stop_check(self):
        marker = lambda: False
        run_experiment.run_pipeline("1", "2", _default_params(), stop_check=marker)
        kwargs = self._basler_mod.reference_frequency_sweep.call_args[1]
        assert kwargs["stop_check"] is marker

    def test_opencv_pair_mode_forwards_stop_check(self):
        marker = lambda: False
        run_experiment.run_pipeline("2", "1", _default_params(), stop_check=marker)
        kwargs = self._cv_mod.frequency_sweep_inclusive.call_args[1]
        assert kwargs["stop_check"] is marker

    def test_opencv_reference_mode_forwards_stop_check(self):
        marker = lambda: False
        run_experiment.run_pipeline("2", "2", _default_params(), stop_check=marker)
        kwargs = self._cv_mod.reference_frequency_sweep_inclusive.call_args[1]
        assert kwargs["stop_check"] is marker

    def test_allied_pair_mode_forwards_stop_check(self):
        marker = lambda: False
        run_experiment.run_pipeline("3", "1", _default_params(), stop_check=marker)
        kwargs = self._av_mod.frequency_sweep_allied_vision.call_args[1]
        assert kwargs["stop_check"] is marker

    def test_allied_reference_mode_forwards_stop_check(self):
        marker = lambda: False
        run_experiment.run_pipeline("3", "2", _default_params(), stop_check=marker)
        kwargs = self._av_mod.reference_frequency_sweep_allied_vision.call_args[1]
        assert kwargs["stop_check"] is marker


# ===========================================================================
# run_pipeline() — gain_factor propagation
# ===========================================================================

class TestRunPipelineGainFactor:
    """
    gain_factor must reach every sweep function, for every camera and both
    subtraction modes, unchanged from what the user typed.
    """

    def setup_method(self):
        self._basler_mod = _mock_pipeline_module("complete_pipeline")
        self._cv_mod     = _mock_pipeline_module("complete_pipeline_inclusive")
        self._av_mod     = _mock_pipeline_module("complete_pipeline_allied_vision")

    def teardown_method(self):
        for name in ("complete_pipeline",
                     "complete_pipeline_inclusive",
                     "complete_pipeline_allied_vision"):
            sys.modules.pop(name, None)

    def test_basler_pair_mode(self):
        run_experiment.run_pipeline("1", "1", _default_params(gain_factor=15))
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(15)

    def test_basler_reference_mode(self):
        run_experiment.run_pipeline("1", "2", _default_params(gain_factor=15))
        kwargs = self._basler_mod.reference_frequency_sweep.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(15)

    def test_opencv_pair_mode(self):
        run_experiment.run_pipeline("2", "1", _default_params(gain_factor=30))
        kwargs = self._cv_mod.frequency_sweep_inclusive.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(30)

    def test_opencv_reference_mode(self):
        run_experiment.run_pipeline("2", "2", _default_params(gain_factor=30))
        kwargs = self._cv_mod.reference_frequency_sweep_inclusive.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(30)

    def test_allied_pair_mode(self):
        run_experiment.run_pipeline("3", "1", _default_params(gain_factor=5))
        kwargs = self._av_mod.frequency_sweep_allied_vision.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(5)

    def test_allied_reference_mode(self):
        run_experiment.run_pipeline("3", "2", _default_params(gain_factor=5))
        kwargs = self._av_mod.reference_frequency_sweep_allied_vision.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(5)

    def test_default_gain_factor_is_1(self):
        # _default_params() itself defaults gain_factor to 1 (no amplification),
        # matching the sweep functions' own default — confirms run_pipeline()
        # doesn't silently drop or override it when the caller didn't ask for
        # anything unusual.
        run_experiment.run_pipeline("1", "1", _default_params())
        kwargs = self._basler_mod.frequency_sweep.call_args[1]
        assert kwargs["gain_factor"] == pytest.approx(1)


# ===========================================================================
# run_pipeline() — ImportError handling
# ===========================================================================

class TestRunPipelineImportError:
    """
    Verify run_pipeline() returns None when a required pipeline module is
    unavailable (e.g. pypylon or vmbpy not installed).

    Setting sys.modules[name] = None makes Python raise ImportError on any
    attempt to import that name, simulating a missing optional dependency.
    """

    @staticmethod
    def _block_import(name):
        """Return a context manager that blocks `name` from being imported."""
        import contextlib

        @contextlib.contextmanager
        def _cm():
            prev = sys.modules.get(name, _SENTINEL)
            sys.modules[name] = None
            try:
                yield
            finally:
                if prev is _SENTINEL:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = prev

        return _cm()

    def test_returns_none_when_basler_module_missing(self):
        with self._block_import("complete_pipeline"):
            result = run_experiment.run_pipeline("1", "1", _default_params())
        assert result is None

    def test_returns_none_when_cv_module_missing(self):
        with self._block_import("complete_pipeline_inclusive"):
            result = run_experiment.run_pipeline("2", "1", _default_params())
        assert result is None

    def test_returns_none_when_allied_module_missing(self):
        with self._block_import("complete_pipeline_allied_vision"):
            result = run_experiment.run_pipeline("3", "1", _default_params())
        assert result is None


# ===========================================================================
# confirm_settings() — display smoke test
# ===========================================================================

class TestConfirmSettings:
    def test_confirm_shows_exposure_in_seconds(self, capsys):
        with patch("builtins.input", return_value="n"):
            run_experiment.confirm_settings(
                "2", "1",
                _default_params(exposure=0.01),
            )
        output = capsys.readouterr().out
        assert "0.01" in output
        assert "s" in output

    def test_confirm_shows_frequency_range_correctly(self, capsys):
        with patch("builtins.input", return_value="n"):
            run_experiment.confirm_settings(
                "1", "1",
                _default_params(start_freq=100, end_freq=100.3, step=0.25),
            )
        output = capsys.readouterr().out
        assert "100.3" in output
        assert "0.25" in output

    def test_confirm_returns_false_on_n(self):
        with patch("builtins.input", return_value="n"):
            result = run_experiment.confirm_settings("2", "1", _default_params())
        assert result is False

    def test_confirm_returns_true_on_y(self):
        with patch("builtins.input", return_value="y"):
            result = run_experiment.confirm_settings("2", "1", _default_params())
        assert result is True


# ===========================================================================
# _show_preview_feed() — live camera preview before sweep
# ===========================================================================

class TestShowPreviewFeed:

    def test_warns_and_skips_when_library_not_importable(self, capsys):
        # A missing SDK now prints a specific, actionable [ERROR] message
        # (via _missing_sdk_message) instead of a generic [WARNING], and
        # names exactly which package to install.
        with patch("importlib.import_module", side_effect=ImportError("no pypylon")):
            run_experiment._show_preview_feed("1")
        out = capsys.readouterr().out
        assert "ERROR" in out
        assert "pip install pypylon" in out

    def test_missing_function_on_loaded_library_warns_with_specifics(self, capsys):
        # Distinct from "SDK not installed": the module imported fine but is
        # missing a function it should have (e.g. an incomplete or outdated
        # copy of the file) — a different problem, a different message.
        mock_lib = MagicMock(spec=[])  # spec=[] means every attribute access raises AttributeError
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("2")
        out = capsys.readouterr().out
        assert "WARNING" in out
        assert "missing a" in out

    def test_warns_and_skips_when_camera_is_none(self, capsys):
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = None
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("2")
        mock_lib.show_live_feed_from_camera.assert_not_called()
        out = capsys.readouterr().out
        assert "WARNING" in out

    def test_calls_feed_and_disconnects_on_success(self):
        mock_cam = MagicMock()
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = mock_cam
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("3")
        mock_lib.show_live_feed_from_camera.assert_called_once_with(mock_cam)
        mock_lib.disconnect_camera.assert_called_once_with(mock_cam)

    def test_applies_exposure_and_gain_before_showing_feed(self):
        # Basler/Allied Vision (any choice but "2") convert seconds to
        # microseconds, the same as run_pipeline() does for the real sweep.
        mock_cam = MagicMock()
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = mock_cam
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("3", exposure_s=0.01, gain=2.0)
        mock_lib.set_exposure_manual.assert_called_once_with(mock_cam, pytest.approx(10_000.0))
        mock_lib.set_gain_manual.assert_called_once_with(mock_cam, 2.0)

    def test_applies_exposure_using_log2_scale_for_webcam(self):
        mock_cam = MagicMock()
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = mock_cam
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("2", exposure_s=0.015625, gain=0.0)
        mock_lib.set_exposure_manual.assert_called_once_with(mock_cam, pytest.approx(-6.0, abs=0.01))

    def test_no_exposure_or_gain_given_skips_applying_settings(self):
        mock_cam = MagicMock()
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = mock_cam
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("3")  # exposure_s/gain default to None
        mock_lib.set_exposure_manual.assert_not_called()
        mock_lib.set_gain_manual.assert_not_called()

    def test_failure_applying_settings_is_caught_and_feed_still_shows(self, capsys):
        mock_cam = MagicMock()
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = mock_cam
        mock_lib.set_exposure_manual.side_effect = RuntimeError("camera busy")
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("3", exposure_s=0.01, gain=0.0)
        mock_lib.show_live_feed_from_camera.assert_called_once_with(mock_cam)
        out = capsys.readouterr().out
        assert "Could not apply exposure/gain" in out

    def test_feed_crash_is_caught_and_disconnect_still_runs(self, capsys):
        # The preview is a convenience, not a requirement — a crash here
        # (e.g. a cable came loose while aiming) must not take down the
        # rest of the program. This is a deliberate behavior change: this
        # used to re-raise and crash run_experiment.py entirely.
        mock_cam = MagicMock()
        mock_lib = MagicMock()
        mock_lib.connect_camera.return_value = mock_cam
        mock_lib.show_live_feed_from_camera.side_effect = RuntimeError("crash")
        with patch("importlib.import_module", return_value=mock_lib):
            run_experiment._show_preview_feed("2")  # must not raise
        mock_lib.disconnect_camera.assert_called_once_with(mock_cam)
        out = capsys.readouterr().out
        assert "WARNING" in out
        assert "crash" in out


# ===========================================================================
# reconfigure_if_needed() — pre-sweep settings adjustment loop
# ===========================================================================

class TestReconfigureIfNeeded:

    PARAMS = dict(
        start_freq=100.0, end_freq=200.0, step=100.0, n_averages=5,
        exposure=0.01, gain=0.0, gain_factor=1,
    )

    def test_returns_params_unchanged_when_no(self):
        with patch("builtins.input", return_value="no"), \
             patch.object(run_experiment, "_show_preview_feed"):
            result = run_experiment.reconfigure_if_needed("2", dict(self.PARAMS))
        assert result == self.PARAMS

    def test_camera_choice_updates_exposure_and_gain(self):
        with patch("builtins.input", side_effect=["camera", "0.02", "1.0", "25", "n"]), \
             patch.object(run_experiment, "_show_preview_feed"):
            result = run_experiment.reconfigure_if_needed("2", dict(self.PARAMS))
        assert result["exposure"]    == pytest.approx(0.02)
        assert result["gain"]        == pytest.approx(1.0)
        assert result["gain_factor"] == pytest.approx(25)

    def test_signal_choice_updates_frequency_params(self):
        with patch("builtins.input",
                   side_effect=["signal", "200.0", "400.0", "50.0", "3", "n"]), \
             patch.object(run_experiment, "_show_preview_feed"):
            result = run_experiment.reconfigure_if_needed("1", dict(self.PARAMS))
        assert result["start_freq"] == pytest.approx(200.0)
        assert result["end_freq"]   == pytest.approx(400.0)
        assert result["step"]       == pytest.approx(50.0)
        assert result["n_averages"] == 3

    def test_preview_feed_shown_after_adjustment(self):
        # The preview must reflect the settings just typed (0.02 s, 1.0 dB),
        # not the ones the camera happened to already be sitting at.
        with patch("builtins.input", side_effect=["camera", "0.02", "1.0", "20", "n"]), \
             patch.object(run_experiment, "_show_preview_feed") as mock_feed:
            run_experiment.reconfigure_if_needed("2", dict(self.PARAMS))
        mock_feed.assert_called_once_with("2", pytest.approx(0.02), pytest.approx(1.0))

    def test_preview_not_shown_when_no_changes(self):
        with patch("builtins.input", return_value="no"), \
             patch.object(run_experiment, "_show_preview_feed") as mock_feed:
            run_experiment.reconfigure_if_needed("3", dict(self.PARAMS))
        mock_feed.assert_not_called()

    def test_loops_when_user_wants_more_changes(self):
        with patch("builtins.input", side_effect=["camera", "0.05", "2.0", "30", "y", "no"]), \
             patch.object(run_experiment, "_show_preview_feed"):
            result = run_experiment.reconfigure_if_needed("1", dict(self.PARAMS))
        assert result["exposure"] == pytest.approx(0.05)
        assert result["gain"]     == pytest.approx(2.0)


# ===========================================================================
# ask_positive_float() — shared by choose_sweep_params(), reconfigure_if_needed(),
# and monitor.py (which imports this exact function instead of keeping its
# own copy)
# ===========================================================================

class TestAskPositiveFloat:
    def test_returns_default_on_empty_input(self):
        with patch("builtins.input", return_value=""):
            result = run_experiment.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(0.01)

    def test_rejects_zero_then_accepts_positive(self):
        with patch("builtins.input", side_effect=["0", "0.02"]):
            result = run_experiment.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(0.02)

    def test_rejects_negative_then_accepts_positive(self):
        with patch("builtins.input", side_effect=["-5", "1"]):
            result = run_experiment.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(1)

    def test_prints_explanation_when_rejecting(self, capsys):
        with patch("builtins.input", side_effect=["-1", "1"]):
            run_experiment.ask_positive_float("Exposure (s)", default=0.01)
        out = capsys.readouterr().out
        assert "must be greater than 0" in out

    def test_choose_sweep_params_rejects_zero_exposure(self):
        # End-to-end: the exposure question inside choose_sweep_params()
        # must actually be routed through ask_positive_float(), not a plain
        # ask() that would silently accept 0.
        answers = ["100", "1000", "100", "5",   # freq/step/averages
                   "0", "0.02",                  # exposure: rejected, retried
                   "0.0", "20", "out"]           # gain, gain_factor, output_dir
        with patch("builtins.input", side_effect=answers):
            params = run_experiment.choose_sweep_params()
        assert params["exposure"] == pytest.approx(0.02)


# ===========================================================================
# _missing_sdk_message() — shared install instructions for a missing camera
# SDK, used by both run_pipeline() and _show_preview_feed()
# ===========================================================================

class TestMissingSdkMessage:
    def test_basler_message(self, capsys):
        run_experiment._missing_sdk_message("1", "complete_pipeline", ImportError("no pypylon"))
        out = capsys.readouterr().out
        assert "pip install pypylon" in out
        assert "Pylon Camera Software Suite" in out

    def test_opencv_message(self, capsys):
        run_experiment._missing_sdk_message("2", "complete_pipeline_inclusive", ImportError("no cv2"))
        out = capsys.readouterr().out
        assert "pip install opencv-python" in out

    def test_allied_message_on_windows_uses_backslash_path(self, capsys):
        with patch.object(run_experiment, "_ON_WINDOWS", True):
            run_experiment._missing_sdk_message("3", "complete_pipeline_allied_vision", ImportError("no vmbpy"))
        out = capsys.readouterr().out
        assert "C:\\path\\to\\vmbpy_file.whl" in out

    def test_allied_message_on_mac_linux_uses_forward_slash_path(self, capsys):
        with patch.object(run_experiment, "_ON_WINDOWS", False):
            run_experiment._missing_sdk_message("3", "complete_pipeline_allied_vision", ImportError("no vmbpy"))
        out = capsys.readouterr().out
        assert "/path/to/vmbpy_file.whl" in out
        assert "C:\\" not in out

    def test_error_detail_included(self, capsys):
        run_experiment._missing_sdk_message("2", "complete_pipeline_inclusive",
                                             ImportError("libGL.so.1: cannot open shared object file"))
        out = capsys.readouterr().out
        assert "libGL.so.1" in out


# ===========================================================================
# run_pipeline() — crash recovery: invalid exposure, mid-sweep exceptions,
# and an unrecognised camera_choice
# ===========================================================================

class TestRunPipelineErrorRecovery:
    def setup_method(self):
        self._basler_mod = _mock_pipeline_module("complete_pipeline")
        self._cv_mod     = _mock_pipeline_module("complete_pipeline_inclusive")
        self._av_mod     = _mock_pipeline_module("complete_pipeline_allied_vision")

    def teardown_method(self):
        for name in ("complete_pipeline",
                     "complete_pipeline_inclusive",
                     "complete_pipeline_allied_vision"):
            sys.modules.pop(name, None)

    def test_zero_exposure_on_opencv_path_is_caught(self, capsys):
        # math.log2(0) raises ValueError — must be caught with a specific
        # message, not let a raw "math domain error" traceback through.
        result = run_experiment.run_pipeline("2", "1", _default_params(exposure=0.0))
        assert result is None
        out = capsys.readouterr().out
        assert "Invalid exposure" in out
        self._cv_mod.frequency_sweep_inclusive.assert_not_called()

    def test_negative_exposure_on_opencv_path_is_caught(self, capsys):
        result = run_experiment.run_pipeline("2", "1", _default_params(exposure=-0.01))
        assert result is None
        out = capsys.readouterr().out
        assert "Invalid exposure" in out

    def test_sweep_crash_on_basler_path_is_caught(self, capsys):
        self._basler_mod.frequency_sweep.side_effect = RuntimeError("signal generator disconnected")
        result = run_experiment.run_pipeline("1", "1", _default_params())
        assert result is None
        out = capsys.readouterr().out
        assert "stopped unexpectedly" in out
        assert "signal generator disconnected" in out

    def test_sweep_crash_on_reference_mode_is_caught(self, capsys):
        self._av_mod.reference_frequency_sweep_allied_vision.side_effect = RuntimeError("camera unplugged")
        result = run_experiment.run_pipeline("3", "2", _default_params())
        assert result is None
        out = capsys.readouterr().out
        assert "stopped unexpectedly" in out

    def test_successful_sweep_still_returns_results(self):
        # Confirms the try/except added around the sweep call does not
        # swallow a normal, successful result.
        result = run_experiment.run_pipeline("1", "1", _default_params())
        assert result == {100.0: None}

    def test_unknown_camera_choice_returns_none(self, capsys):
        result = run_experiment.run_pipeline("9", "1", _default_params())
        assert result is None
        out = capsys.readouterr().out
        assert "Unknown camera choice" in out


# ===========================================================================
# main() — Ctrl+C during any question should exit quietly, not crash
# ===========================================================================

class TestMainKeyboardInterrupt:
    def test_keyboard_interrupt_exits_cleanly(self, capsys):
        with patch.object(run_experiment, "_run", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                run_experiment.main()
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "Cancelled" in out

    def test_normal_run_does_not_trigger_cancel_message(self, capsys):
        with patch.object(run_experiment, "_run"):
            run_experiment.main()
        out = capsys.readouterr().out
        assert "Cancelled" not in out


# ===========================================================================
# show_results() — matplotlib display fallback
# ===========================================================================

def _tiny_image():
    return np.zeros((10, 10), dtype=np.uint8)


class TestShowResults:
    def test_no_results_prints_message_and_returns(self, capsys):
        run_experiment.show_results({}, "unused_dir")
        out = capsys.readouterr().out
        assert "No results to display" in out

    def test_matplotlib_not_installed_falls_back(self, capsys, tmp_path):
        with patch.dict(sys.modules, {"matplotlib.pyplot": None}):
            run_experiment.show_results({100.0: _tiny_image()}, str(tmp_path))
        out = capsys.readouterr().out
        assert "matplotlib not installed" in out
        assert str(tmp_path) in out

    def test_saves_grid_image_and_opens_viewer_on_success(self, tmp_path, capsys):
        results = {100.0: _tiny_image(), 200.0: _tiny_image()}
        with patch("matplotlib.pyplot.show"):
            run_experiment.show_results(results, str(tmp_path))
        out = capsys.readouterr().out
        assert "Results grid saved to" in out
        assert "Viewer open" in out
        assert list(tmp_path.glob("sweep_results_*.png"))

    def test_viewer_crash_is_caught_and_grid_is_still_reported(self, tmp_path, capsys):
        results = {100.0: _tiny_image()}
        with patch("matplotlib.pyplot.show", side_effect=RuntimeError("no display found")):
            run_experiment.show_results(results, str(tmp_path))
        out = capsys.readouterr().out
        assert "Could not open the interactive viewer" in out
        assert "no display found" in out
        assert "Your results are safe" in out
        # The grid PNG must have been saved before the viewer was attempted.
        assert list(tmp_path.glob("sweep_results_*.png"))


# ===========================================================================
# build_grid_figure() — the display-free half show_results() and
# run_experiment_gui.py's ResultsPage both build on
# ===========================================================================

class TestBuildGridFigure:
    def test_returns_figure_and_saved_path(self, tmp_path):
        results = {100.0: _tiny_image(), 200.0: _tiny_image()}
        fig, path = run_experiment.build_grid_figure(results, str(tmp_path))
        assert fig is not None
        assert os.path.exists(path)
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_does_not_display_anything(self, tmp_path):
        # A pure-build function must never try to open a window — patching
        # plt.show() to raise proves it's never called.
        results = {100.0: _tiny_image()}
        with patch("matplotlib.pyplot.show", side_effect=AssertionError("should not be called")):
            fig, path = run_experiment.build_grid_figure(results, str(tmp_path))
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_one_subplot_per_frequency(self, tmp_path):
        results = {100.0: _tiny_image(), 200.0: _tiny_image(), 300.0: _tiny_image()}
        fig, _ = run_experiment.build_grid_figure(results, str(tmp_path))
        visible_axes = [ax for ax in fig.get_axes() if ax.get_visible()]
        assert len(visible_axes) == len(results)
        import matplotlib.pyplot as plt
        plt.close(fig)

    def test_show_results_uses_the_same_saved_file_build_grid_figure_would(self, tmp_path):
        # show_results() must not duplicate build_grid_figure()'s drawing
        # logic — calling it directly should produce the exact same kind
        # of saved file show_results() reports.
        results = {150.0: _tiny_image()}
        with patch("matplotlib.pyplot.show"):
            run_experiment.show_results(results, str(tmp_path))
        saved = list(tmp_path.glob("sweep_results_*.png"))
        assert len(saved) == 1
