"""
test_complete_pipeline_allied_vision.py
Tests for complete_pipeline_allied_vision.py (Allied Vision / vmbpy pipeline).

vmbpy requires the VimbaX native runtime which is not available without
hardware, so the entire vmbpy package is stubbed out in sys.modules before
the module under test is imported. The same technique used in
test_camera_control_allied_vision.py.

Sections covered
----------------
  _validate_sweep_params() (no hardware):
    The shared validation helper.  Tested directly since it is a pure
    function that returns True/False with no hardware contact.

  frequency_sweep_allied_vision() validation (no hardware):
    The public function delegates to _validate_sweep_params, so invalid
    params must return None before any device is opened.

  reference_frequency_sweep_allied_vision() validation (no hardware):
    Same check for the reference-subtraction variant.

  Full sweep with mocked hardware:
    All Allied Vision camera calls, signal generator calls, live feed
    windows, and file I/O are replaced with MagicMocks.  Tests verify
    the sweep returns the expected data structure and calls set_frequency
    the correct number of times.
"""

import sys
import os
import types

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub vmbpy BEFORE importing the module under test (same pattern as
# test_camera_control_allied_vision.py).
# ---------------------------------------------------------------------------

class _FrameStatus:
    Complete = "Complete"

class _VimbaFeatureError(Exception):
    pass

class _VmbTimeout(Exception):
    pass

_vmbpy_stub = types.ModuleType("vmbpy")
_vmbpy_stub.VmbSystem       = MagicMock()
_vmbpy_stub.FrameStatus     = _FrameStatus
_vmbpy_stub.VmbFeatureError = _VimbaFeatureError
_vmbpy_stub.VmbTimeout      = _VmbTimeout
_vmbpy_stub.PixelFormat     = MagicMock()
sys.modules["vmbpy"] = _vmbpy_stub
sys.modules.pop("camera_control_allied_vision",    None)
sys.modules.pop("complete_pipeline_allied_vision", None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import complete_pipeline_allied_vision as cp


# ===========================================================================
# _validate_sweep_params — pure validation helper
# ===========================================================================

class TestValidateSweepParams:
    VALID = dict(
        start_freq  = 100.0,
        end_freq    = 200.0,
        step        = 100.0,
        n_averages  = 5,
        exposure_us = 10_000.0,
        amplitude   = 1.0,
        channel     = 1,
    )

    def test_valid_params_return_true(self):
        assert cp._validate_sweep_params(**self.VALID) is True

    @pytest.mark.parametrize("field,value", [
        ("start_freq",  0),
        ("start_freq",  -100),
        ("end_freq",    50),       # end < start
        ("step",        0),
        ("step",        -5),
        ("n_averages",  0),
        ("n_averages",  -1),
        ("exposure_us", 0),
        ("exposure_us", -1000),
        ("amplitude",   0),
        ("amplitude",   -1),
        ("channel",     0),
        ("channel",     3),
    ])
    def test_invalid_param_returns_false(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp._validate_sweep_params(**kwargs) is False

    def test_channel_1_is_valid(self):
        assert cp._validate_sweep_params(**{**self.VALID, "channel": 1}) is True

    def test_channel_2_is_valid(self):
        assert cp._validate_sweep_params(**{**self.VALID, "channel": 2}) is True

    def test_equal_start_and_end_is_valid(self):
        # Single-frequency sweep: start == end is allowed
        assert cp._validate_sweep_params(**{**self.VALID, "end_freq": 100.0}) is True


# ===========================================================================
# INPUT VALIDATION — public sweep functions
# ===========================================================================

class TestFrequencySweepAVValidation:
    VALID = dict(
        start_freq  = 100.0,
        end_freq    = 200.0,
        step        = 100.0,
        n_averages  = 5,
        exposure_us = 10_000.0,
        gain        = 0.0,
        output_dir  = "out",
    )

    @pytest.mark.parametrize("field,value", [
        ("start_freq",  0),
        ("end_freq",    50),
        ("step",        0),
        ("n_averages",  0),
        ("exposure_us", 0),
    ])
    def test_invalid_param_returns_none(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp.frequency_sweep_allied_vision(**kwargs) is None

    def test_valid_params_reach_hardware_stage(self):
        # Validation passes → the function tries to open devices.
        # We intercept at _connect_devices to avoid actual hardware calls.
        with patch.object(cp, "_connect_devices", return_value=(None, None, "")):
            result = cp.frequency_sweep_allied_vision(**self.VALID)
        assert result is None   # None because _connect_devices returned None instr


class TestReferenceFrequencySweepAVValidation:
    VALID = dict(
        start_freq  = 100.0,
        end_freq    = 200.0,
        step        = 100.0,
        n_averages  = 5,
        exposure_us = 10_000.0,
        gain        = 0.0,
        output_dir  = "out",
    )

    @pytest.mark.parametrize("field,value", [
        ("start_freq",  0),
        ("end_freq",    50),
        ("step",        0),
        ("n_averages",  0),
        ("exposure_us", 0),
    ])
    def test_invalid_param_returns_none(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp.reference_frequency_sweep_allied_vision(**kwargs) is None


# ===========================================================================
# FULL SWEEP — frequency_sweep_allied_vision with all hardware mocked
# ===========================================================================

FAKE_FRAME  = np.zeros((50, 50), dtype=np.uint8)
SG_SETTINGS = {
    "waveform": "sine", "frequency": 100.0,
    "amplitude": 1.0,   "offset": 0.0, "channel output": 1,
}


def _mock_cam_info():
    return {"model": "MockAV", "id": "DEV_MOCK",
            "exposure_us": 10000.0, "gain_db": 0.0,
            "width": 50, "height": 50}


@pytest.fixture
def hw(tmp_path):
    """
    Stub all hardware interactions in complete_pipeline_allied_vision so the
    sweep logic runs without a physical Allied Vision camera or signal generator.
    """
    with patch.object(cp, "_connect_devices",
                      return_value=(MagicMock(), MagicMock(), "MOCK_SG")), \
         patch.object(cp, "show_live_feed_from_camera"), \
         patch.object(cp, "discard_warmup_frames"), \
         patch.object(cp, "_lock_camera_settings",
                      return_value=(10_000.0, 0.0)), \
         patch.object(cp, "_configure_signal_generator",
                      return_value=SG_SETTINGS), \
         patch.object(cp, "_save_metadata"), \
         patch.object(cp, "set_frequency"), \
         patch.object(cp, "_settle_with_live_feed"), \
         patch.object(cp, "grab_n_frames",
                      return_value=[FAKE_FRAME, FAKE_FRAME]), \
         patch.object(cp, "substract_frames",  return_value=FAKE_FRAME), \
         patch.object(cp, "average_img",        return_value=FAKE_FRAME), \
         patch.object(cp, "amplify_difference", return_value=FAKE_FRAME), \
         patch.object(cp, "save_image",         return_value=str(tmp_path / "img.png")), \
         patch.object(cp, "_cleanup"), \
         patch.object(cp, "_print_sweep_summary"):
        yield {"tmp_path": tmp_path}


class TestFrequencySweepAVMocked:

    def test_returns_dict(self, hw):
        result = cp.frequency_sweep_allied_vision(100, 200, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert isinstance(result, dict)

    def test_result_has_one_entry_per_frequency(self, hw):
        result = cp.frequency_sweep_allied_vision(100, 300, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert len(result) == 3

    def test_result_keys_are_swept_frequencies(self, hw):
        result = cp.frequency_sweep_allied_vision(100, 200, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert 100.0 in result and 200.0 in result

    def test_set_frequency_called_once_per_step(self, hw):
        with patch.object(cp, "set_frequency") as mock_sf:
            cp.frequency_sweep_allied_vision(100, 300, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert mock_sf.call_count == 3

    def test_single_frequency_sweep(self, hw):
        result = cp.frequency_sweep_allied_vision(440, 440, 1, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert len(result) == 1

    def test_non_divisible_end_does_not_exceed_range(self, hw):
        with patch.object(cp, "set_frequency") as mock_sf:
            cp.frequency_sweep_allied_vision(100, 100.3, 0.25, 1, 10000, 0.0, str(hw["tmp_path"]))
        called_freqs = [c[0][1] for c in mock_sf.call_args_list]
        assert all(f <= 100.3 + 1e-6 for f in called_freqs)

    def test_returns_none_when_connect_devices_fails(self, tmp_path):
        with patch.object(cp, "_connect_devices", return_value=(None, None, "")):
            result = cp.frequency_sweep_allied_vision(100, 200, 100, 2, 10000, 0.0, str(tmp_path))
        assert result is None


class TestReferenceFrequencySweepAVMocked:

    @pytest.fixture
    def hw_ref(self, tmp_path):
        with patch.object(cp, "_connect_devices",
                          return_value=(MagicMock(), MagicMock(), "MOCK_SG")), \
             patch.object(cp, "show_live_feed_from_camera"), \
             patch.object(cp, "discard_warmup_frames"), \
             patch.object(cp, "_lock_camera_settings",
                          return_value=(10_000.0, 0.0)), \
             patch.object(cp, "_configure_signal_generator",
                          return_value=SG_SETTINGS), \
             patch.object(cp, "_save_metadata"), \
             patch.object(cp, "set_frequency"), \
             patch.object(cp, "_settle_with_live_feed"), \
             patch.object(cp, "grab_reference_frame",  return_value=FAKE_FRAME), \
             patch.object(cp, "grab_n_frames",
                          return_value=[FAKE_FRAME]), \
             patch.object(cp, "substract_frames",  return_value=FAKE_FRAME), \
             patch.object(cp, "average_img",        return_value=FAKE_FRAME), \
             patch.object(cp, "amplify_difference", return_value=FAKE_FRAME), \
             patch.object(cp, "save_image",         return_value=str(tmp_path / "img.png")), \
             patch.object(cp, "_cleanup"), \
             patch.object(cp, "_print_sweep_summary"):
            yield {"tmp_path": tmp_path}

    def test_returns_dict(self, hw_ref):
        result = cp.reference_frequency_sweep_allied_vision(
            100, 200, 100, 2, 10000, 0.0, str(hw_ref["tmp_path"]))
        assert isinstance(result, dict)

    def test_result_has_correct_number_of_entries(self, hw_ref):
        result = cp.reference_frequency_sweep_allied_vision(
            100, 300, 100, 2, 10000, 0.0, str(hw_ref["tmp_path"]))
        assert len(result) == 3

    def test_returns_none_when_connect_devices_fails(self, tmp_path):
        with patch.object(cp, "_connect_devices", return_value=(None, None, "")):
            result = cp.reference_frequency_sweep_allied_vision(
                100, 200, 100, 2, 10000, 0.0, str(tmp_path))
        assert result is None

    def test_gain_factor_scales_the_difference_before_averaging(self, hw_ref):
        flat_five = np.full((50, 50), 5, dtype=np.uint8)
        with patch.object(cp, "substract_frames", return_value=flat_five), \
             patch.object(cp, "average_img", return_value=flat_five) as mock_avg:
            cp.reference_frequency_sweep_allied_vision(
                440, 440, 1, 2, 10000, 0.0, str(hw_ref["tmp_path"]), gain_factor=10)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 50).all() for d in diffs)   # 5 * 10 = 50


# ===========================================================================
# gain_factor (pair-subtraction mode) — must scale every difference image
# before it is averaged and saved, saturating at 255 instead of wrapping
# around (uint8 overflow).
# ===========================================================================

class TestGainFactorAV:

    def test_scales_the_difference_before_averaging(self, hw):
        flat_five = np.full((50, 50), 5, dtype=np.uint8)
        with patch.object(cp, "substract_frames", return_value=flat_five), \
             patch.object(cp, "average_img", return_value=flat_five) as mock_avg:
            cp.frequency_sweep_allied_vision(440, 440, 1, 2, 10000, 0.0,
                                             str(hw["tmp_path"]), gain_factor=10)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 50).all() for d in diffs)   # 5 * 10 = 50

    def test_saturates_instead_of_wrapping(self, hw):
        # 20 * 20 = 400, which would wrap to 144 under plain uint8 multiplication.
        flat_twenty = np.full((50, 50), 20, dtype=np.uint8)
        with patch.object(cp, "substract_frames", return_value=flat_twenty), \
             patch.object(cp, "average_img", return_value=flat_twenty) as mock_avg:
            cp.frequency_sweep_allied_vision(440, 440, 1, 2, 10000, 0.0,
                                             str(hw["tmp_path"]), gain_factor=20)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 255).all() for d in diffs)


# ===========================================================================
# skip_live_feed parameter
# ===========================================================================

class TestSkipLiveFeedAV:

    def test_skip_true_does_not_call_show_live_feed(self, hw):
        with patch.object(cp, "show_live_feed_from_camera") as mock_feed:
            cp.frequency_sweep_allied_vision(100, 200, 100, 2, 10000, 0.0,
                                             str(hw["tmp_path"]),
                                             skip_live_feed=True)
        mock_feed.assert_not_called()

    def test_skip_false_calls_show_live_feed(self, hw):
        with patch.object(cp, "show_live_feed_from_camera") as mock_feed:
            cp.frequency_sweep_allied_vision(100, 200, 100, 2, 10000, 0.0,
                                             str(hw["tmp_path"]),
                                             skip_live_feed=False)
        mock_feed.assert_called_once()
