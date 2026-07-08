"""
test_capture_and_display_cv2.py
Tests for capture_and_display_cv2.py (any OpenCV-visible camera).

Sections covered
----------------
  main() — camera fails to open
    cap.isOpened() returning False must print a message naming the index
    and return without touching the display windows.

  main() — settings
    camera_index / exposure / gain passed to main() must reach
    cv2.VideoCapture() and cap.set() unchanged.

  main() — grab loop
    Live Feed and Frame Subtraction windows are shown once two frames have
    been read; the loop exits cleanly on 'q' or on a failed read;
    cap.release() runs even if the loop raises.

  main() — gain_factor saturation
    Same convertScaleAbs saturation guarantee as capture_and_display.py.
"""

import sys
import os

import cv2
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import capture_and_display_cv2 as cad_cv2


def _bgr_frame(value, size=10):
    return np.full((size, size, 3), value, dtype=np.uint8)


def _make_mock_cap(read_sequence, is_opened=True):
    """read_sequence is a list of (ret, frame) tuples returned in order."""
    cap = MagicMock()
    cap.isOpened.return_value = is_opened
    cap.read.side_effect = read_sequence
    return cap


# ===========================================================================
# main() — camera fails to open
# ===========================================================================

class TestMainCameraNotOpened:
    def test_prints_message_with_index_and_returns(self, capsys):
        cap = _make_mock_cap([], is_opened=False)
        with patch("cv2.VideoCapture", return_value=cap):
            cad_cv2.main(camera_index=3)
        out = capsys.readouterr().out
        assert "Could not open camera at index 3" in out

    def test_does_not_touch_display_when_not_opened(self):
        cap = _make_mock_cap([], is_opened=False)
        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow") as mock_imshow:
            cad_cv2.main()
        mock_imshow.assert_not_called()


# ===========================================================================
# main() — settings applied
# ===========================================================================

class TestMainAppliesSettings:
    def test_camera_index_forwarded_to_videocapture(self):
        cap = _make_mock_cap([(False, None)])
        with patch("cv2.VideoCapture", return_value=cap) as mock_vc:
            cad_cv2.main(camera_index=2)
        assert mock_vc.call_args[0][0] == 2

    def test_exposure_and_gain_forwarded_to_cap_set(self):
        cap = _make_mock_cap([(False, None)])
        with patch("cv2.VideoCapture", return_value=cap):
            cad_cv2.main(exposure=-8, gain=4.5)

        set_calls = {call.args[0]: call.args[1] for call in cap.set.call_args_list}
        assert set_calls[cv2.CAP_PROP_EXPOSURE] == -8
        assert set_calls[cv2.CAP_PROP_GAIN] == 4.5

    def test_defaults_match_module_constants(self):
        cap = _make_mock_cap([(False, None)])
        with patch("cv2.VideoCapture", return_value=cap):
            cad_cv2.main()

        set_calls = {call.args[0]: call.args[1] for call in cap.set.call_args_list}
        assert set_calls[cv2.CAP_PROP_EXPOSURE] == cad_cv2.EXPOSURE
        assert set_calls[cv2.CAP_PROP_GAIN] == cad_cv2.GAIN


# ===========================================================================
# main() — grab loop
# ===========================================================================

class TestMainGrabLoop:
    def test_shows_live_feed_and_subtraction_then_quits_on_q(self):
        cap = _make_mock_cap([
            (True, _bgr_frame(50)),
            (True, _bgr_frame(200)),
        ])
        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main()

        shown_windows = [c.args[0] for c in mock_imshow.call_args_list]
        assert "Live Feed" in shown_windows
        assert "Frame Subtraction" in shown_windows

    def test_no_subtraction_window_on_first_frame(self):
        cap = _make_mock_cap([(True, _bgr_frame(50))])
        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main()

        shown_windows = [c.args[0] for c in mock_imshow.call_args_list]
        assert "Live Feed" in shown_windows
        assert "Frame Subtraction" not in shown_windows

    def test_stops_and_prints_message_on_failed_read(self, capsys):
        cap = _make_mock_cap([(False, None)])
        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=-1), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main()
        out = capsys.readouterr().out
        assert "Failed to grab frame" in out

    def test_releases_camera_even_if_loop_raises(self):
        cap = _make_mock_cap([])
        cap.read.side_effect = RuntimeError("driver crashed")
        with patch("cv2.VideoCapture", return_value=cap):
            with pytest.raises(RuntimeError):
                cad_cv2.main()
        cap.release.assert_called_once()

    def test_releases_camera_on_clean_quit(self):
        cap = _make_mock_cap([(True, _bgr_frame(50))])
        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main()
        cap.release.assert_called_once()


