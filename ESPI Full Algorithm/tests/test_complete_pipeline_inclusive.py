"""
test_complete_pipeline_inclusive.py
Tests for complete_pipeline_inclusive.py (OpenCV / any-camera pipeline).

Sections covered
----------------
  Input validation (no hardware):
    frequency_sweep_inclusive() and reference_frequency_sweep_inclusive()
    validate parameters before connecting to anything.  Invalid params
    return None immediately, so no mocking is needed for these tests.

  Full sweep with mocked hardware:
    All device connections (signal generator + OpenCV camera), the live
    feed window, warmup frame discards, and file I/O are replaced with
    MagicMocks.  Tests check that the sweep returns the expected data
    structure and calls set_frequency the right number of times.
"""

import sys
import os
from contextlib import ExitStack

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import complete_pipeline_inclusive as cp


# ===========================================================================
# INPUT VALIDATION — frequency_sweep_inclusive
# ===========================================================================

class TestFrequencySweepInclusiveValidation:
    VALID = dict(
        start_freq = 100.0,
        end_freq   = 200.0,
        step       = 100.0,
        n_averages = 5,
        exposure   = -6.0,
        gain       = 0.0,
        output_dir = "out",
    )

    @pytest.mark.parametrize("field,value", [
        ("start_freq", 0),
        ("start_freq", -100),
        ("end_freq",   50),        # end < start
        ("step",       0),
        ("step",       -1),
        ("n_averages", 0),
        ("n_averages", -3),
    ])
    def test_invalid_param_returns_none(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp.frequency_sweep_inclusive(**kwargs) is None

    def test_valid_params_attempt_hardware(self):
        # Should reach the hardware connection stage, not fail on validation.
        with patch("complete_pipeline_inclusive.open_connection", return_value=None):
            result = cp.frequency_sweep_inclusive(**self.VALID)
        assert result is None  # None from missing instrument, not validation


class TestReferenceFrequencySweepInclusiveValidation:
    VALID = dict(
        start_freq = 100.0,
        end_freq   = 200.0,
        step       = 100.0,
        n_averages = 5,
        exposure   = -6.0,
        gain       = 0.0,
        output_dir = "out",
    )

    @pytest.mark.parametrize("field,value", [
        ("start_freq", 0),
        ("start_freq", -1),
        ("end_freq",   50),
        ("step",       0),
        ("n_averages", 0),
    ])
    def test_invalid_param_returns_none(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp.reference_frequency_sweep_inclusive(**kwargs) is None


# ===========================================================================
# FULL SWEEP — frequency_sweep_inclusive with all hardware mocked
# ===========================================================================

FAKE_FRAME = np.zeros((50, 50), dtype=np.uint8)
SG_SETTINGS = {
    "waveform": "sine", "frequency": 100.0,
    "amplitude": 1.0,   "offset": 0.0, "channel output": 1,
}
FAKE_CAM_INFO = {
    "model": "MockCam", "index": 0,
    "width": 640, "height": 480, "fps": 30.0,
    "exposure": -6.0, "gain": 0.0, "backend": "mock",
}


def _hw_patches(tmp_path, *, include_reference_grab=False):
    """Return the list of patches that replace all hardware in the inclusive pipeline."""
    patches = [
        patch("complete_pipeline_inclusive.open_connection",         return_value=MagicMock()),
        patch("complete_pipeline_inclusive.get_identity",            return_value="MOCK_SG"),
        patch("complete_pipeline_inclusive.connect_camera",          return_value=MagicMock()),
        patch("complete_pipeline_inclusive.show_live_feed_from_camera"),
        patch("complete_pipeline_inclusive.discard_warmup_frames"),
        patch("complete_pipeline_inclusive.set_exposure_manual",     return_value=-6.0),
        patch("complete_pipeline_inclusive.set_gain_manual",         return_value=0.0),
        patch("complete_pipeline_inclusive.get_camera_info",         return_value=FAKE_CAM_INFO),
        patch("complete_pipeline_inclusive.configure_channel",       return_value=SG_SETTINGS),
        patch("complete_pipeline_inclusive.set_frequency",           return_value=100.0),
        patch("complete_pipeline_inclusive.turn_off_output"),
        patch("complete_pipeline_inclusive.disconnect_camera"),
        patch("complete_pipeline_inclusive.close_connection"),
        patch("complete_pipeline_inclusive.grab_n_frames",           return_value=[FAKE_FRAME, FAKE_FRAME]),
        patch("complete_pipeline_inclusive.substract_frames",        return_value=FAKE_FRAME),
        patch("complete_pipeline_inclusive.average_img",             return_value=FAKE_FRAME),
        patch("complete_pipeline_inclusive.amplify_difference",      return_value=FAKE_FRAME),
        patch("complete_pipeline_inclusive.save_image",              return_value=str(tmp_path / "img.png")),
        patch("complete_pipeline_inclusive.save_session_log"),
        patch("complete_pipeline_inclusive.cv2.imshow"),
        patch("complete_pipeline_inclusive.cv2.waitKey",             return_value=0),
        patch("complete_pipeline_inclusive._settle_with_live_feed"),
    ]
    if include_reference_grab:
        patches.append(
            patch("complete_pipeline_inclusive.grab_reference_frame", return_value=FAKE_FRAME)
        )
    return patches


@pytest.fixture
def hw(tmp_path):
    """
    Replace every external dependency in complete_pipeline_inclusive so the
    sweep logic runs end-to-end without any physical hardware.
    """
    with ExitStack() as stack:
        for p in _hw_patches(tmp_path):
            stack.enter_context(p)
        yield {"tmp_path": tmp_path}


class TestFrequencySweepInclusiveMocked:

    def test_returns_dict(self, hw):
        result = cp.frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0, str(hw["tmp_path"]))
        assert isinstance(result, dict)

    def test_result_has_one_entry_per_frequency(self, hw):
        result = cp.frequency_sweep_inclusive(100, 300, 100, 2, -6, 0.0, str(hw["tmp_path"]))
        assert len(result) == 3

    def test_result_keys_are_swept_frequencies(self, hw):
        result = cp.frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0, str(hw["tmp_path"]))
        assert 100.0 in result and 200.0 in result

    def test_set_frequency_called_once_per_step(self, hw):
        with patch("complete_pipeline_inclusive.set_frequency") as mock_sf:
            cp.frequency_sweep_inclusive(100, 300, 100, 2, -6, 0.0, str(hw["tmp_path"]))
        assert mock_sf.call_count == 3

    def test_single_frequency_sweep(self, hw):
        result = cp.frequency_sweep_inclusive(440, 440, 1, 2, -6, 0.0, str(hw["tmp_path"]))
        assert len(result) == 1

    def test_returns_none_when_signal_generator_missing(self, tmp_path):
        with patch("complete_pipeline_inclusive.open_connection", return_value=None):
            result = cp.frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0, str(tmp_path))
        assert result is None

    def test_returns_none_when_camera_missing(self, tmp_path):
        with patch("complete_pipeline_inclusive.open_connection", return_value=MagicMock()), \
             patch("complete_pipeline_inclusive.get_identity",    return_value="SG"), \
             patch("complete_pipeline_inclusive.connect_camera",  return_value=None), \
             patch("complete_pipeline_inclusive.close_connection"):
            result = cp.frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0, str(tmp_path))
        assert result is None

    def test_non_divisible_end_does_not_exceed_range(self, hw):
        # step=0.25 from 100 never lands on 100.3; sweep must stop at 100.25
        with patch("complete_pipeline_inclusive.set_frequency") as mock_sf:
            cp.frequency_sweep_inclusive(100, 100.3, 0.25, 1, -6, 0.0, str(hw["tmp_path"]))
        called_freqs = [c[0][1] for c in mock_sf.call_args_list]
        assert all(f <= 100.3 + 1e-6 for f in called_freqs)


