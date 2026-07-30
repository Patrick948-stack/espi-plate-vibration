"""
test_camera_control_allied_vision.py
Tests for camera_control_allied_vision.py (Allied Vision / vmbpy).

vmbpy requires the VimbaX native runtime which is not available in CI, so the
entire vmbpy package is stubbed out in sys.modules BEFORE the module under
test is imported. This lets us test all logic paths without physical hardware.

Sections covered
----------------
  Pure functions (no camera required):
    substract_frames, amplify_difference, binarize_diff, average_img,
    run_espi_pipeline, build_filename, save_image, save_session_log,
    log_frame_metadata

  Hardware functions (vmbpy + _AVHandle mocked):
    connect_camera, disconnect_camera, set_exposure_manual, set_gain_manual,
    set_capture_roi, reset_capture_roi, grab_single_frame,
    grab_single_frame_with_retry, grab_n_frames, grab_reference_frame,
    discard_warmup_frames
"""

import sys
import os
import types
import csv

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub vmbpy BEFORE importing the module under test.
# The module does:
#   from vmbpy import VmbSystem as Vimba, FrameStatus, VmbFeatureError as VimbaFeatureError
# so every name we set here becomes a module-level name in cc_av.
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

# Now remove any stale import so Python re-runs the module-level code.
sys.modules.pop("camera_control_allied_vision", None)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import camera_control_allied_vision as cc_av

from conftest import make_mock_cv2_camera


# ---------------------------------------------------------------------------
# Helpers for building mock Allied Vision camera handles
# ---------------------------------------------------------------------------

def _make_av_cam(width=1920, height=1200,
                 exp_min=100.0, exp_max=100_000.0,
                 gain_min=0.0, gain_max=24.0):
    """Return a mock Allied Vision Camera object (the raw cam, not the handle)."""
    cam = MagicMock()
    cam.get_name.return_value = "MockAVCam"
    cam.get_id.return_value = "DEV_MOCK"

    cam.Width.get.return_value = width
    cam.WidthMax.get.return_value = width
    cam.Height.get.return_value = height
    cam.HeightMax.get.return_value = height

    cam.ExposureTime.get_range.return_value = (exp_min, exp_max)
    cam.ExposureTime.get.return_value = exp_min
    cam.Gain.get_range.return_value = (gain_min, gain_max)
    cam.Gain.get.return_value = gain_min

    return cam


def _make_handle(cam=None):
    """Return an _AVHandle wrapping a mock Allied Vision camera."""
    if cam is None:
        cam = _make_av_cam()
    handle = cc_av._AVHandle(MagicMock(), cam)
    return handle


def _make_frame(array, status=_FrameStatus.Complete):
    """Return a mock vmbpy Frame that yields the given numpy array."""
    frame = MagicMock()
    frame.get_status.return_value = status
    frame.as_numpy_ndarray.return_value = array
    return frame


# ===========================================================================
# SECTION 5 — IMAGE PROCESSING (pure numpy / cv2)
# ===========================================================================

class TestSubstractFrames:
    def test_identical_frames_give_zeros(self, gray_100x100):
        diff = cc_av.substract_frames(gray_100x100, gray_100x100)
        assert np.all(diff == 0)

    def test_returns_uint8(self, gray_100x100, gray_100x100_b):
        diff = cc_av.substract_frames(gray_100x100, gray_100x100_b)
        assert diff.dtype == np.uint8

    def test_no_uint8_overflow(self):
        a = np.array([[10]], dtype=np.uint8)
        b = np.array([[20]], dtype=np.uint8)
        assert cc_av.substract_frames(a, b)[0, 0] == 10

    def test_mismatched_shapes_returns_none(self, gray_100x100):
        small = np.zeros((50, 50), dtype=np.uint8)
        assert cc_av.substract_frames(gray_100x100, small) is None

    def test_shape_preserved(self, gray_100x100, gray_100x100_b):
        diff = cc_av.substract_frames(gray_100x100, gray_100x100_b)
        assert diff.shape == gray_100x100.shape


