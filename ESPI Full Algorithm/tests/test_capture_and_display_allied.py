"""
test_capture_and_display_allied.py
Tests for capture_and_display_allied.py (Allied Vision live feed + frame
subtraction monitor).

vmbpy requires the VimbaX native runtime which is not available in CI, so
the entire vmbpy package is stubbed out in sys.modules BEFORE the module
under test is imported, the same approach test_camera_control_allied_vision.py
uses. This also proves that importing capture_and_display_allied no longer
opens a camera by itself, only main() does, which used to not be true: the
old version ran its whole camera loop at module import time.

Sections covered
----------------
  get_camera()
    Index out of range / no cameras detected both raise RuntimeError with
    an accurate message.

  main() — list_cameras
    Prints every detected camera and returns without opening a live feed.

  main() — no camera / bad index
    RuntimeError from get_camera() is caught and printed, not raised.

  main() — settings
    exposure_us / gain passed to main() reach set_exposure() / set_gain();
    gain=None must skip the gain call entirely.

  main() — grab loop
    Live Feed and Frame Subtraction windows shown once two frames arrive;
    VmbTimeout is retried; other frame errors stop the loop cleanly.

  main() — gain_factor saturation
    Same convertScaleAbs saturation guarantee as the other two scripts.
"""

import sys
import os
import types

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub vmbpy BEFORE importing the module under test.
# capture_and_display_allied.py does `import vmbpy` and then uses
# vmbpy.VmbSystem, vmbpy.VmbTimeout, and vmbpy.PixelFormat.
# ---------------------------------------------------------------------------


class _VmbTimeout(Exception):
    pass


_vmbpy_stub = types.ModuleType("vmbpy")
_vmbpy_stub.VmbSystem = MagicMock()
_vmbpy_stub.VmbTimeout = _VmbTimeout
_vmbpy_stub.PixelFormat = MagicMock()

sys.modules["vmbpy"] = _vmbpy_stub