@pytest.fixture
def hw_ref(tmp_path):
    """Hardware mock fixture for reference_frequency_sweep_inclusive."""
    with ExitStack() as stack:
        for p in _hw_patches(tmp_path, include_reference_grab=True):
            stack.enter_context(p)
        # reference sweep grabs only 1 frame per frequency, not 2
        stack.enter_context(
            patch("complete_pipeline_inclusive.grab_n_frames", return_value=[FAKE_FRAME])
        )
        yield {"tmp_path": tmp_path}


class TestReferenceFrequencySweepInclusiveMocked:

    def test_returns_dict(self, hw_ref):
        result = cp.reference_frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0, str(hw_ref["tmp_path"]))
        assert isinstance(result, dict)

    def test_result_has_correct_number_of_entries(self, hw_ref):
        result = cp.reference_frequency_sweep_inclusive(100, 300, 100, 2, -6, 0.0, str(hw_ref["tmp_path"]))
        assert len(result) == 3

    def test_returns_none_when_signal_generator_missing(self, tmp_path):
        with patch("complete_pipeline_inclusive.open_connection", return_value=None):
            result = cp.reference_frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0, str(tmp_path))
        assert result is None


# ===========================================================================
# gain_factor — must scale every difference image before it is averaged and
# saved, saturating at 255 instead of wrapping around (uint8 overflow).
# ===========================================================================

