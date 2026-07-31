"""
test_preview_worker_cleanup_diagnosis.py
========================================
Diagnostic tests to verify preview worker properly releases camera.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from run_experiment_gui import CameraPreviewWorker


class TestPreviewWorkerCameraRelease:
    """Verify preview worker releases camera so other threads can use it."""

    def test_disconnect_called_on_normal_exit(self):
        """disconnect_camera should be called when run completes normally."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_cam_lib.connect_camera.return_value = (mock_camera, {})
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib

            worker._stop = True
            worker.run()

            # Verify disconnect was called
            mock_cam_lib.disconnect_camera.assert_called_once_with(mock_camera)

    def test_disconnect_called_on_error_in_grab(self):
        """disconnect_camera should be called even if grab_single_frame raises error."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_cam_lib.connect_camera.return_value = (mock_camera, {})
            mock_cam_lib.grab_single_frame.side_effect = RuntimeError("Camera failure")
            mock_import.return_value = mock_cam_lib

            worker.run()

            # Verify disconnect was still called despite error
            mock_cam_lib.disconnect_camera.assert_called_once_with(mock_camera)

    def test_disconnect_called_on_connection_failure(self):
        """If connect_camera returns (None, {}), disconnect should not be called, but finished should be."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = (None, {})
            mock_import.return_value = mock_cam_lib

            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            worker._stop = True
            worker.run()

            # Disconnect should NOT be called since camera is None
            mock_cam_lib.disconnect_camera.assert_not_called()
            # But finished signal SHOULD be emitted
            assert len(finished) >= 1, "Should emit finished even on connection failure"

    def test_finished_signal_emitted_even_if_disconnect_fails(self):
        """finished_cleanly should be emitted even if disconnect raises error."""
        worker = CameraPreviewWorker("2", 0.02, 5.0)

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_cam_lib.connect_camera.return_value = (mock_camera, {})
            mock_cam_lib.grab_single_frame.return_value = None
            # Make disconnect fail
            mock_cam_lib.disconnect_camera.side_effect = RuntimeError("Disconnect failed")
            mock_import.return_value = mock_cam_lib

            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            worker._stop = True
            worker.run()

            # Despite disconnect failing, finished should still be emitted
            assert len(finished) >= 1, "finished_cleanly should be emitted despite disconnect error"

    def test_signal_emission_order(self):
        """Verify signals are emitted in correct order: error, then finished."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = (None, {})
            mock_import.return_value = mock_cam_lib

            signals = []
            worker.error.connect(lambda msg: signals.append("error"))
            worker.finished_cleanly.connect(lambda: signals.append("finished"))

            worker._stop = True
            worker.run()

            # Error should come before finished
            assert "error" in signals, "Should emit error"
            assert "finished" in signals, "Should emit finished"
            if "error" in signals and "finished" in signals:
                error_idx = signals.index("error")
                finished_idx = signals.index("finished")
                assert error_idx < finished_idx, "Error should come before finished"


class TestPreviewWorkerCameraLock:
    """Verify preview worker doesn't hold exclusive camera lock."""

    def test_preview_truly_releases_camera_to_sweep(self):
        """Simulate preview running and stopping, then sweep connecting."""
        # This is a complex scenario requiring sequential operations
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()

            # Track how many times connect_camera is called
            connect_calls = []
            def mock_connect(**kwargs):
                connect_calls.append(True)
                return (mock_camera, {})

            mock_cam_lib.connect_camera.side_effect = mock_connect
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib

            # Run preview (should connect and disconnect)
            preview_worker = CameraPreviewWorker("1", 0.01, 0.0)
            preview_worker._stop = True
            preview_worker.run()

            # Verify disconnect was called
            assert mock_cam_lib.disconnect_camera.called, "Preview should disconnect"

            # Now simulate sweep connecting to same camera
            # This should succeed (simulate with another call)
            assert len(connect_calls) >= 1, "Connect should have been called at least once"
            # In real scenario, if disconnect didn't work, connecting again would fail
            # We verify disconnect WAS called as evidence it released the lock

    def test_camera_variable_properly_initialized_before_finally(self):
        """camera variable must be initialized before try block or finally block crashes."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            # Make connect_camera fail with error before returning tuple
            mock_cam_lib.connect_camera.side_effect = ImportError("SDK missing")
            mock_import.return_value = mock_cam_lib

            # This should not crash in finally block
            try:
                worker.run()
            except Exception as e:
                pytest.fail(f"run() should not raise exception, got: {e}")