class TestAmplifyDifference:
    def test_output_is_uint8_full_range(self, gray_100x100, gray_100x100_b):
        diff = cc_av.substract_frames(gray_100x100, gray_100x100_b)
        amp = cc_av.amplify_difference(diff)
        assert amp.dtype == np.uint8
        assert int(amp.min()) == 0
        assert int(amp.max()) == 255

    def test_all_zero_stays_zero(self, black_image):
        assert np.all(cc_av.amplify_difference(black_image) == 0)


class TestBinarizeDiff:
    def test_output_only_contains_0_and_255(self, gray_100x100):
        binary, _ = cc_av.binarize_diff(gray_100x100)
        assert set(np.unique(binary)).issubset({0, 255})

    def test_manual_threshold_is_127(self, gray_100x100):
        _, thresh = cc_av.binarize_diff(gray_100x100, method="manual")
        assert thresh == 127

    def test_otsu_threshold_is_numeric(self, gray_100x100):
        _, thresh = cc_av.binarize_diff(gray_100x100, method="otsu")
        assert isinstance(thresh, (int, float))


class TestAverageImg:
    def test_empty_list_returns_none(self):
        assert cc_av.average_img([]) is None

    def test_arithmetic_mean(self):
        a = np.full((4, 4), 60, dtype=np.uint8)
        b = np.full((4, 4), 80, dtype=np.uint8)
        result = cc_av.average_img([a, b])
        assert np.all(result == 70)

    def test_output_dtype_is_uint8(self, gray_100x100, gray_100x100_b):
        result = cc_av.average_img([gray_100x100, gray_100x100_b])
        assert result.dtype == np.uint8


class TestRunEspiPipeline:
    def test_keys_present(self, gray_100x100, gray_100x100_b):
        result = cc_av.run_espi_pipeline(gray_100x100, gray_100x100_b)
        for key in ("diff", "amplified", "binary", "colored", "threshold"):
            assert key in result

    def test_colored_is_3_channel(self, gray_100x100, gray_100x100_b):
        result = cc_av.run_espi_pipeline(gray_100x100, gray_100x100_b)
        assert result["colored"].ndim == 3


# ===========================================================================
# SECTION 7 — FILE LOGGING
# ===========================================================================

class TestBuildFilename:
    def test_contains_step_and_extension(self):
        name = cc_av.build_filename(440.0, 10000, "espi")
        assert "espi" in name and name.endswith(".png")

    def test_frequency_zero_padded(self):
        assert "00440.0Hz" in cc_av.build_filename(440.0, 10000, "s")

    def test_custom_extension(self):
        assert cc_av.build_filename(0, 0, "s", "tiff").endswith(".tiff")


class TestSaveImage:
    def test_creates_png_file(self, tmp_path, gray_100x100):
        path = cc_av.save_image(gray_100x100, str(tmp_path), step="t")
        assert path and os.path.isfile(path)

    def test_creates_tiff_for_16bit(self, tmp_path, gray_100x100):
        path = cc_av.save_image(gray_100x100, str(tmp_path), step="t", bit_depth="16bit")
        assert path and path.endswith(".tiff")

    def test_creates_output_dir(self, tmp_path, gray_100x100):
        sub = str(tmp_path / "new_dir")
        cc_av.save_image(gray_100x100, sub, step="t")
        assert os.path.isdir(sub)


class TestSaveSessionLog:
    def test_creates_log_file(self, tmp_path):
        cc_av.save_session_log({"model": "AV"}, str(tmp_path))
        assert len(list(tmp_path.glob("session_log_*.txt"))) == 1

    def test_contains_key_value(self, tmp_path):
        cc_av.save_session_log({"gain": 5.0}, str(tmp_path))
        text = list(tmp_path.glob("session_log_*.txt"))[0].read_text()
        assert "gain" in text and "5.0" in text


class TestLogFrameMetadata:
    def test_creates_csv(self, tmp_path):
        cc_av.log_frame_metadata(0, 10000.0, 128.0, str(tmp_path))
        assert (tmp_path / "frame_metadata.csv").exists()

    def test_appends_rows_correctly(self, tmp_path):
        for i in range(3):
            cc_av.log_frame_metadata(i, 10000.0, 50.0, str(tmp_path))
        lines = (tmp_path / "frame_metadata.csv").read_text().splitlines()
        assert len(lines) == 4  # header + 3

    def test_header_written_once(self, tmp_path):
        cc_av.log_frame_metadata(0, 10000.0, 10.0, str(tmp_path))
        cc_av.log_frame_metadata(1, 10000.0, 20.0, str(tmp_path))
        text = (tmp_path / "frame_metadata.csv").read_text()
        assert text.count("frame_index") == 1