class TestGainFactorInclusive:

    def test_pair_mode_scales_the_difference_before_averaging(self, hw):
        flat_five = np.full((50, 50), 5, dtype=np.uint8)
        with patch("complete_pipeline_inclusive.substract_frames", return_value=flat_five), \
             patch("complete_pipeline_inclusive.average_img", return_value=flat_five) as mock_avg:
            cp.frequency_sweep_inclusive(440, 440, 1, 2, -6, 0.0, str(hw["tmp_path"]),
                                         gain_factor=10)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 50).all() for d in diffs)   # 5 * 10 = 50

    def test_pair_mode_saturates_instead_of_wrapping(self, hw):
        # 20 * 20 = 400, which would wrap to 144 under plain uint8 multiplication.
        flat_twenty = np.full((50, 50), 20, dtype=np.uint8)
        with patch("complete_pipeline_inclusive.substract_frames", return_value=flat_twenty), \
             patch("complete_pipeline_inclusive.average_img", return_value=flat_twenty) as mock_avg:
            cp.frequency_sweep_inclusive(440, 440, 1, 2, -6, 0.0, str(hw["tmp_path"]),
                                         gain_factor=20)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 255).all() for d in diffs)

    def test_reference_mode_scales_the_difference_before_averaging(self, hw_ref):
        flat_five = np.full((50, 50), 5, dtype=np.uint8)
        with patch("complete_pipeline_inclusive.substract_frames", return_value=flat_five), \
             patch("complete_pipeline_inclusive.average_img", return_value=flat_five) as mock_avg:
            cp.reference_frequency_sweep_inclusive(440, 440, 1, 2, -6, 0.0, str(hw_ref["tmp_path"]),
                                                    gain_factor=10)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 50).all() for d in diffs)


# ===========================================================================
# skip_live_feed parameter
# ===========================================================================

class TestSkipLiveFeedInclusive:

    def test_skip_true_does_not_call_show_live_feed(self, hw):
        with patch("complete_pipeline_inclusive.show_live_feed_from_camera") as mock_feed:
            cp.frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0,
                                         str(hw["tmp_path"]), skip_live_feed=True)
        mock_feed.assert_not_called()

    def test_skip_false_calls_show_live_feed(self, hw):
        with patch("complete_pipeline_inclusive.show_live_feed_from_camera") as mock_feed:
            cp.frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0,
                                         str(hw["tmp_path"]), skip_live_feed=False)
        mock_feed.assert_called_once()

    def test_reference_skip_true_does_not_call_show_live_feed(self, hw_ref):
        with patch("complete_pipeline_inclusive.show_live_feed_from_camera") as mock_feed:
            cp.reference_frequency_sweep_inclusive(100, 200, 100, 2, -6, 0.0,
                                                   str(hw_ref["tmp_path"]),
                                                   skip_live_feed=True)
        mock_feed.assert_not_called()
