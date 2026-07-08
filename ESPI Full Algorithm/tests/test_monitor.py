"""
test_monitor.py
Tests for monitor.py — the interactive camera picker + live preview launcher.

Sections covered
----------------
  ask_positive_float()
    Wraps run_experiment.ask() with a "> 0" check. Tests cover: default
    value, rejecting zero, rejecting negative numbers, and retrying until a
    valid value is typed.

  choose_camera() / choose_camera_index() / choose_camera_settings()
    Interactive prompts. Tests cover: defaults, valid choices, invalid
    choices being rejected and re-asked, and Basler skipping the camera
    index prompt entirely (camera_control.py has no index parameter).

  confirm_settings()
    Smoke-test that the confirmation screen shows the right camera name,
    shows an index only for non-Basler cameras, and returns True/False
    based on the y/n answer.

  launch_monitor()
    Imports the right capture_and_display module and calls its main() with
    correctly converted kwargs. Tests cover: exposure unit conversion per
    camera type, a missing SDK (ImportError) for each of the three camera
    types, and unexpected exceptions raised from inside main().

  main()
    Full orchestration smoke tests: normal run, and cancelling at the
    confirmation prompt.
"""

import math
import sys
import os
import types
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import monitor


# ===========================================================================
# ask_positive_float()
# ===========================================================================

class TestAskPositiveFloat:
    def test_returns_default_on_empty_input(self):
        with patch("builtins.input", return_value=""):
            result = monitor.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(0.01)

    def test_accepts_typed_positive_value(self):
        with patch("builtins.input", return_value="0.5"):
            result = monitor.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(0.5)

    def test_rejects_zero_then_accepts_positive(self):
        with patch("builtins.input", side_effect=["0", "0.02"]):
            result = monitor.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(0.02)

    def test_rejects_negative_then_accepts_positive(self):
        with patch("builtins.input", side_effect=["-5", "20"]):
            result = monitor.ask_positive_float("gain_factor", default=20)
        assert result == pytest.approx(20)

    def test_prints_explanation_when_rejecting(self, capsys):
        with patch("builtins.input", side_effect=["-1", "1"]):
            monitor.ask_positive_float("gain_factor", default=20)
        out = capsys.readouterr().out
        assert "must be greater than 0" in out

    def test_non_numeric_input_is_rejected_by_underlying_ask(self):
        # ask() itself retries on a bad cast before ask_positive_float ever
        # sees the value, so a non-numeric answer never reaches our check.
        with patch("builtins.input", side_effect=["not_a_number", "3.0"]):
            result = monitor.ask_positive_float("Exposure (s)", default=0.01)
        assert result == pytest.approx(3.0)


# ===========================================================================
# choose_camera()
# ===========================================================================

class TestChooseCamera:
    def test_default_is_webcam(self):
        with patch("builtins.input", return_value=""):
            result = monitor.choose_camera()
        assert result == "2"

    @pytest.mark.parametrize("choice", ["1", "2", "3"])
    def test_accepts_each_valid_choice(self, choice):
        with patch("builtins.input", return_value=choice):
            result = monitor.choose_camera()
        assert result == choice

    def test_rejects_invalid_choice_then_accepts(self):
        with patch("builtins.input", side_effect=["9", "1"]):
            result = monitor.choose_camera()
        assert result == "1"


# ===========================================================================
# choose_camera_index()
# ===========================================================================

class TestChooseCameraIndex:
    def test_basler_returns_zero_without_asking(self):
        with patch("builtins.input") as mock_input:
            result = monitor.choose_camera_index("1")
        assert result == 0
        mock_input.assert_not_called()

    def test_webcam_default_index_is_zero(self):
        with patch("builtins.input", return_value=""):
            result = monitor.choose_camera_index("2")
        assert result == 0

    def test_webcam_accepts_typed_index(self):
        with patch("builtins.input", return_value="1"):
            result = monitor.choose_camera_index("2")
        assert result == 1

    def test_allied_accepts_typed_index(self):
        with patch("builtins.input", return_value="2"):
            result = monitor.choose_camera_index("3")
        assert result == 2

    def test_negative_index_is_rejected_then_retried(self):
        with patch("builtins.input", side_effect=["-1", "0"]):
            result = monitor.choose_camera_index("2")
        assert result == 0


# ===========================================================================
# choose_camera_settings()
# ===========================================================================