# ===========================================================================
# SECTION 1 — CAMERA CONNECTION
# ===========================================================================

class TestConnectCamera:
    def test_returns_none_when_vimba_not_available(self):
        with patch.object(cc_av, "_VIMBA_AVAILABLE", False):
            result = cc_av.connect_camera()
        assert result is None

    def test_returns_none_when_no_cameras_found(self):
        mock_vimba = MagicMock()
        mock_vimba.get_all_cameras.return_value = []

        with patch.object(cc_av, "_VIMBA_AVAILABLE", True), \
             patch.object(cc_av, "Vimba") as MockVimba:
            MockVimba.get_instance.return_value = mock_vimba
            result = cc_av.connect_camera(0)

        assert result is None

    def test_returns_none_when_index_out_of_range(self):
        cam = _make_av_cam()
        mock_vimba = MagicMock()
        mock_vimba.get_all_cameras.return_value = [cam]

        with patch.object(cc_av, "_VIMBA_AVAILABLE", True), \
             patch.object(cc_av, "Vimba") as MockVimba:
            MockVimba.get_instance.return_value = mock_vimba
            result = cc_av.connect_camera(5)  # only 1 camera present

        assert result is None

    def test_returns_avhandle_on_success(self):
        cam = _make_av_cam()
        mock_vimba = MagicMock()
        mock_vimba.get_all_cameras.return_value = [cam]

        with patch.object(cc_av, "_VIMBA_AVAILABLE", True), \
             patch.object(cc_av, "Vimba") as MockVimba:
            MockVimba.get_instance.return_value = mock_vimba
            result = cc_av.connect_camera(0)

        assert isinstance(result, cc_av._AVHandle)

    def test_forces_pixel_format_to_mono8(self):
        # The camera remembers its own pixel format across reconnects, in its
        # own onboard memory. Without forcing it here, a camera left in some
        # other format by an earlier session would silently stay that way,
        # and every downstream function assumes 0-255 Mono8 data.
        cam = _make_av_cam()
        mock_vimba = MagicMock()
        mock_vimba.get_all_cameras.return_value = [cam]

        with patch.object(cc_av, "_VIMBA_AVAILABLE", True), \
             patch.object(cc_av, "Vimba") as MockVimba:
            MockVimba.get_instance.return_value = mock_vimba
            cc_av.connect_camera(0)

        cam.set_pixel_format.assert_called_once_with(cc_av.PixelFormat.Mono8)


class TestSetPixelFormat:
    """
    vmbpy's own set_pixel_format() needs a member of its PixelFormat type
    (e.g. PixelFormat.Mono8), not a plain string. This was the actual reason
    forcing Mono8 never worked before: the old code passed the string "Mono8"
    straight through, which vmbpy does not accept.
    """

    def test_converts_string_to_pixelformat_member(self):
        cam = _make_av_cam()
        handle = _make_handle(cam)

        cc_av.set_pixel_format(handle, "Mono8")

        cam.set_pixel_format.assert_called_once_with(cc_av.PixelFormat.Mono8)

    def test_camera_rejecting_format_is_caught_and_printed(self, capsys):
        # Simulates the real SDK call failing (e.g. a camera model that
        # doesn't support the requested format) rather than crashing the
        # whole connect_camera() call.
        cam = _make_av_cam()
        cam.set_pixel_format.side_effect = Exception("format not supported")
        handle = _make_handle(cam)

        cc_av.set_pixel_format(handle, "Mono8")

        out = capsys.readouterr().out
        assert "Could not set format" in out


class TestDisconnectCamera:
    def test_calls_exit_on_cam_and_vimba(self):
        cam = _make_av_cam()
        handle = _make_handle(cam)
        cc_av.disconnect_camera(handle)
        cam.__exit__.assert_called()
        handle._vimba.__exit__.assert_called()

    def test_removes_roi_entry(self):
        handle = _make_handle()
        cc_av._roi_store[id(handle)] = (0, 0, 100, 100)
        cc_av.disconnect_camera(handle)
        assert id(handle) not in cc_av._roi_store


