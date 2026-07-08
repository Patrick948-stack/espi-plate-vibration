"""
test_capture_and_display.py
Tests for capture_and_display.py (Basler live feed + frame subtraction monitor).

Sections covered
----------------
  main() — no camera
    connect_camera() returning None must print a message and return without
    touching cv2 or the grab loop at all.

  main() — settings
    exposure_us / gain_db passed to main() must reach set_exposure_manual()
    and set_gain_manual() unchanged.

  main() — grab loop
    Live Feed and Frame Subtraction windows are shown once two frames have
    been grabbed; the loop exits cleanly on 'q'; disconnect_camera() runs
    even if the loop raises.

  main() — gain_factor saturation
    The amplified subtraction image must clip at 255 instead of wrapping
    around, the bug that motivated switching from
    `gain_factor * cv2.absdiff(...)` to `cv2.convertScaleAbs(...)`.
"""

import sys
import os

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import capture_and_display as cad
from conftest import make_mock_basler_camera


def _make_grab_result(frame, succeeded=True):
    gr = MagicMock()
    gr.GrabSucceeded.return_value = succeeded
    gr.Array = frame
    return gr


# ===========================================================================
# main() — no camera found
# ===========================================================================

class TestMainNoCamera:
    def test_prints_message_and_returns(self, capsys):
        with patch("capture_and_display.connect_camera", return_value=None):
            cad.main()
        out = capsys.readouterr().out
        assert "No camera found" in out

    def test_does_not_touch_cv2_when_no_camera(self):
        with patch("capture_and_display.connect_camera", return_value=None), \
             patch("cv2.imshow") as mock_imshow:
            cad.main()
        mock_imshow.assert_not_called()


# ===========================================================================
# main() — settings applied
# ===========================================================================

