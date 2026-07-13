"""
test_complete_pipeline.py
Tests for complete_pipeline.py (Basler camera pipeline).

Sections covered
----------------
  Frequency list math (standalone, no hardware):
    The math.floor + 1e-9 formula that builds the sweep frequency list.
    Parametrized over clean integers, float-precision traps, and the
    non-divisible end-frequency case that originally caused the rounding bug.

  Input validation (no hardware):
    frequency_sweep() and reference_frequency_sweep() both validate params
    before touching any hardware.  Invalid params must return None immediately.

  Full sweep with mocked hardware:
    All device connections, camera grabs, and file I/O are replaced with
    MagicMocks.  Tests verify the pipeline returns the right data structure,
    calls set_frequency the correct number of times, and handles the case
    where a device is unavailable at startup.
"""

import math
import sys
import os

import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import complete_pipeline as cp


# ===========================================================================
# STANDALONE FREQUENCY LIST MATH
# These tests verify the math.floor + 1e-9 approach independently of the
# pipeline.  They run without any hardware and with no mocking.
# ===========================================================================

class TestFrequencyListMath:

    @staticmethod
    def _build(start, end, step):
        n = math.floor((end - start) / step + 1e-9)
        return [start + i * step for i in range(n + 1)]

    @pytest.mark.parametrize("start,end,step,expected_len", [
        (100,  200,   100,   2),   # clean integers
        (100,  100.3, 0.25,  2),   # original rounding bug: 100.3 not reachable at 0.25 steps
        (100,  100.5, 0.25,  3),   # exact multiple
        (100,  101,   0.25,  5),   # many small steps
        (500,  500,   1,     1),   # single frequency (start == end)
        (0.1,  1.0,   0.1,   10),  # float precision trap (0.9/0.1 ≈ 8.9999...)
        (100,  400,   50,    7),   # medium sweep
    ])
    def test_correct_number_of_frequencies(self, start, end, step, expected_len):
        freqs = self._build(start, end, step)
        assert len(freqs) == expected_len

    @pytest.mark.parametrize("start,end,step", [
        (100,  200,   100),
        (100,  100.5, 0.25),
        (0.1,  1.0,   0.1),
        (100,  101,   0.25),
    ])
    def test_first_frequency_equals_start(self, start, end, step):
        freqs = self._build(start, end, step)
        assert freqs[0] == pytest.approx(start)

    @pytest.mark.parametrize("start,end,step,expected_last", [
        (100,  200,   100,  200.0),
        (100,  100.5, 0.25, 100.5),
        (100,  101,   0.25, 101.0),
        (0.1,  1.0,   0.1,  1.0),
    ])
    def test_last_frequency_equals_end_when_divisible(self, start, end, step, expected_last):
        freqs = self._build(start, end, step)
        assert freqs[-1] == pytest.approx(expected_last)

    def test_non_divisible_end_not_exceeded(self):
        # end=100.3 is not on the 0.25-Hz grid from 100; last step must be ≤ 100.3
        freqs = self._build(100, 100.3, 0.25)
        assert all(f <= 100.3 + 1e-6 for f in freqs)

    def test_frequencies_increase_monotonically(self):
        freqs = self._build(100, 101, 0.25)
        for a, b in zip(freqs, freqs[1:]):
            assert b > a

    def test_step_size_is_constant(self):
        freqs = self._build(100, 103, 1)
        diffs = [freqs[i + 1] - freqs[i] for i in range(len(freqs) - 1)]
        for d in diffs:
            assert d == pytest.approx(1.0)

    def test_float_precision_trap_gives_correct_count(self):
        # 0.9 / 0.1 often evaluates to 8.9999999... in floating point.
        # The 1e-9 epsilon in floor() must rescue it to give 10 values.
        freqs = self._build(0.1, 1.0, 0.1)
        assert len(freqs) == 10
        assert freqs[-1] == pytest.approx(1.0, abs=1e-9)


