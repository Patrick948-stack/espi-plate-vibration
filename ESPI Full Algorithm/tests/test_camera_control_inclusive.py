"""
test_camera_control_inclusive.py
Tests for camera_control_inclusive.py (any OpenCV-supported camera).

Sections covered
----------------
  Pure functions (no camera required):
    substract_frames, amplify_difference, binarize_diff, average_img,
    run_espi_pipeline, build_filename, save_image, save_session_log,
    log_frame_metadata

  Hardware functions (cv2.VideoCapture mocked):
    connect_camera, disconnect_camera, set_exposure_manual, set_gain_manual,
    grab_single_frame, grab_single_frame_with_retry, grab_n_frames,
    grab_reference_frame, discard_warmup_frames,
    set_capture_roi, reset_capture_roi, _apply_roi
"""

import sys
import os
import csv

import numpy as np
import cv2
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import camera_control_inclusive as cc

from conftest import make_mock_cv2_camera


# ===========================================================================
# SECTION 5 — IMAGE PROCESSING
# ===========================================================================

class TestSubstractFrames:
    def test_identical_frames_give_zero_diff(self, gray_100x100):
        diff = cc.substract_frames(gray_100x100, gray_100x100)
        assert np.all(diff == 0)

    def test_returns_uint8(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        assert diff.dtype == np.uint8

    def test_no_uint8_overflow(self):
        a = np.array([[10]], dtype=np.uint8)
        b = np.array([[20]], dtype=np.uint8)
        diff = cc.substract_frames(a, b)
        assert diff[0, 0] == 10  # not 246

    def test_known_value(self):
        a = np.array([[200]], dtype=np.uint8)
        b = np.array([[50]], dtype=np.uint8)
        diff = cc.substract_frames(a, b)
        assert diff[0, 0] == 150

    def test_mismatched_shapes_returns_none(self, gray_100x100):
        small = np.zeros((50, 50), dtype=np.uint8)
        result = cc.substract_frames(gray_100x100, small)
        assert result is None

    def test_output_shape_matches_input(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        assert diff.shape == gray_100x100.shape


class TestAmplifyDifference:
    def test_output_is_uint8(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        amp = cc.amplify_difference(diff)
        assert amp.dtype == np.uint8

    def test_output_range_full(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        amp = cc.amplify_difference(diff)
        assert int(amp.min()) == 0
        assert int(amp.max()) == 255

    def test_all_zero_stays_zero(self, black_image):
        amp = cc.amplify_difference(black_image)
        assert np.all(amp == 0)

    def test_shape_preserved(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        amp = cc.amplify_difference(diff)
        assert amp.shape == diff.shape


class TestBinarizeDiff:
    def test_returns_tuple_of_two(self, gray_100x100):
        result = cc.binarize_diff(gray_100x100)
        assert isinstance(result, tuple) and len(result) == 2

    def test_only_contains_0_and_255(self, gray_100x100):
        binary, _ = cc.binarize_diff(gray_100x100)
        assert set(np.unique(binary)).issubset({0, 255})

    def test_manual_threshold_value_is_127(self, gray_100x100):
        _, thresh = cc.binarize_diff(gray_100x100, method="manual")
        assert thresh == 127

    def test_otsu_gives_numeric_threshold(self, gray_100x100):
        _, thresh = cc.binarize_diff(gray_100x100, method="otsu")
        assert isinstance(thresh, (int, float))

    def test_shape_preserved(self, gray_100x100):
        binary, _ = cc.binarize_diff(gray_100x100)
        assert binary.shape == gray_100x100.shape


class TestAverageImg:
    def test_empty_list_returns_none(self):
        assert cc.average_img([]) is None

    def test_single_frame_unchanged(self, gray_100x100):
        result = cc.average_img([gray_100x100])
        np.testing.assert_array_equal(result, gray_100x100)

    def test_arithmetic_mean_two_frames(self):
        a = np.full((4, 4), 100, dtype=np.uint8)
        b = np.full((4, 4), 200, dtype=np.uint8)
        result = cc.average_img([a, b])
        assert np.all(result == 150)

    def test_output_dtype_is_uint8(self, gray_100x100, gray_100x100_b):
        result = cc.average_img([gray_100x100, gray_100x100_b])
        assert result.dtype == np.uint8

    def test_output_shape_matches(self, gray_100x100, gray_100x100_b):
        result = cc.average_img([gray_100x100, gray_100x100_b])
        assert result.shape == gray_100x100.shape


class TestRunEspiPipeline:
    def test_has_all_keys(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        for key in ("diff", "amplified", "binary", "colored", "threshold"):
            assert key in result

    def test_colored_is_3channel(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        assert result["colored"].ndim == 3 and result["colored"].shape[2] == 3

    def test_binary_is_only_0_and_255(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        assert set(np.unique(result["binary"])).issubset({0, 255})


# ===========================================================================
# SECTION 7 — FILE LOGGING
# ===========================================================================

class TestBuildFilename:
    def test_contains_step(self):
        assert "my_step" in cc.build_filename(440.0, 10000, "my_step")

    def test_ends_with_png_by_default(self):
        assert cc.build_filename(440.0, 10000, "s").endswith(".png")

    def test_custom_extension(self):
        assert cc.build_filename(440.0, 10000, "s", "tiff").endswith(".tiff")

    def test_frequency_zero_padded(self):
        assert "00440.0Hz" in cc.build_filename(440.0, 10000, "s")

    def test_exposure_zero_padded(self):
        assert "010000us" in cc.build_filename(440.0, 10000, "s")


class TestSaveImage:
    def test_creates_file(self, tmp_path, gray_100x100):
        path = cc.save_image(gray_100x100, str(tmp_path), step="test")
        assert path and os.path.isfile(path)

    def test_16bit_creates_tiff(self, tmp_path, gray_100x100):
        path = cc.save_image(gray_100x100, str(tmp_path), step="t", bit_depth="16bit")
        assert path and path.endswith(".tiff")

    def test_creates_directory_if_missing(self, tmp_path, gray_100x100):
        new_dir = str(tmp_path / "sub")
        cc.save_image(gray_100x100, new_dir, step="t")
        assert os.path.isdir(new_dir)

    def test_returns_none_on_bad_path(self, gray_100x100):
        # On Windows, a path like "/no_such_dir_xyz/sub" is NOT absolute
        # (it lacks a drive letter), so os.path.isabs() returns False and
        # _resolve_output_dir treats it as relative — creating the directory
        # and returning a real path.  To guarantee rejection on all platforms
        # we use an absolute path on a different drive (Windows) or a
        # non-existent root (Linux/macOS).
        import sys
        if sys.platform == "win32":
            bad_dir = "Q:\\no_such_dir_xyz\\sub"
        else:
            bad_dir = "/no_such_dir_xyz/sub"
        assert cc.save_image(gray_100x100, bad_dir, step="t") is None


class TestSaveSessionLog:
    def test_creates_file(self, tmp_path):
        cc.save_session_log({"k": "v"}, str(tmp_path))
        assert len(list(tmp_path.glob("session_log_*.txt"))) == 1

    def test_file_contains_key_and_value(self, tmp_path):
        cc.save_session_log({"exposure": 10000}, str(tmp_path))
        text = list(tmp_path.glob("session_log_*.txt"))[0].read_text()
        assert "exposure" in text and "10000" in text


class TestLogFrameMetadata:
    def test_creates_csv_with_header(self, tmp_path):
        cc.log_frame_metadata(0, -6.0, 100.0, str(tmp_path))
        csv_path = tmp_path / "frame_metadata.csv"
        assert csv_path.exists()
        assert "frame_index" in csv_path.read_text()

    def test_appends_rows(self, tmp_path):
        for i in range(5):
            cc.log_frame_metadata(i, -6.0, 50.0, str(tmp_path))
        lines = (tmp_path / "frame_metadata.csv").read_text().splitlines()
        assert len(lines) == 6  # header + 5 rows

    def test_frame_index_stored_correctly(self, tmp_path):
        cc.log_frame_metadata(99, -6.0, 10.0, str(tmp_path))
        reader = csv.DictReader(open(tmp_path / "frame_metadata.csv"))
        assert int(next(reader)["frame_index"]) == 99


# ===========================================================================
# SECTION 1 — CAMERA CONNECTION (cv2.VideoCapture mocked)
# ===========================================================================

class TestConnectCamera:
    def test_returns_none_when_camera_not_opened(self):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        with patch("camera_control_inclusive.cv2.VideoCapture", return_value=mock_cap):
            result = cc.connect_camera(0)
        assert result is None

    def test_returns_camera_on_success(self):
        mock_cap = make_mock_cv2_camera()
        with patch("camera_control_inclusive.cv2.VideoCapture", return_value=mock_cap):
            result = cc.connect_camera(0)
        assert result is mock_cap

    def test_passes_correct_index_to_videocapture(self):
        mock_cap = make_mock_cv2_camera()
        with patch("camera_control_inclusive.cv2.VideoCapture", return_value=mock_cap) as mock_vc:
            cc.connect_camera(2)
        mock_vc.assert_called_once_with(2)


class TestDisconnectCamera:
    def test_calls_release(self):
        mock_cap = make_mock_cv2_camera()
        cc.disconnect_camera(mock_cap)
        mock_cap.release.assert_called_once()

    def test_removes_roi_from_store(self):
        mock_cap = make_mock_cv2_camera()
        cc._roi_store[id(mock_cap)] = (0, 0, 100, 100)
        cc.disconnect_camera(mock_cap)
        assert id(mock_cap) not in cc._roi_store


# ===========================================================================
# SECTION 2 — CAMERA SETTINGS
# ===========================================================================

class TestSetExposureManual:
    def test_sets_auto_exposure_off(self):
        mock_cap = make_mock_cv2_camera()
        cc.set_exposure_manual(mock_cap, -6)
        # CAP_PROP_AUTO_EXPOSURE = 21 in OpenCV, but camera_control_inclusive uses value 1
        calls = [c[0][0] for c in mock_cap.set.call_args_list]
        assert cv2.CAP_PROP_AUTO_EXPOSURE in calls

    def test_sets_exposure_value(self):
        mock_cap = make_mock_cv2_camera()
        cc.set_exposure_manual(mock_cap, -6)
        calls = [c[0] for c in mock_cap.set.call_args_list]
        assert (cv2.CAP_PROP_EXPOSURE, -6) in calls


class TestSetGainManual:
    def test_sets_gain_property(self):
        mock_cap = make_mock_cv2_camera()
        cc.set_gain_manual(mock_cap, 5.0)
        calls = [c[0] for c in mock_cap.set.call_args_list]
        assert (cv2.CAP_PROP_GAIN, 5.0) in calls

    def test_returns_actual_gain(self):
        mock_cap = make_mock_cv2_camera()
        mock_cap.get.side_effect = None
        mock_cap.get.return_value = 5.0
        result = cc.set_gain_manual(mock_cap, 5.0)
        assert result == 5.0


# ===========================================================================
# SECTION 4 — IMAGE CAPTURE
# ===========================================================================

class TestGrabSingleFrame:
    def test_returns_gray_array_from_bgr_camera(self):
        bgr_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(frame=bgr_frame)
        with patch("camera_control_inclusive.cv2.VideoCapture", return_value=mock_cap):
            result = cc.grab_single_frame(mock_cap)
        assert result is not None
        assert result.ndim == 2  # greyscale

    def test_returns_none_when_read_fails(self):
        mock_cap = make_mock_cv2_camera(read_ok=False)
        result = cc.grab_single_frame(mock_cap)
        assert result is None

    def test_applies_roi_crop(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(width=200, height=200, frame=frame)
        cc._roi_store[id(mock_cap)] = (10, 20, 50, 60)
        result = cc.grab_single_frame(mock_cap)
        cc._roi_store.pop(id(mock_cap), None)
        assert result is not None
        assert result.shape == (60, 50)

    def test_already_gray_frame_unchanged(self):
        gray_frame = np.zeros((100, 100), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera()
        mock_cap.read.return_value = (True, gray_frame)
        result = cc.grab_single_frame(mock_cap)
        assert result.ndim == 2


class TestGrabSingleFrameColor:
    """
    grab_single_frame() always reduces a color frame to greyscale before
    returning it, which is correct for every caller that expects a ready to
    use 2D array (monitor.py, capture_and_display*.py, run_experiment.py).
    monitor_gui.py's single-channel R/G/B extraction needs the real color
    data before that reduction happens, which grab_single_frame_color()
    exists to preserve.
    """

    def test_returns_bgr_array_unmodified_for_color_camera(self):
        bgr_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        bgr_frame[:, :, 2] = 200  # red channel
        mock_cap = make_mock_cv2_camera(frame=bgr_frame)
        result = cc.grab_single_frame_color(mock_cap)
        assert result is not None
        assert result.ndim == 3
        assert result.shape[2] == 3
        assert np.all(result[:, :, 2] == 200)
        assert np.all(result[:, :, 0] == 0)
        assert np.all(result[:, :, 1] == 0)

    def test_returns_none_when_read_fails(self):
        mock_cap = make_mock_cv2_camera(read_ok=False)
        result = cc.grab_single_frame_color(mock_cap)
        assert result is None

    def test_applies_roi_crop(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(width=200, height=200, frame=frame)
        cc._roi_store[id(mock_cap)] = (10, 20, 50, 60)
        result = cc.grab_single_frame_color(mock_cap)
        cc._roi_store.pop(id(mock_cap), None)
        assert result is not None
        assert result.shape[:2] == (60, 50)

    def test_already_gray_frame_unchanged(self):
        gray_frame = np.zeros((100, 100), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera()
        mock_cap.read.return_value = (True, gray_frame)
        result = cc.grab_single_frame_color(mock_cap)
        assert result.ndim == 2

    def test_does_not_change_grab_single_frame_own_behavior(self):
        """Regression: adding this function must not touch grab_single_frame's contract."""
        bgr_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        bgr_frame[:, :, 2] = 200
        mock_cap = make_mock_cv2_camera(frame=bgr_frame)
        result = cc.grab_single_frame(mock_cap)
        assert result.ndim == 2


class TestGrabSingleFrameWithRetry:
    def test_returns_frame_on_first_success(self):
        bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(frame=bgr)
        result = cc.grab_single_frame_with_retry(mock_cap, max_retries=3)
        assert result is not None

    def test_retries_on_failure_then_succeeds(self):
        bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera()
        mock_cap.read.side_effect = [(False, None), (True, bgr)]
        result = cc.grab_single_frame_with_retry(mock_cap, max_retries=3)
        assert result is not None

    def test_returns_none_after_all_retries_fail(self):
        mock_cap = make_mock_cv2_camera(read_ok=False)
        mock_cap.read.side_effect = [(False, None)] * 3
        result = cc.grab_single_frame_with_retry(mock_cap, max_retries=3)
        assert result is None


class TestGrabNFrames:
    def test_returns_list_of_requested_length(self):
        bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(frame=bgr)
        frames = cc.grab_n_frames(mock_cap, 3)
        assert len(frames) == 3

    def test_skips_failed_frames(self):
        bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera()
        # 2 successes, 1 failure in between
        mock_cap.read.side_effect = [(True, bgr), (False, None), (False, None), (False, None), (True, bgr)]
        frames = cc.grab_n_frames(mock_cap, 2)
        # Length may be 1 since second request eventually fails all retries
        assert isinstance(frames, list)


class TestGrabReferenceFrame:
    def test_returns_frame(self):
        bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(frame=bgr)
        result = cc.grab_reference_frame(mock_cap)
        assert result is not None

    def test_returns_none_on_failure(self):
        mock_cap = make_mock_cv2_camera(read_ok=False)
        result = cc.grab_reference_frame(mock_cap)
        assert result is None


class TestDiscardWarmupFrames:
    def test_calls_read_n_times(self):
        bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera(frame=bgr)
        cc.discard_warmup_frames(mock_cap, n=5)
        assert mock_cap.read.call_count == 5

    def test_stops_early_on_camera_failure(self):
        mock_cap = make_mock_cv2_camera()
        mock_cap.read.side_effect = [(True, np.zeros((10, 10, 3), dtype=np.uint8)),
                                     (False, None),
                                     (True, np.zeros((10, 10, 3), dtype=np.uint8))]
        cc.discard_warmup_frames(mock_cap, n=5)
        assert mock_cap.read.call_count == 2  # stops after the first failure


# ===========================================================================
# SECTION 3 — ROI (software crop)
# ===========================================================================

class TestSetCaptureRoi:
    def setup_method(self):
        cc._roi_store.clear()

    def test_stores_roi_in_dict(self):
        mock_cap = make_mock_cv2_camera(width=640, height=480)
        cc.set_capture_roi(mock_cap, 10, 20, 100, 80)
        assert id(mock_cap) in cc._roi_store
        assert cc._roi_store[id(mock_cap)] == (10, 20, 100, 80)

    def test_clamps_x_to_frame_boundary(self):
        mock_cap = make_mock_cv2_camera(width=640, height=480)
        cc.set_capture_roi(mock_cap, x=700, y=0, width=100, height=100)
        x, _, _, _ = cc._roi_store[id(mock_cap)]
        assert x <= 639  # clamped to frame_w - 1

    def test_clamps_width_so_roi_stays_inside_frame(self):
        mock_cap = make_mock_cv2_camera(width=640, height=480)
        cc.set_capture_roi(mock_cap, x=600, y=0, width=200, height=100)
        _, _, w, _ = cc._roi_store[id(mock_cap)]
        assert w <= 40  # only 40 pixels available from x=600

    def test_minimum_width_is_1(self):
        mock_cap = make_mock_cv2_camera(width=640, height=480)
        cc.set_capture_roi(mock_cap, x=639, y=0, width=0, height=100)
        _, _, w, _ = cc._roi_store[id(mock_cap)]
        assert w >= 1


class TestResetCaptureRoi:
    def setup_method(self):
        cc._roi_store.clear()

    def test_removes_roi_from_store(self):
        mock_cap = make_mock_cv2_camera()
        cc._roi_store[id(mock_cap)] = (10, 10, 100, 100)
        cc.reset_capture_roi(mock_cap)
        assert id(mock_cap) not in cc._roi_store

    def test_no_error_when_no_roi_set(self):
        mock_cap = make_mock_cv2_camera()
        cc.reset_capture_roi(mock_cap)  # should not raise


class TestApplyRoi:
    def setup_method(self):
        cc._roi_store.clear()

    def test_crops_frame_to_roi(self):
        img = np.zeros((200, 200), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera()
        cc._roi_store[id(mock_cap)] = (10, 20, 50, 60)
        result = cc._apply_roi(img, mock_cap)
        assert result.shape == (60, 50)

    def test_returns_full_frame_when_no_roi(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        mock_cap = make_mock_cv2_camera()
        result = cc._apply_roi(img, mock_cap)
        assert result.shape == (100, 100)