class TestMainAppliesSettings:
    def test_exposure_and_gain_forwarded_unchanged(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = [False]

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual") as mock_exp, \
             patch("capture_and_display.set_gain_manual") as mock_gain:
            cad.main(exposure_us=12345, gain_db=3.0, gain_factor=10)

        mock_exp.assert_called_once_with(cam, 12345)
        mock_gain.assert_called_once_with(cam, 3.0)

    def test_defaults_match_module_constants(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = [False]

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual") as mock_exp, \
             patch("capture_and_display.set_gain_manual") as mock_gain:
            cad.main()

        mock_exp.assert_called_once_with(cam, cad.EXPOSURE_US)
        mock_gain.assert_called_once_with(cam, cad.GAIN_DB)


# ===========================================================================
# main() — grab loop
# ===========================================================================

class TestMainGrabLoop:
    def test_shows_live_feed_and_subtraction_then_quits_on_q(self):
        cam = make_mock_basler_camera()
        frame_a = np.full((10, 10), 50, dtype=np.uint8)
        frame_b = np.full((10, 10), 200, dtype=np.uint8)

        cam.IsGrabbing.side_effect = [True, True, False]
        cam.RetrieveResult.side_effect = [
            _make_grab_result(frame_a),
            _make_grab_result(frame_b),
        ]

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad.main()

        shown_windows = [c.args[0] for c in mock_imshow.call_args_list]
        assert "Live Feed" in shown_windows
        assert "Frame Subtraction" in shown_windows

    def test_no_subtraction_window_on_first_frame(self):
        # Only one frame has been grabbed, there is no previous frame yet to
        # subtract against, so "Frame Subtraction" must not appear.
        cam = make_mock_basler_camera()
        frame_a = np.full((10, 10), 50, dtype=np.uint8)

        cam.IsGrabbing.side_effect = [True, False]
        cam.RetrieveResult.side_effect = [_make_grab_result(frame_a)]

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad.main()

        shown_windows = [c.args[0] for c in mock_imshow.call_args_list]
        assert "Live Feed" in shown_windows
        assert "Frame Subtraction" not in shown_windows

    def test_failed_grab_is_released_and_skipped(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = [True, False]
        cam.RetrieveResult.side_effect = [_make_grab_result(None, succeeded=False)]

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad.main()

        mock_imshow.assert_not_called()

    def test_disconnects_camera_even_if_loop_raises(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = RuntimeError("USB link dropped")

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera") as mock_disc, \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"):
            with pytest.raises(RuntimeError):
                cad.main()

        mock_disc.assert_called_once_with(cam)


# ===========================================================================
# main() — gain_factor amplification must saturate, not wrap around
# ===========================================================================

class TestGainFactorSaturation:
    def test_large_difference_clips_at_255(self):
        # True amplified value would be (250-10)*3 = 720, far past 255.
        # cv2.convertScaleAbs must clip to 255 (pure white) instead of
        # wrapping into a smaller uint8 value.
        cam = make_mock_basler_camera()
        frame_a = np.full((4, 4), 10, dtype=np.uint8)
        frame_b = np.full((4, 4), 250, dtype=np.uint8)

        cam.IsGrabbing.side_effect = [True, True, False]
        cam.RetrieveResult.side_effect = [
            _make_grab_result(frame_a),
            _make_grab_result(frame_b),
        ]

        captured = {}

        def _fake_imshow(name, image):
            captured[name] = image.copy()

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("cv2.imshow", side_effect=_fake_imshow), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad.main(gain_factor=3)

        assert np.all(captured["Frame Subtraction"] == 255)
        assert captured["Frame Subtraction"].dtype == np.uint8

    def test_small_difference_scales_linearly(self):
        cam = make_mock_basler_camera()
        frame_a = np.full((4, 4), 10, dtype=np.uint8)
        frame_b = np.full((4, 4), 15, dtype=np.uint8)  # diff = 5

        cam.IsGrabbing.side_effect = [True, True, False]
        cam.RetrieveResult.side_effect = [
            _make_grab_result(frame_a),
            _make_grab_result(frame_b),
        ]

        captured = {}

        def _fake_imshow(name, image):
            captured[name] = image.copy()

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("cv2.imshow", side_effect=_fake_imshow), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad.main(gain_factor=4)

        # 5 * 4 = 20, well under 255, no clipping expected.
        assert np.all(captured["Frame Subtraction"] == 20)


# ===========================================================================
# main() — optional live graph (graph_type)
# ===========================================================================

class TestGraphType:
    def test_default_graph_type_creates_no_graph(self):
        # graph_type defaults to None, live_graphs.create_live_graph(None)
        # returns None — main() must never call .update()/.close() on
        # anything in that case, since there is nothing to call it on.
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = [True, False]
        cam.RetrieveResult.side_effect = [
            _make_grab_result(np.full((5, 5), 1, dtype=np.uint8))
        ]

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("capture_and_display.live_graphs.create_live_graph") as mock_create, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad.main()

        mock_create.assert_called_once_with(None)

    def test_histogram_graph_type_forwarded_and_updated_per_frame(self):
        cam = make_mock_basler_camera()
        frame_a = np.full((5, 5), 1, dtype=np.uint8)
        frame_b = np.full((5, 5), 2, dtype=np.uint8)
        cam.IsGrabbing.side_effect = [True, True, False]
        cam.RetrieveResult.side_effect = [
            _make_grab_result(frame_a),
            _make_grab_result(frame_b),
        ]

        mock_graph = MagicMock()

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("capture_and_display.live_graphs.create_live_graph",
                   return_value=mock_graph) as mock_create, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad.main(graph_type="histogram")

        mock_create.assert_called_once_with("histogram")
        assert mock_graph.update.call_count == 2
        np.testing.assert_array_equal(mock_graph.update.call_args_list[0].args[0], frame_a)
        np.testing.assert_array_equal(mock_graph.update.call_args_list[1].args[0], frame_b)

    def test_graph_closed_when_camera_loop_ends(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = [False]
        mock_graph = MagicMock()

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("capture_and_display.live_graphs.create_live_graph",
                   return_value=mock_graph):
            cad.main(graph_type="3d")

        mock_graph.close.assert_called_once()

    def test_graph_closed_even_if_loop_raises(self):
        cam = make_mock_basler_camera()
        cam.IsGrabbing.side_effect = RuntimeError("USB link dropped")
        mock_graph = MagicMock()

        with patch("capture_and_display.connect_camera", return_value=cam), \
             patch("capture_and_display.disconnect_camera"), \
             patch("capture_and_display.set_exposure_manual"), \
             patch("capture_and_display.set_gain_manual"), \
             patch("capture_and_display.live_graphs.create_live_graph",
                   return_value=mock_graph):
            with pytest.raises(RuntimeError):
                cad.main(graph_type="histogram")

        mock_graph.close.assert_called_once()