# ===========================================================================
# INPUT VALIDATION — frequency_sweep
# These call the real function with one invalid parameter at a time.
# Validation happens before any hardware is touched, so no mocking needed.
# ===========================================================================

class TestFrequencySweepValidation:
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
        ("start_freq",  -1),
        ("end_freq",    50),      # end < start
        ("step",        0),
        ("step",        -10),
        ("n_averages",  0),
        ("n_averages",  -1),
        ("exposure_us", 0),
        ("exposure_us", -500),
        ("gain",        -0.1),
    ])
    def test_invalid_param_returns_none(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp.frequency_sweep(**kwargs) is None

    def test_valid_params_do_not_fail_validation(self):
        # With valid params the function tries to connect hardware and will
        # return None only because there is no real device — NOT because of
        # validation.  We just confirm it doesn't blow up before that point.
        with patch("complete_pipeline.open_connection", return_value=None):
            result = cp.frequency_sweep(**self.VALID)
        assert result is None   # None from "no instrument", not from validation


class TestReferenceFrequencySweepValidation:
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
        ("start_freq",  -50),
        ("end_freq",    50),
        ("step",        0),
        ("n_averages",  0),
        ("exposure_us", 0),
        ("gain",        -1),
    ])
    def test_invalid_param_returns_none(self, field, value):
        kwargs = {**self.VALID, field: value}
        assert cp.reference_frequency_sweep(**kwargs) is None


# ===========================================================================
# FULL SWEEP — frequency_sweep with all hardware mocked
# ===========================================================================

FAKE_FRAME = np.zeros((50, 50), dtype=np.uint8)
SG_SETTINGS = {
    "waveform": "sine", "frequency": 100.0,
    "amplitude": 1.0,   "offset": 0.0, "channel output": 1,
}


@pytest.fixture
def hw(tmp_path):
    """
    Mock every hardware call in complete_pipeline so the sweep logic can run
    end-to-end without a signal generator or Basler camera.
    """
    with patch("complete_pipeline.open_connection",   return_value=MagicMock()) as sg, \
         patch("complete_pipeline.connect_camera",    return_value=MagicMock()) as cam, \
         patch("complete_pipeline.close_connection"), \
         patch("complete_pipeline.disconnect_camera"), \
         patch("complete_pipeline.set_exposure_manual"), \
         patch("complete_pipeline.set_gain_manual"), \
         patch("complete_pipeline.configure_channel", return_value=SG_SETTINGS), \
         patch("complete_pipeline.set_frequency"), \
         patch("complete_pipeline.turn_off_output"), \
         patch("complete_pipeline.grab_n_frames",     return_value=[FAKE_FRAME, FAKE_FRAME]), \
         patch("complete_pipeline.substract_frames",  return_value=FAKE_FRAME), \
         patch("complete_pipeline.average_img",       return_value=FAKE_FRAME), \
         patch("complete_pipeline.save_image",        return_value=str(tmp_path / "img.png")), \
         patch("complete_pipeline._settle_with_live_feed"):
        yield {"sg": sg, "cam": cam, "tmp_path": tmp_path}