class TestChooseCameraSettings:
    def test_defaults(self):
        with patch("builtins.input", return_value=""):
            result = monitor.choose_camera_settings()
        assert result["exposure_s"] == pytest.approx(0.01)
        assert result["gain_db"] == pytest.approx(0.0)
        assert result["gain_factor"] == pytest.approx(20)
        assert result["graph_type"] is None

    def test_typed_values(self):
        with patch("builtins.input", side_effect=["0.05", "2.5", "10", "histogram"]):
            result = monitor.choose_camera_settings()
        assert result["exposure_s"] == pytest.approx(0.05)
        assert result["gain_db"] == pytest.approx(2.5)
        assert result["gain_factor"] == pytest.approx(10)
        assert result["graph_type"] == "histogram"

    def test_zero_exposure_is_rejected_then_retried(self):
        with patch("builtins.input", side_effect=["0", "0.02", "0.0", "5", "none"]):
            result = monitor.choose_camera_settings()
        assert result["exposure_s"] == pytest.approx(0.02)
        assert result["gain_factor"] == pytest.approx(5)

    def test_gain_db_may_be_zero_or_negative(self):
        # Unlike exposure and gain_factor, gain in dB is a valid setting at
        # or below zero (0 dB = no amplification), so it must not be routed
        # through ask_positive_float.
        with patch("builtins.input", side_effect=["0.01", "-3.0", "20", "none"]):
            result = monitor.choose_camera_settings()
        assert result["gain_db"] == pytest.approx(-3.0)

    def test_3d_graph_choice(self):
        with patch("builtins.input", side_effect=["0.01", "0.0", "20", "3d"]):
            result = monitor.choose_camera_settings()
        assert result["graph_type"] == "3d"

    def test_invalid_graph_choice_is_rejected_then_retried(self):
        with patch("builtins.input",
                   side_effect=["0.01", "0.0", "20", "bar-chart", "histogram"]):
            result = monitor.choose_camera_settings()
        assert result["graph_type"] == "histogram"


# ===========================================================================
# confirm_settings()
# ===========================================================================

class TestConfirmSettings:
    SETTINGS = dict(exposure_s=0.01, gain_db=1.0, gain_factor=20)

    def test_basler_does_not_show_index(self, capsys):
        with patch("builtins.input", return_value="n"):
            monitor.confirm_settings("1", 0, self.SETTINGS)
        out = capsys.readouterr().out
        assert "Basler" in out
        assert "index" not in out

    def test_webcam_shows_index(self, capsys):
        with patch("builtins.input", return_value="n"):
            monitor.confirm_settings("2", 1, self.SETTINGS)
        out = capsys.readouterr().out
        assert "USB / webcam" in out
        assert "index 1" in out

    def test_allied_shows_index(self, capsys):
        with patch("builtins.input", return_value="n"):
            monitor.confirm_settings("3", 2, self.SETTINGS)
        out = capsys.readouterr().out
        assert "Allied Vision" in out
        assert "index 2" in out

    def test_returns_true_on_y(self):
        with patch("builtins.input", return_value="y"):
            result = monitor.confirm_settings("2", 0, self.SETTINGS)
        assert result is True

    def test_returns_false_on_n(self):
        with patch("builtins.input", return_value="n"):
            result = monitor.confirm_settings("2", 0, self.SETTINGS)
        assert result is False


# ===========================================================================
# launch_monitor()
# ===========================================================================

class TestLaunchMonitorImportError:
    """Each camera type must name its own SDK in the install instructions."""

    def test_basler_missing_sdk_message(self, capsys):
        with patch("importlib.import_module", side_effect=ImportError("no pypylon")):
            result = monitor.launch_monitor("1", 0, TestConfirmSettings.SETTINGS)
        assert result is False
        out = capsys.readouterr().out
        assert "pip install pypylon" in out

    def test_webcam_missing_sdk_message(self, capsys):
        with patch("importlib.import_module", side_effect=ImportError("no cv2")):
            result = monitor.launch_monitor("2", 0, TestConfirmSettings.SETTINGS)
        assert result is False
        out = capsys.readouterr().out
        assert "pip install opencv-python" in out

    def test_allied_missing_sdk_message(self, capsys):
        with patch("importlib.import_module", side_effect=ImportError("no vmbpy")):
            result = monitor.launch_monitor("3", 0, TestConfirmSettings.SETTINGS)
        assert result is False
        out = capsys.readouterr().out
        assert "vmbpy" in out
        assert "VmbPy" in out