# ===========================================================================
# SECTION 2 — CAMERA SETTINGS
# ===========================================================================

class TestSetExposureManual:
    def test_disables_auto_exposure(self):
        handle = _make_handle()
        cc_av.set_exposure_manual(handle, 10000)
        handle.cam.ExposureAuto.set.assert_called_with("Off")

    def test_sets_exposure_value(self):
        handle = _make_handle()
        cc_av.set_exposure_manual(handle, 10000)
        handle.cam.ExposureTime.set.assert_called_with(10000.0)

    def test_clamps_below_minimum(self):
        handle = _make_handle()
        handle.cam.ExposureTime.get_range.return_value = (100.0, 100_000.0)
        cc_av.set_exposure_manual(handle, 1.0)  # below min of 100
        call_val = handle.cam.ExposureTime.set.call_args[0][0]
        assert call_val >= 100.0

    def test_clamps_above_maximum(self):
        handle = _make_handle()
        handle.cam.ExposureTime.get_range.return_value = (100.0, 100_000.0)
        cc_av.set_exposure_manual(handle, 999_999.0)
        call_val = handle.cam.ExposureTime.set.call_args[0][0]
        assert call_val <= 100_000.0

    def test_returns_none_on_exception(self):
        handle = _make_handle()
        handle.cam.ExposureTime.get_range.side_effect = RuntimeError("hw error")
        result = cc_av.set_exposure_manual(handle, 10000)
        assert result is None


class TestSetGainManual:
    def test_disables_auto_gain(self):
        handle = _make_handle()
        cc_av.set_gain_manual(handle, 5.0)
        handle.cam.GainAuto.set.assert_called_with("Off")

    def test_sets_gain_value(self):
        handle = _make_handle()
        cc_av.set_gain_manual(handle, 5.0)
        handle.cam.Gain.set.assert_called_with(5.0)

    def test_clamps_above_maximum(self):
        handle = _make_handle()
        handle.cam.Gain.get_range.return_value = (0.0, 24.0)
        cc_av.set_gain_manual(handle, 100.0)
        call_val = handle.cam.Gain.set.call_args[0][0]
        assert call_val <= 24.0


# ===========================================================================
# SECTION 3 — ROI
# ===========================================================================

class TestSetCaptureRoi:
    def setup_method(self):
        cc_av._roi_store.clear()

    def test_stores_roi_in_dict(self):
        handle = _make_handle(_make_av_cam(width=1920, height=1200))
        cc_av.set_capture_roi(handle, 10, 20, 500, 400)
        assert id(handle) in cc_av._roi_store

    def test_calls_cam_width_and_height_set(self):
        cam = _make_av_cam(width=1920, height=1200)
        handle = _make_handle(cam)
        cc_av.set_capture_roi(handle, 0, 0, 500, 400)
        cam.Width.set.assert_called()
        cam.Height.set.assert_called()

    def test_clamps_to_max_dimensions(self):
        cam = _make_av_cam(width=640, height=480)
        handle = _make_handle(cam)
        cc_av.set_capture_roi(handle, 0, 0, 9999, 9999)
        w_arg = cam.Width.set.call_args[0][0]
        h_arg = cam.Height.set.call_args[0][0]
        assert w_arg <= 640
        assert h_arg <= 480


class TestResetCaptureRoi:
    def setup_method(self):
        cc_av._roi_store.clear()

    def test_removes_roi_from_store(self):
        handle = _make_handle()
        cc_av._roi_store[id(handle)] = (0, 0, 100, 100)
        cc_av.reset_capture_roi(handle)
        assert id(handle) not in cc_av._roi_store

    def test_resets_camera_to_max_dimensions(self):
        cam = _make_av_cam(width=1920, height=1200)
        handle = _make_handle(cam)
        cc_av.reset_capture_roi(handle)
        cam.Width.set.assert_called_with(1920)
        cam.Height.set.assert_called_with(1200)


# ===========================================================================
# SECTION 4 — IMAGE CAPTURE
# ===========================================================================