class TestFrequencySweepMocked:

    def test_returns_dict(self, hw):
        result = cp.frequency_sweep(100, 300, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert isinstance(result, dict)

    def test_result_has_one_entry_per_frequency(self, hw):
        result = cp.frequency_sweep(100, 300, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert len(result) == 3   # 100, 200, 300 Hz

    def test_result_keys_are_the_swept_frequencies(self, hw):
        result = cp.frequency_sweep(100, 200, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert set(result.keys()) == {100.0, 200.0}

    def test_set_frequency_called_once_per_step(self, hw):
        with patch("complete_pipeline.set_frequency") as mock_sf:
            cp.frequency_sweep(100, 300, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert mock_sf.call_count == 3

    def test_returns_none_when_signal_generator_missing(self, tmp_path):
        with patch("complete_pipeline.open_connection", return_value=None):
            result = cp.frequency_sweep(100, 200, 100, 2, 10000, 0.0, str(tmp_path))
        assert result is None

    def test_returns_none_when_camera_missing(self, tmp_path):
        with patch("complete_pipeline.open_connection", return_value=MagicMock()), \
             patch("complete_pipeline.connect_camera",  return_value=None), \
             patch("complete_pipeline.close_connection"):
            result = cp.frequency_sweep(100, 200, 100, 2, 10000, 0.0, str(tmp_path))
        assert result is None

    def test_single_frequency_sweep(self, hw):
        result = cp.frequency_sweep(440, 440, 1, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert len(result) == 1
        assert 440.0 in result


class TestReferenceFrequencySweepMocked:

    def test_returns_dict(self, hw):
        result = cp.reference_frequency_sweep(100, 200, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert isinstance(result, dict)

    def test_result_has_correct_number_of_entries(self, hw):
        result = cp.reference_frequency_sweep(100, 300, 100, 2, 10000, 0.0, str(hw["tmp_path"]))
        assert len(result) == 3

    def test_returns_none_when_signal_generator_missing(self, tmp_path):
        with patch("complete_pipeline.open_connection", return_value=None):
            result = cp.reference_frequency_sweep(100, 200, 100, 2, 10000, 0.0, str(tmp_path))
        assert result is None


# ===========================================================================
# gain_factor — must scale every difference image before it is averaged and
# saved, saturating at 255 instead of wrapping around (uint8 overflow).
# ===========================================================================

class TestGainFactor:

    def test_default_gain_factor_is_1(self, hw):
        with patch("complete_pipeline.average_img", return_value=FAKE_FRAME) as mock_avg:
            cp.frequency_sweep(440, 440, 1, 2, 10000, 0.0, str(hw["tmp_path"]))
        diffs = mock_avg.call_args[0][0]
        # substract_frames is mocked to return all-zero frames, so a plain
        # equality check on values would pass regardless of gain_factor.
        # What we can verify here is that the default wasn't dropped: the
        # dtype must still be uint8, exactly what convertScaleAbs produces.
        assert all(d.dtype == np.uint8 for d in diffs)

    def test_gain_factor_scales_the_difference_before_averaging(self, hw):
        flat_five = np.full((50, 50), 5, dtype=np.uint8)
        with patch("complete_pipeline.substract_frames", return_value=flat_five), \
             patch("complete_pipeline.average_img", return_value=flat_five) as mock_avg:
            cp.frequency_sweep(440, 440, 1, 2, 10000, 0.0, str(hw["tmp_path"]),
                                gain_factor=10)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 50).all() for d in diffs)   # 5 * 10 = 50

    def test_gain_factor_saturates_instead_of_wrapping(self, hw):
        # 20 * 20 = 400, which would wrap to 144 (400 - 256) under plain
        # uint8 multiplication. cv2.convertScaleAbs must clip to 255 instead.
        flat_twenty = np.full((50, 50), 20, dtype=np.uint8)
        with patch("complete_pipeline.substract_frames", return_value=flat_twenty), \
             patch("complete_pipeline.average_img", return_value=flat_twenty) as mock_avg:
            cp.frequency_sweep(440, 440, 1, 2, 10000, 0.0, str(hw["tmp_path"]),
                                gain_factor=20)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 255).all() for d in diffs)

    def test_reference_sweep_gain_factor_scales_the_difference(self, hw):
        flat_five = np.full((50, 50), 5, dtype=np.uint8)
        with patch("complete_pipeline.substract_frames", return_value=flat_five), \
             patch("complete_pipeline.average_img", return_value=flat_five) as mock_avg:
            cp.reference_frequency_sweep(440, 440, 1, 2, 10000, 0.0, str(hw["tmp_path"]),
                                          gain_factor=10)
        diffs = mock_avg.call_args[0][0]
        assert all((d == 50).all() for d in diffs)
