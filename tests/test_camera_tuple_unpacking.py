"""
test_camera_tuple_unpacking.py
==============================
TDD tests for camera tuple unpacking bug.
Tests verify that connect_camera() returns a tuple and the code properly unpacks it.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from run_experiment_gui import CameraPreviewWorker, LiveMonitoringWorker


class TestCameraPreviewWorkerTupleUnpacking:
    """Test that CameraPreviewWorker properly unpacks camera tuple."""
    
    def test_connect_camera_returns_tuple(self):
        """Verify that mock connect_camera returns (camera, format_info) tuple."""
        worker = CameraPreviewWorker("2", 0.01, 0.0, "standard")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            # Simulate real return: tuple (camera, format_info)
            mock_camera = MagicMock()
            mock_format = {"hardware_format": "BGR8", "camera_type": "USB"}
            mock_cam_lib.connect_camera.return_value = (mock_camera, mock_format)
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True
            worker.run()
            
            # Verify connect_camera was called
            mock_cam_lib.connect_camera.assert_called_with(grayscale_method="standard")
    
    def test_preview_worker_handles_tuple_correctly(self):
        """CameraPreviewWorker.run() must properly unpack the tuple."""
        worker = CameraPreviewWorker("1", 0.01, 0.0, "standard")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_format = {"hardware_format": "Mono8"}
            
            # Return tuple like real camera modules do
            mock_cam_lib.connect_camera.return_value = (mock_camera, mock_format)
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True
            worker.run()
            
            # Verify set_exposure_manual was called with the camera object, not tuple
            mock_cam_lib.set_exposure_manual.assert_called()
            call_args = mock_cam_lib.set_exposure_manual.call_args[0]
            # First argument should be the camera object, not a tuple
            assert call_args[0] is mock_camera, f"Expected camera object, got {type(call_args[0])}"
    
    def test_preview_worker_disconnect_called_with_camera_object(self):
        """disconnect_camera() must be called with camera object, not tuple."""
        worker = CameraPreviewWorker("2", 0.01, 0.0, "standard")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_format = {"hardware_format": "BGR8"}
            
            mock_cam_lib.connect_camera.return_value = (mock_camera, mock_format)
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True
            worker.run()
            
            # Verify disconnect_camera was called with camera object, not tuple
            mock_cam_lib.disconnect_camera.assert_called_with(mock_camera)


class TestLiveMonitoringWorkerTupleUnpacking:
    """Test that LiveMonitoringWorker properly unpacks camera tuple."""
    
    def test_monitoring_worker_handles_tuple_correctly(self):
        """LiveMonitoringWorker.run() must properly unpack the tuple."""
        worker = LiveMonitoringWorker("1", 0.01, 0.0, "standard")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_format = {"hardware_format": "Mono8"}
            
            # Return tuple like real camera modules do
            mock_cam_lib.connect_camera.return_value = (mock_camera, mock_format)
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True
            worker.run()
            
            # Verify set_exposure_manual was called with camera object
            mock_cam_lib.set_exposure_manual.assert_called()
            call_args = mock_cam_lib.set_exposure_manual.call_args[0]
            assert call_args[0] is mock_camera
    
    def test_monitoring_worker_disconnect_called_with_camera_object(self):
        """disconnect_camera() must be called with camera object, not tuple."""
        worker = LiveMonitoringWorker("1", 0.01, 0.0, "standard")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_format = {"hardware_format": "Mono8"}
            
            mock_cam_lib.connect_camera.return_value = (mock_camera, mock_format)
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True
            worker.run()
            
            # Verify disconnect_camera was called with camera object
            mock_cam_lib.disconnect_camera.assert_called_with(mock_camera)