# ===========================================================================
# main() — gain_factor amplification must saturate, not wrap around
# ===========================================================================

class TestGainFactorSaturation:
    def test_large_difference_clips_at_255(self):
        cap = _make_mock_cap([
            (True, _bgr_frame(10)),
            (True, _bgr_frame(250)),
        ])

        captured = {}

        def _fake_imshow(name, image):
            captured[name] = image.copy()

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow", side_effect=_fake_imshow), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main(gain_factor=3)

        assert np.all(captured["Frame Subtraction"] == 255)
        assert captured["Frame Subtraction"].dtype == np.uint8

    def test_small_difference_scales_linearly(self):
        cap = _make_mock_cap([
            (True, _bgr_frame(10)),
            (True, _bgr_frame(15)),
        ])

        captured = {}

        def _fake_imshow(name, image):
            captured[name] = image.copy()

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("cv2.imshow", side_effect=_fake_imshow), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main(gain_factor=4)

        assert np.all(captured["Frame Subtraction"] == 20)


# ===========================================================================
# _capture_backend() — Windows/Mac/Linux camera backend selection
# ===========================================================================

class TestCaptureBackend:
    """
    capture_and_display_cv2.py used to hardcode cv2.CAP_AVFOUNDATION, a
    macOS-only backend constant. On Windows this either fails to open the
    camera or silently falls back to a slower default. _capture_backend()
    picks the right one per OS instead.
    """

    def test_mac_uses_avfoundation(self):
        with patch("capture_and_display_cv2.sys.platform", "darwin"):
            assert cad_cv2._capture_backend() == cv2.CAP_AVFOUNDATION

    def test_windows_uses_dshow(self):
        with patch("capture_and_display_cv2.sys.platform", "win32"):
            assert cad_cv2._capture_backend() == cv2.CAP_DSHOW

    def test_linux_uses_cap_any(self):
        with patch("capture_and_display_cv2.sys.platform", "linux"):
            assert cad_cv2._capture_backend() == cv2.CAP_ANY

    def test_backend_is_forwarded_to_videocapture(self):
        cap = _make_mock_cap([(False, None)])
        with patch("cv2.VideoCapture", return_value=cap) as mock_vc, \
             patch("capture_and_display_cv2.sys.platform", "win32"):
            cad_cv2.main()
        assert mock_vc.call_args[0][1] == cv2.CAP_DSHOW


# ===========================================================================
# main() — optional live graph (graph_type)
# ===========================================================================

class TestGraphType:
    def test_default_graph_type_creates_no_graph(self):
        cap = _make_mock_cap([(True, _bgr_frame(1))])
        with patch("cv2.VideoCapture", return_value=cap), \
             patch("capture_and_display_cv2.live_graphs.create_live_graph") as mock_create, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main()
        mock_create.assert_called_once_with(None)

    def test_histogram_graph_type_forwarded_and_updated_per_frame(self):
        cap = _make_mock_cap([
            (True, _bgr_frame(1)),
            (True, _bgr_frame(2)),
        ])
        mock_graph = MagicMock()

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("capture_and_display_cv2.live_graphs.create_live_graph",
                   return_value=mock_graph) as mock_create, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main(graph_type="histogram")

        mock_create.assert_called_once_with("histogram")
        assert mock_graph.update.call_count == 2

    def test_graph_closed_when_loop_ends_cleanly(self):
        cap = _make_mock_cap([(True, _bgr_frame(1))])
        mock_graph = MagicMock()

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("capture_and_display_cv2.live_graphs.create_live_graph",
                   return_value=mock_graph), \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad_cv2.main(graph_type="3d")

        mock_graph.close.assert_called_once()

    def test_graph_closed_even_if_read_raises(self):
        cap = _make_mock_cap([])
        cap.read.side_effect = RuntimeError("driver crashed")
        mock_graph = MagicMock()

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("capture_and_display_cv2.live_graphs.create_live_graph",
                   return_value=mock_graph):
            with pytest.raises(RuntimeError):
                cad_cv2.main(graph_type="histogram")

        mock_graph.close.assert_called_once()