class TestGrabSingleFrame:
    def test_returns_uint8_array_on_success(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame(handle)
        assert result is not None
        assert result.dtype == np.uint8

    def test_normalises_non_uint8_to_uint8(self):
        img = np.full((10, 10), 4000, dtype=np.uint16)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame(handle)
        assert result is not None
        assert result.dtype == np.uint8
        assert result.max() <= 255

    def test_returns_none_on_incomplete_frame(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        mock_frame = _make_frame(img, status="Incomplete")
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame(handle)
        assert result is None

    def test_returns_none_on_exception(self):
        handle = _make_handle()
        handle.cam.get_frame.side_effect = RuntimeError("hw error")
        result = cc_av.grab_single_frame(handle)
        assert result is None

    def test_squeezes_single_channel_dimension(self):
        img = np.zeros((50, 50, 1), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame(handle)
        assert result.ndim == 2

    def test_applies_roi_crop(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        cc_av._roi_store[id(handle)] = (10, 20, 50, 60)
        result = cc_av.grab_single_frame(handle)
        cc_av._roi_store.pop(id(handle), None)
        assert result is not None
        assert result.shape == (60, 50)


class TestGrabSingleFrameColor:
    """
    grab_single_frame() always reduces a color frame to greyscale via
    to_gray() before returning it. monitor_gui.py's single-channel R/G/B
    extraction needs the real (H, W, 3) BGR data before that reduction
    happens, for a color capable Allied Vision camera (model suffix 'c'),
    which grab_single_frame_color() exists to preserve.
    """

    def test_returns_bgr_array_unmodified_for_color_camera(self):
        bgr_img = np.zeros((50, 50, 3), dtype=np.uint8)
        bgr_img[:, :, 2] = 200  # red channel
        mock_frame = _make_frame(bgr_img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame_color(handle)
        assert result is not None
        assert result.ndim == 3
        assert result.shape[2] == 3
        assert np.all(result[:, :, 2] == 200)

    def test_squeezes_single_channel_mono_dimension(self):
        img = np.zeros((50, 50, 1), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame_color(handle)
        assert result.ndim == 2

    def test_normalises_non_uint8_to_uint8(self):
        img = np.full((10, 10), 4000, dtype=np.uint16)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame_color(handle)
        assert result is not None
        assert result.dtype == np.uint8

    def test_returns_none_on_incomplete_frame(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        mock_frame = _make_frame(img, status="Incomplete")
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame_color(handle)
        assert result is None

    def test_does_not_change_grab_single_frame_own_behavior(self):
        """Regression: adding this function must not touch grab_single_frame's contract."""
        bgr_img = np.zeros((50, 50, 3), dtype=np.uint8)
        bgr_img[:, :, 2] = 200
        mock_frame = _make_frame(bgr_img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame(handle)
        assert result.ndim == 2


class TestGrabSingleFrameWithRetry:
    def test_returns_on_first_success(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        result = cc_av.grab_single_frame_with_retry(handle, max_retries=3)
        assert result is not None

    def test_returns_none_after_all_retries_fail(self):
        handle = _make_handle()
        handle.cam.get_frame.side_effect = RuntimeError("always fails")
        result = cc_av.grab_single_frame_with_retry(handle, max_retries=3)
        assert result is None

    def test_max_retries_calls_get_frame_at_most_n_times(self):
        handle = _make_handle()
        handle.cam.get_frame.side_effect = RuntimeError("fail")
        cc_av.grab_single_frame_with_retry(handle, max_retries=2)
        assert handle.cam.get_frame.call_count == 2


class TestGrabNFrames:
    def test_returns_list_of_n_frames(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        frames = cc_av.grab_n_frames(handle, 3)
        assert len(frames) == 3

    def test_partial_results_when_some_fail(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        good_frame = _make_frame(img)
        handle = _make_handle()
        # First grab succeeds, remaining fail
        handle.cam.get_frame.side_effect = [good_frame] + [RuntimeError("fail")] * 9
        frames = cc_av.grab_n_frames(handle, 2, max_retries=3)
        # We got exactly 1 good frame; 2nd request failed all retries
        assert len(frames) == 1


class TestDiscardWarmupFrames:
    def test_calls_grab_n_times(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        mock_frame = _make_frame(img)
        handle = _make_handle()
        handle.cam.get_frame.return_value = mock_frame
        cc_av.discard_warmup_frames(handle, n=4)
        assert handle.cam.get_frame.call_count >= 4