sys.modules.pop("capture_and_display_allied", None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import capture_and_display_allied as cad_av


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_camera(name="MockAV", cam_id="DEV_MOCK"):
    cam = MagicMock()
    cam.get_name.return_value = name
    cam.get_id.return_value = cam_id
    cam.get_model.return_value = "Mako"
    return cam


def _make_mock_vmb(cameras):
    """Return the object yielded by `with vmbpy.VmbSystem.get_instance() as vmb:`."""
    vmb = MagicMock()
    vmb.get_all_cameras.return_value = cameras
    return vmb


def _patch_vmb_system(cameras):
    """
    Patch vmbpy.VmbSystem.get_instance() so the `with` block in main()
    yields a mock vmb exposing the given camera list.
    """
    vmb = _make_mock_vmb(cameras)
    instance = MagicMock()
    instance.__enter__.return_value = vmb
    instance.__exit__.return_value = False
    return patch.object(cad_av.vmbpy.VmbSystem, "get_instance", return_value=instance), vmb


def _av_frame(array):
    frame = MagicMock()
    frame.as_opencv_image.return_value = array
    return frame


# ===========================================================================
# frame_to_gray() — must reuse camera_control_allied_vision.to_gray(),
# not keep its own separate copy of the same shape-handling logic
# ===========================================================================

class TestFrameToGray:
    def test_mono_frame_unwraps_third_dimension(self):
        mono = np.full((10, 10, 1), 42, dtype=np.uint8)
        result = cad_av.frame_to_gray(_av_frame(mono))
        assert result.shape == (10, 10)
        assert (result == 42).all()

    def test_delegates_to_shared_to_gray(self):
        # Proves the reuse, not just matching behavior by coincidence.
        arr = np.zeros((5, 5), dtype=np.uint8)
        with patch.object(cad_av, "to_gray", return_value="sentinel") as mock_to_gray:
            result = cad_av.frame_to_gray(_av_frame(arr))
        mock_to_gray.assert_called_once()
        assert result == "sentinel"


# ===========================================================================
# get_camera()
# ===========================================================================

class TestGetCamera:
    def test_returns_camera_at_index(self):
        cams = [_make_mock_camera("A"), _make_mock_camera("B")]
        vmb = _make_mock_vmb(cams)
        assert cad_av.get_camera(vmb, 1) is cams[1]

    def test_raises_when_no_cameras(self):
        vmb = _make_mock_vmb([])
        with pytest.raises(RuntimeError, match="No Allied Vision cameras detected"):
            cad_av.get_camera(vmb, 0)

    def test_raises_when_index_out_of_range(self):
        vmb = _make_mock_vmb([_make_mock_camera()])
        with pytest.raises(RuntimeError, match="camera_index=5 is out of range"):
            cad_av.get_camera(vmb, 5)


# ===========================================================================
# main() — list_cameras
# ===========================================================================

class TestMainListCameras:
    def test_prints_detected_cameras_and_returns(self, capsys):
        cams = [_make_mock_camera("A", "ID_A"), _make_mock_camera("B", "ID_B")]
        patcher, vmb = _patch_vmb_system(cams)
        with patcher:
            cad_av.main(list_cameras=True)
        out = capsys.readouterr().out
        assert "Found 2 Allied Vision camera(s)" in out
        assert "ID_A" in out
        assert "ID_B" in out

    def test_does_not_open_a_live_feed(self):
        patcher, vmb = _patch_vmb_system([_make_mock_camera()])
        with patcher, patch("cv2.imshow") as mock_imshow:
            cad_av.main(list_cameras=True)
        mock_imshow.assert_not_called()


# ===========================================================================
# main() — no camera / bad index
# ===========================================================================

class TestMainCameraLookupFailure:
    def test_no_cameras_detected_prints_error_and_returns(self, capsys):
        patcher, vmb = _patch_vmb_system([])
        with patcher:
            cad_av.main()
        out = capsys.readouterr().out
        assert "[ERROR]" in out
        assert "No Allied Vision cameras detected" in out

    def test_index_out_of_range_prints_error_and_returns(self, capsys):
        patcher, vmb = _patch_vmb_system([_make_mock_camera()])
        with patcher:
            cad_av.main(camera_index=7)
        out = capsys.readouterr().out
        assert "camera_index=7 is out of range" in out


# ===========================================================================
# main() — settings applied
# ===========================================================================

class TestMainAppliesSettings:
    def _cam_with_no_frames(self):
        cam = _make_mock_camera()
        cam.__enter__ = MagicMock(return_value=cam)
        cam.__exit__ = MagicMock(return_value=False)
        cam.get_frame.side_effect = RuntimeError("stop")  # break loop immediately
        return cam

    def test_exposure_forwarded_to_set_exposure(self):
        cam = self._cam_with_no_frames()
        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure") as mock_exp, \
             patch.object(cad_av, "set_gain") as mock_gain, \
             patch("cv2.destroyAllWindows"):
            cad_av.main(exposure_us=20000, gain=2.0)
        mock_exp.assert_called_once_with(cam, 20000)
        mock_gain.assert_called_once_with(cam, 2.0)

    def test_gain_none_still_calls_set_gain_which_skips_internally(self):
        # set_gain(cam, None) is always called, it is set_gain's own job to
        # no-op on None (see capture_and_display_allied.set_gain).
        cam = self._cam_with_no_frames()
        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch("cv2.destroyAllWindows"):
            cad_av.main(gain=None)
        cam.Gain.set.assert_not_called()


# ===========================================================================
# main() — grab loop
# ===========================================================================

class TestMainGrabLoop:
    def _open_cam(self):
        cam = _make_mock_camera()
        cam.__enter__ = MagicMock(return_value=cam)
        cam.__exit__ = MagicMock(return_value=False)
        return cam

    def test_shows_live_feed_and_subtraction_then_quits_on_q(self):
        cam = self._open_cam()
        frame_a = _av_frame(np.full((10, 10), 50, dtype=np.uint8))
        frame_b = _av_frame(np.full((10, 10), 200, dtype=np.uint8))
        cam.get_frame.side_effect = [frame_a, frame_b]

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad_av.main()

        shown_windows = [c.args[0] for c in mock_imshow.call_args_list]
        assert "Live Feed" in shown_windows
        assert "Frame Subtraction" in shown_windows

    def test_timeout_is_retried_not_fatal(self):
        cam = self._open_cam()
        frame_a = _av_frame(np.full((5, 5), 50, dtype=np.uint8))
        cam.get_frame.side_effect = [cad_av.vmbpy.VmbTimeout("slow link"), frame_a]

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad_av.main()

        shown_windows = [c.args[0] for c in mock_imshow.call_args_list]
        assert "Live Feed" in shown_windows

    def test_frame_grab_error_stops_loop_cleanly(self, capsys):
        cam = self._open_cam()
        cam.get_frame.side_effect = RuntimeError("USB link dropped")

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch("cv2.imshow") as mock_imshow, \
             patch("cv2.destroyAllWindows"):
            cad_av.main()  # must return, not raise

        out = capsys.readouterr().out
        assert "Frame grab failed" in out
        mock_imshow.assert_not_called()


# ===========================================================================
# main() — gain_factor amplification must saturate, not wrap around
# ===========================================================================

class TestGainFactorSaturation:
    def test_large_difference_clips_at_255(self):
        cam = _make_mock_camera()
        cam.__enter__ = MagicMock(return_value=cam)
        cam.__exit__ = MagicMock(return_value=False)
        frame_a = _av_frame(np.full((4, 4), 10, dtype=np.uint8))
        frame_b = _av_frame(np.full((4, 4), 250, dtype=np.uint8))
        cam.get_frame.side_effect = [frame_a, frame_b]

        captured = {}

        def _fake_imshow(name, image):
            captured[name] = image.copy()

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch("cv2.imshow", side_effect=_fake_imshow), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            cad_av.main(gain_factor=3)

        assert np.all(captured["Frame Subtraction"] == 255)
        assert captured["Frame Subtraction"].dtype == np.uint8


# ===========================================================================
# main() — optional live graph (graph_type)
# ===========================================================================

class TestGraphType:
    def _open_cam(self):
        cam = _make_mock_camera()
        cam.__enter__ = MagicMock(return_value=cam)
        cam.__exit__ = MagicMock(return_value=False)
        return cam

    def test_default_graph_type_creates_no_graph(self):
        cam = self._open_cam()
        cam.get_frame.side_effect = [_av_frame(np.full((4, 4), 1, dtype=np.uint8))]

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch.object(cad_av, "live_graphs") as mock_live_graphs, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            cad_av.main()

        mock_live_graphs.create_live_graph.assert_called_once_with(None)

    def test_histogram_graph_type_forwarded_and_updated_per_frame(self):
        cam = self._open_cam()
        frame_a = _av_frame(np.full((4, 4), 1, dtype=np.uint8))
        frame_b = _av_frame(np.full((4, 4), 2, dtype=np.uint8))
        cam.get_frame.side_effect = [frame_a, frame_b]
        mock_graph = MagicMock()

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch.object(cad_av, "live_graphs") as mock_live_graphs, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", side_effect=[-1, ord("q")]), \
             patch("cv2.destroyAllWindows"):
            mock_live_graphs.create_live_graph.return_value = mock_graph
            cad_av.main(graph_type="histogram")

        mock_live_graphs.create_live_graph.assert_called_once_with("histogram")
        assert mock_graph.update.call_count == 2

    def test_graph_closed_when_loop_ends_cleanly(self):
        cam = self._open_cam()
        cam.get_frame.side_effect = [_av_frame(np.full((4, 4), 1, dtype=np.uint8))]
        mock_graph = MagicMock()

        patcher, vmb = _patch_vmb_system([cam])
        with patcher, \
             patch.object(cad_av, "set_exposure"), \
             patch.object(cad_av, "set_gain"), \
             patch.object(cad_av, "live_graphs") as mock_live_graphs, \
             patch("cv2.imshow"), \
             patch("cv2.waitKey", return_value=ord("q")), \
             patch("cv2.destroyAllWindows"):
            mock_live_graphs.create_live_graph.return_value = mock_graph
            cad_av.main(graph_type="3d")

        mock_graph.close.assert_called_once()

    def test_no_graph_created_when_no_cameras_detected(self):
        # The graph must not be created before the camera lookup succeeds —
        # otherwise a "no camera" error would leave a graph window open
        # with nothing ever feeding it frames.
        patcher, vmb = _patch_vmb_system([])
        with patcher, \
             patch.object(cad_av, "live_graphs") as mock_live_graphs:
            cad_av.main(graph_type="histogram")

        mock_live_graphs.create_live_graph.assert_not_called()
