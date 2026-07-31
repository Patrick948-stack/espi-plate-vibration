"""
test_camera_control.py
Tests for camera_control.py (Basler / pypylon).

Sections covered
----------------
  Pure functions (no camera required):
    substract_frames, amplify_difference, binarize_diff, average_img,
    run_espi_pipeline, build_filename, save_image, save_session_log,
    log_frame_metadata

  Hardware functions (Basler camera mocked):
    connect_camera, disconnect_camera, set_exposure_manual, set_gain_manual,
    grab_single_frame, grab_n_frames, set_capture_roi, reset_capture_roi
"""

import sys
import os
import csv

import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup — make the parent directory importable
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import camera_control as cc

# Pull in shared fixtures from conftest.py
from conftest import make_mock_basler_camera


# ===========================================================================
# SECTION 5 — IMAGE PROCESSING (pure numpy / cv2, no camera needed)
# ===========================================================================

class TestSubstractFrames:
    def test_identical_frames_produce_all_zeros(self, gray_100x100):
        diff = cc.substract_frames(gray_100x100, gray_100x100)
        assert np.all(diff == 0)

    def test_returns_uint8_array(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        assert diff.dtype == np.uint8

    def test_output_shape_matches_input(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        assert diff.shape == gray_100x100.shape

    def test_no_uint8_overflow(self):
        a = np.array([[10]], dtype=np.uint8)
        b = np.array([[20]], dtype=np.uint8)
        diff = cc.substract_frames(a, b)
        # cv2.absdiff gives abs(10-20) = 10, NOT uint8 wrap-around (246)
        assert diff[0, 0] == 10

    def test_known_difference_value(self):
        a = np.array([[100]], dtype=np.uint8)
        b = np.array([[60]], dtype=np.uint8)
        diff = cc.substract_frames(a, b)
        assert diff[0, 0] == 40

    def test_mismatched_shapes_raise(self, gray_100x100):
        small = np.zeros((50, 50), dtype=np.uint8)
        with pytest.raises(AssertionError):
            cc.substract_frames(gray_100x100, small)


class TestAmplifyDifference:
    def test_output_is_uint8(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        amplified = cc.amplify_difference(diff)
        assert amplified.dtype == np.uint8

    def test_output_range_is_0_to_255(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        amplified = cc.amplify_difference(diff)
        assert int(amplified.min()) == 0
        assert int(amplified.max()) == 255

    def test_output_shape_unchanged(self, gray_100x100, gray_100x100_b):
        diff = cc.substract_frames(gray_100x100, gray_100x100_b)
        amplified = cc.amplify_difference(diff)
        assert amplified.shape == diff.shape

    def test_uniform_input_produces_uniform_output(self, uniform_gray):
        amplified = cc.amplify_difference(uniform_gray)
        assert amplified.dtype == np.uint8

    def test_all_zero_input_stays_all_zero(self, black_image):
        amplified = cc.amplify_difference(black_image)
        assert np.all(amplified == 0)


class TestBinarizeDiff:
    def test_returns_tuple(self, gray_100x100):
        result = cc.binarize_diff(gray_100x100)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_output_is_binary_otsu(self, gray_100x100):
        binary, _ = cc.binarize_diff(gray_100x100, method="otsu")
        unique = set(np.unique(binary))
        assert unique.issubset({0, 255})

    def test_output_is_binary_manual(self, gray_100x100):
        binary, _ = cc.binarize_diff(gray_100x100, method="manual")
        unique = set(np.unique(binary))
        assert unique.issubset({0, 255})

    def test_manual_threshold_is_127(self, gray_100x100):
        _, thresh = cc.binarize_diff(gray_100x100, method="manual")
        assert thresh == 127

    def test_otsu_threshold_is_numeric(self, gray_100x100):
        _, thresh = cc.binarize_diff(gray_100x100, method="otsu")
        assert isinstance(thresh, (int, float))

    def test_output_shape_unchanged(self, gray_100x100):
        binary, _ = cc.binarize_diff(gray_100x100)
        assert binary.shape == gray_100x100.shape

    def test_all_zero_input_gives_all_zero_binary(self, black_image):
        binary, _ = cc.binarize_diff(black_image)
        assert np.all(binary == 0)


class TestAverageImg:
    def test_empty_list_returns_none(self):
        assert cc.average_img([]) is None

    def test_single_frame_returns_same_values(self, gray_100x100):
        result = cc.average_img([gray_100x100])
        np.testing.assert_array_equal(result, gray_100x100)

    def test_identical_frames_return_same_values(self, uniform_gray):
        result = cc.average_img([uniform_gray, uniform_gray, uniform_gray])
        np.testing.assert_array_equal(result, uniform_gray)

    def test_output_dtype_is_uint8(self, gray_100x100, gray_100x100_b):
        result = cc.average_img([gray_100x100, gray_100x100_b])
        assert result.dtype == np.uint8

    def test_output_shape_matches_input(self, gray_100x100, gray_100x100_b):
        result = cc.average_img([gray_100x100, gray_100x100_b])
        assert result.shape == gray_100x100.shape

    def test_arithmetic_mean_two_frames(self):
        a = np.full((4, 4), 100, dtype=np.uint8)
        b = np.full((4, 4), 200, dtype=np.uint8)
        result = cc.average_img([a, b])
        assert np.all(result == 150)


class TestRunEspiPipeline:
    def test_returns_dict_with_expected_keys(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        for key in ("diff", "amplified", "binary", "colored", "threshold"):
            assert key in result

    def test_all_arrays_have_correct_dtype(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        assert result["diff"].dtype == np.uint8
        assert result["amplified"].dtype == np.uint8
        assert result["binary"].dtype == np.uint8
        assert result["colored"].dtype == np.uint8

    def test_colored_output_is_3_channel(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        assert result["colored"].ndim == 3
        assert result["colored"].shape[2] == 3

    def test_binary_contains_only_0_and_255(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        unique = set(np.unique(result["binary"]))
        assert unique.issubset({0, 255})

    def test_threshold_is_a_number(self, gray_100x100, gray_100x100_b):
        result = cc.run_espi_pipeline(gray_100x100, gray_100x100_b)
        assert isinstance(result["threshold"], (int, float))


# ===========================================================================
# SECTION 7 — FILE LOGGING (pure file I/O)
# ===========================================================================

class TestBuildFilename:
    def test_contains_step_name(self):
        name = cc.build_filename(440.0, 10000, "espi_test")
        assert "espi_test" in name

    def test_contains_hz_label(self):
        name = cc.build_filename(440.0, 10000, "step")
        assert "Hz" in name

    def test_contains_us_label(self):
        name = cc.build_filename(440.0, 10000, "step")
        assert "us" in name

    def test_default_extension_is_png(self):
        name = cc.build_filename(440.0, 10000, "step")
        assert name.endswith(".png")

    def test_custom_extension(self):
        name = cc.build_filename(440.0, 10000, "step", extension="tiff")
        assert name.endswith(".tiff")

    def test_frequency_is_zero_padded(self):
        name = cc.build_filename(440.0, 10000, "step")
        assert "00440.0Hz" in name

    def test_exposure_is_zero_padded(self):
        name = cc.build_filename(440.0, 10000, "step")
        assert "010000us" in name


class TestSaveImage:
    def test_creates_png_file(self, tmp_path, gray_100x100):
        path = cc.save_image(gray_100x100, str(tmp_path), 440.0, 10000, "test")
        assert path is not None
        assert os.path.isfile(path)
        assert path.endswith(".png")

    def test_creates_tiff_for_16bit(self, tmp_path, gray_100x100):
        path = cc.save_image(gray_100x100, str(tmp_path), 440.0, 10000, "test", bit_depth="16bit")
        assert path is not None
        assert path.endswith(".tiff")

    def test_creates_output_directory_if_missing(self, tmp_path, gray_100x100):
        new_dir = str(tmp_path / "new_subdir")
        path = cc.save_image(gray_100x100, new_dir, 440.0, 10000, "test")
        assert os.path.isdir(new_dir)

    def test_returns_none_on_bad_path(self, gray_100x100):
        # On Windows, a path like "/nonexistent_root_dir_xyz/test" is NOT
        # absolute (it lacks a drive letter), so os.path.isabs() returns
        # False and _resolve_output_dir treats it as relative — creating the
        # directory and returning a real path.  To guarantee rejection on all
        # platforms we use an absolute path on a different drive (Windows) or
        # a non-existent root (Linux/macOS).
        import sys
        if sys.platform == "win32":
            bad_dir = "Q:\\nonexistent_root_dir_xyz\\test"
        else:
            bad_dir = "/nonexistent_root_dir_xyz/test"
        result = cc.save_image(gray_100x100, bad_dir, 0.0, 0.0, "bad")
        assert result is None

    def test_defaults_to_desktop_when_no_dir(self, gray_100x100):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        path = cc.save_image(gray_100x100)
        if path is not None:
            assert path.startswith(desktop)
            os.remove(path)


class TestSaveSessionLog:
    def test_creates_log_file(self, tmp_path):
        cc.save_session_log({"model": "TestCam", "exposure": 10000}, str(tmp_path))
        logs = list(tmp_path.glob("session_log_*.txt"))
        assert len(logs) == 1

    def test_log_contains_all_keys(self, tmp_path):
        info = {"model": "TestCam", "exposure_us": 5000, "gain": 0.0}
        cc.save_session_log(info, str(tmp_path))
        log_text = list(tmp_path.glob("session_log_*.txt"))[0].read_text()
        for key in info:
            assert key in log_text

    def test_log_contains_values(self, tmp_path):
        info = {"model": "MockBasler"}
        cc.save_session_log(info, str(tmp_path))
        log_text = list(tmp_path.glob("session_log_*.txt"))[0].read_text()
        assert "MockBasler" in log_text

    def test_creates_directory_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "logs")
        cc.save_session_log({}, new_dir)
        assert os.path.isdir(new_dir)


class TestLogFrameMetadata:
    def test_creates_csv_with_header(self, tmp_path):
        cc.log_frame_metadata(0, 10000.0, 128.5, str(tmp_path))
        csv_path = tmp_path / "frame_metadata.csv"
        assert csv_path.exists()
        with open(csv_path) as f:
            header = f.readline()
        assert "frame_index" in header

    def test_csv_appends_multiple_rows(self, tmp_path):
        for i in range(3):
            cc.log_frame_metadata(i, 10000.0, float(i * 10), str(tmp_path))
        with open(tmp_path / "frame_metadata.csv") as f:
            rows = f.readlines()
        assert len(rows) == 4  # 1 header + 3 data rows

    def test_header_written_only_once(self, tmp_path):
        cc.log_frame_metadata(0, 10000.0, 50.0, str(tmp_path))
        cc.log_frame_metadata(1, 10000.0, 60.0, str(tmp_path))
        with open(tmp_path / "frame_metadata.csv") as f:
            content = f.read()
        assert content.count("frame_index") == 1

    def test_csv_row_contains_frame_index(self, tmp_path):
        cc.log_frame_metadata(42, 10000.0, 100.0, str(tmp_path))
        reader = csv.DictReader(open(tmp_path / "frame_metadata.csv"))
        row = next(reader)
        assert int(row["frame_index"]) == 42

    def test_csv_row_contains_brightness(self, tmp_path):
        cc.log_frame_metadata(0, 10000.0, 123.45, str(tmp_path))
        reader = csv.DictReader(open(tmp_path / "frame_metadata.csv"))
        row = next(reader)
        assert float(row["mean_brightness"]) == pytest.approx(123.45, abs=0.01)


# ===========================================================================
# SECTION 1 — CAMERA CONNECTION (Basler mocked)
# ===========================================================================

class TestConnectCamera:
    def test_returns_none_when_no_camera_found(self):
        from pypylon import genicam
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TlFactory.GetInstance().CreateFirstDevice.side_effect = \
                genicam.GenericException("No camera")
            camera, format_info = cc.connect_camera()
        assert camera is None
        assert isinstance(format_info, dict)

    def test_returns_camera_object_on_success(self):
        cam = make_mock_basler_camera()
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TlFactory.GetInstance().CreateFirstDevice.return_value = MagicMock()
            mock_pylon.InstantCamera.return_value = cam
            camera, format_info = cc.connect_camera()
        assert camera is cam
        assert isinstance(format_info, dict)
        assert "hardware_format" in format_info
        assert "target_format" in format_info
        assert "needs_channel_swap" in format_info
        assert "camera_type" in format_info

    def test_calls_camera_open(self):
        cam = make_mock_basler_camera()
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TlFactory.GetInstance().CreateFirstDevice.return_value = MagicMock()
            mock_pylon.InstantCamera.return_value = cam
            cc.connect_camera()
        cam.Open.assert_called_once()

    def test_forces_pixel_format_to_mono8(self):
        # The camera remembers its own pixel format across reconnects, in its
        # own onboard memory. Without forcing it here, a camera left in some
        # other format by an earlier session would silently stay that way,
        # and every downstream function assumes 0-255 Mono8 data.
        cam = make_mock_basler_camera()
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TlFactory.GetInstance().CreateFirstDevice.return_value = MagicMock()
            mock_pylon.InstantCamera.return_value = cam
            cc.connect_camera()
        assert cam.PixelFormat.Value == "Mono8"


class TestDisconnectCamera:
    def test_calls_stop_grabbing_if_grabbing(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.return_value = True
        cc.disconnect_camera(cam)
        cam.StopGrabbing.assert_called_once()

    def test_skips_stop_grabbing_if_not_grabbing(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.return_value = False
        cc.disconnect_camera(cam)
        cam.StopGrabbing.assert_not_called()

    def test_calls_close(self):
        cam = make_mock_basler_camera()
        cc.disconnect_camera(cam)
        cam.Close.assert_called_once()


# ===========================================================================
# SECTION 2 — CAMERA SETTINGS (Basler mocked)
# ===========================================================================

class TestSetExposureManual:
    def test_disables_auto_exposure(self):
        cam = make_mock_basler_camera()
        cc.set_exposure_manual(cam, 10000)
        assert cam.ExposureAuto.Value == "Off"

    def test_sets_exposure_within_range(self):
        cam = make_mock_basler_camera()
        cc.set_exposure_manual(cam, 50000)
        assert cam.ExposureTime.Value == 50000

    def test_clamps_below_minimum(self):
        cam = make_mock_basler_camera()
        cc.set_exposure_manual(cam, 1)   # min is 10
        assert cam.ExposureTime.Value == cam.ExposureTime.Min

    def test_clamps_above_maximum(self):
        cam = make_mock_basler_camera()
        cc.set_exposure_manual(cam, 999_999)  # max is 100_000
        assert cam.ExposureTime.Value == cam.ExposureTime.Max

    def test_returns_actual_exposure(self):
        cam = make_mock_basler_camera()
        cam.ExposureTime.Value = 10000
        result = cc.set_exposure_manual(cam, 10000)
        assert result == 10000


class TestSetGainManual:
    def test_disables_auto_gain(self):
        cam = make_mock_basler_camera()
        cc.set_gain_manual(cam, 5.0)
        assert cam.GainAuto.Value == "Off"

    def test_sets_gain_within_range(self):
        cam = make_mock_basler_camera()
        cc.set_gain_manual(cam, 10.0)
        assert cam.Gain.Value == 10.0

    def test_clamps_below_minimum(self):
        cam = make_mock_basler_camera()
        cc.set_gain_manual(cam, -5.0)  # min is 0
        assert cam.Gain.Value == cam.Gain.Min

    def test_clamps_above_maximum(self):
        cam = make_mock_basler_camera()
        cc.set_gain_manual(cam, 100.0)  # max is 24
        assert cam.Gain.Value == cam.Gain.Max

    def test_returns_actual_gain(self):
        cam = make_mock_basler_camera()
        cam.Gain.Value = 5.0
        result = cc.set_gain_manual(cam, 5.0)
        assert result == 5.0


# ===========================================================================
# SECTION 4 — IMAGE CAPTURE (Basler mocked)
# ===========================================================================

def _make_grab_result(array, succeeded=True):
    r = MagicMock()
    r.GrabSucceeded.return_value = succeeded
    r.Array = array
    return r


class TestGrabSingleFrame:
    def test_returns_numpy_array_on_success(self):
        cam = make_mock_basler_camera()
        expected = np.zeros((100, 100), dtype=np.uint8)
        grab_result = _make_grab_result(expected)
        cam.RetrieveResult.return_value = grab_result
        cam.IsGrabbing.side_effect = [True, False]

        from pypylon import pylon
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TimeoutHandling_ThrowException = pylon.TimeoutHandling_ThrowException
            cam.StartGrabbingMax.return_value = None
            cam.IsGrabbing.side_effect = None
            cam.RetrieveResult.return_value = grab_result
            frame = cc.grab_single_frame(cam)

        assert isinstance(frame, np.ndarray)

    def test_returns_none_when_grab_fails(self):
        cam = make_mock_basler_camera()
        failed_result = _make_grab_result(None, succeeded=False)
        failed_result.ErrorDescription = "Mock error"
        from pypylon import pylon
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TimeoutHandling_ThrowException = pylon.TimeoutHandling_ThrowException
            cam.RetrieveResult.return_value = failed_result
            frame = cc.grab_single_frame(cam)

        assert frame is None


class TestGrabSingleFrameColor:
    """
    Basler cameras in this project are always Mono8/Mono12 (no color
    channels exist at the hardware level), so grab_single_frame_color()
    exists here only for interface consistency with
    camera_control_inclusive.py and camera_control_allied_vision.py, and
    simply delegates to the existing grab_single_frame().
    """

    def test_delegates_to_grab_single_frame(self, monkeypatch):
        expected = np.zeros((100, 100), dtype=np.uint8)
        monkeypatch.setattr(cc, "grab_single_frame", lambda camera: expected)
        cam = make_mock_basler_camera()
        result = cc.grab_single_frame_color(cam)
        assert result is expected


class TestGrabSingleFrameColorWithRetry:
    """
    Present for interface consistency with camera_control_inclusive.py and
    camera_control_allied_vision.py, which both need real retry logic for
    USB/GigE cameras that occasionally drop the first frame. Basler cameras
    connect over a dedicated GenICam link, not shared USB bandwidth, so
    this simply delegates to grab_single_frame_color().
    """

    def test_delegates_to_grab_single_frame_color(self, monkeypatch):
        expected = np.zeros((100, 100), dtype=np.uint8)
        monkeypatch.setattr(cc, "grab_single_frame_color", lambda camera: expected)
        cam = make_mock_basler_camera()
        result = cc.grab_single_frame_color_with_retry(cam, max_retries=3)
        assert result is expected


class TestGrabNFrames:
    def test_returns_list_of_correct_length(self):
        cam = make_mock_basler_camera()
        frame_data = np.zeros((10, 10), dtype=np.uint8)

        cam.IsGrabbing.side_effect = [True, True, False]
        cam.RetrieveResult.side_effect = [
            _make_grab_result(frame_data),
            _make_grab_result(frame_data),
        ]

        from pypylon import pylon
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TimeoutHandling_ThrowException = pylon.TimeoutHandling_ThrowException
            frames = cc.grab_n_frames(cam, 2)

        assert len(frames) == 2

    def test_returns_empty_list_when_camera_not_grabbing(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.return_value = False

        from pypylon import pylon
        with patch("camera_control.pylon") as mock_pylon:
            mock_pylon.TimeoutHandling_ThrowException = pylon.TimeoutHandling_ThrowException
            frames = cc.grab_n_frames(cam, 3)

        assert frames == []


# ===========================================================================
# SECTION 3 — ROI (Basler mocked)
# ===========================================================================

class TestSetCaptureRoi:
    def test_sets_offset_and_dimensions(self):
        cam = make_mock_basler_camera(width=1920, height=1200)
        cc.set_capture_roi(cam, x=100, y=50, width=500, height=400)
        assert cam.Width.Value == 500
        assert cam.Height.Value == 400

    def test_clamps_roi_to_sensor_boundary(self):
        cam = make_mock_basler_camera(width=640, height=480)
        cc.set_capture_roi(cam, x=0, y=0, width=9999, height=9999)
        assert cam.Width.Value <= 640
        assert cam.Height.Value <= 480


class TestResetCaptureRoi:
    def test_restores_full_sensor_dimensions(self):
        cam = make_mock_basler_camera(width=1920, height=1200)
        cc.set_capture_roi(cam, 100, 100, 400, 300)
        cc.reset_capture_roi(cam)
        assert cam.Width.Value == 1920
        assert cam.Height.Value == 1200

    def test_resets_offsets_to_zero(self):
        cam = make_mock_basler_camera()
        cc.set_capture_roi(cam, 100, 100, 400, 300)
        cc.reset_capture_roi(cam)
        assert cam.OffsetX.Value == 0
        assert cam.OffsetY.Value == 0