class TestLaunchMonitorDispatch:
    """Verify each camera type's main() is called with correctly converted keyword arguments (kwargs)."""

    def test_basler_converts_seconds_to_microseconds(self):
        mock_module = MagicMock()
        with patch("importlib.import_module", return_value=mock_module):
            monitor.launch_monitor(
                "1", 0, dict(exposure_s=0.01, gain_db=1.5, gain_factor=20)
            )
        kwargs = mock_module.main.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(10_000.0)
        assert kwargs["gain_db"] == pytest.approx(1.5)
        assert kwargs["gain_factor"] == pytest.approx(20)
        assert "camera_index" not in kwargs
        # settings dict has no "graph_type" key here (older-style caller) —
        # must default to None instead of raising KeyError.
        assert kwargs["graph_type"] is None

    def test_webcam_converts_seconds_to_log2_scale(self):
        mock_module = MagicMock()
        with patch("importlib.import_module", return_value=mock_module):
            monitor.launch_monitor(
                "2", 1, dict(exposure_s=0.015625, gain_db=0.0, gain_factor=20)
            )
        kwargs = mock_module.main.call_args[1]
        assert kwargs["exposure"] == pytest.approx(-6.0, abs=0.01)
        assert kwargs["camera_index"] == 1
        assert kwargs["gain"] == pytest.approx(0.0)
        assert kwargs["gain_factor"] == pytest.approx(20)
        assert kwargs["graph_type"] is None

    def test_allied_converts_seconds_to_microseconds(self):
        mock_module = MagicMock()
        with patch("importlib.import_module", return_value=mock_module):
            monitor.launch_monitor(
                "3", 2, dict(exposure_s=0.02, gain_db=3.0, gain_factor=15)
            )
        kwargs = mock_module.main.call_args[1]
        assert kwargs["exposure_us"] == pytest.approx(20_000.0)
        assert kwargs["camera_index"] == 2
        assert kwargs["gain"] == pytest.approx(3.0)
        assert kwargs["gain_factor"] == pytest.approx(15)
        assert kwargs["graph_type"] is None

    def test_returns_true_on_success(self):
        mock_module = MagicMock()
        with patch("importlib.import_module", return_value=mock_module):
            result = monitor.launch_monitor("2", 0, TestConfirmSettings.SETTINGS)
        assert result is True

    @pytest.mark.parametrize("camera_choice,index", [("1", 0), ("2", 0), ("3", 0)])
    def test_graph_type_forwarded_when_present(self, camera_choice, index):
        mock_module = MagicMock()
        settings = dict(exposure_s=0.01, gain_db=0.0, gain_factor=20,
                        graph_type="histogram")
        with patch("importlib.import_module", return_value=mock_module):
            monitor.launch_monitor(camera_choice, index, settings)
        kwargs = mock_module.main.call_args[1]
        assert kwargs["graph_type"] == "histogram"


class TestLaunchMonitorErrorHandling:
    def test_value_error_from_main_is_caught(self, capsys):
        mock_module = MagicMock()
        mock_module.main.side_effect = ValueError("math domain error")
        with patch("importlib.import_module", return_value=mock_module):
            result = monitor.launch_monitor("2", 0, TestConfirmSettings.SETTINGS)
        assert result is False
        out = capsys.readouterr().out
        assert "Invalid exposure value" in out

    def test_unexpected_exception_from_main_is_caught(self, capsys):
        mock_module = MagicMock()
        mock_module.main.side_effect = RuntimeError("camera unplugged mid-stream")
        with patch("importlib.import_module", return_value=mock_module):
            result = monitor.launch_monitor("1", 0, TestConfirmSettings.SETTINGS)
        assert result is False
        out = capsys.readouterr().out
        assert "stopped unexpectedly" in out
        assert "camera unplugged mid-stream" in out

    def test_camera_none_inside_main_does_not_raise(self):
        # main() itself prints a message and returns None when no camera is
        # found (see capture_and_display.py) — launch_monitor should treat
        # that as a normal, successful call rather than an error.
        mock_module = MagicMock()
        mock_module.main.return_value = None
        with patch("importlib.import_module", return_value=mock_module):
            result = monitor.launch_monitor("1", 0, TestConfirmSettings.SETTINGS)
        assert result is True


# ===========================================================================
# main() — full orchestration
# ===========================================================================

class TestMain:
    def test_cancelling_at_confirmation_exits_without_launching(self):
        # camera=2 (default), index=default 0, exposure/gain/gain_factor/
        # graph_type defaults, then "n" at the confirmation prompt.
        with patch("builtins.input",
                   side_effect=["", "", "", "", "", "", "n"]), \
             patch.object(monitor, "launch_monitor") as mock_launch, \
             patch.object(monitor, "clear"), \
             patch.object(monitor, "header"):
            with pytest.raises(SystemExit) as exc_info:
                monitor.main()
        assert exc_info.value.code == 0
        mock_launch.assert_not_called()

    def test_confirming_calls_launch_monitor_with_chosen_settings(self):
        # camera "1" (Basler, no index prompt), exposure 0.02, gain 1.0,
        # gain_factor 15, graph_type "histogram", then "y" to confirm.
        with patch("builtins.input",
                   side_effect=["1", "0.02", "1.0", "15", "histogram", "y"]), \
             patch.object(monitor, "launch_monitor") as mock_launch, \
             patch.object(monitor, "clear"), \
             patch.object(monitor, "header"):
            monitor.main()
        mock_launch.assert_called_once()
        camera_choice, camera_index, settings = mock_launch.call_args[0]
        assert camera_choice == "1"
        assert camera_index == 0
        assert settings["exposure_s"] == pytest.approx(0.02)
        assert settings["gain_db"] == pytest.approx(1.0)
        assert settings["gain_factor"] == pytest.approx(15)
        assert settings["graph_type"] == "histogram"
