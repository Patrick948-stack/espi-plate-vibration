"""
test_camera_defensive_programming.py
====================================
TDD for defensive programming in camera workers.
Tests verify all the bugs identified in the brutal code review are fixed.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from run_experiment_gui import CameraPreviewWorker, LiveMonitoringWorker


class TestCameraPreviewWorkerDefensive:
    """Test CameraPreviewWorker defensive programming."""
    
    def test_handles_none_tuple_failure_case(self):
        """Worker must handle (None, {}) return from connect_camera()."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = (None, {})  # Failure case
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            # Should emit error and signal completion
            assert len(error_received) > 0, "Should emit error for (None, {}) case"
            assert len(finished) >= 1, "Should signal completion even on failure"
    
    def test_handles_invalid_return_type(self):
        """Worker must reject non-tuple return values."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = "invalid"  # Wrong type
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            # Should detect invalid type
            assert len(error_received) > 0, "Should emit error for invalid type"
            assert len(finished) >= 1, "Should complete"
    
    def test_handles_malformed_tuple(self):
        """Worker must validate tuple has exactly 2 elements."""
        worker = CameraPreviewWorker("2", 0.02, 5.0)
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = ("only_one",)  # Wrong length
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            # Should detect malformed tuple
            assert len(error_received) > 0, "Should emit error for malformed tuple"
            assert len(finished) >= 1, "Should complete"
    
    def test_specific_exception_for_attribute_error(self):
        """Worker must distinguish AttributeError from other exceptions."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_cam_lib.connect_camera.return_value = (mock_camera, {})
            # Make grab_single_frame raise AttributeError on first call, then stop
            call_count = [0]
            def grab_with_error(camera):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise AttributeError("grab_single_frame missing")
                return None
            mock_cam_lib.grab_single_frame.side_effect = grab_with_error
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            
            # Let it run normally, not stopped
            worker.run()
            
            # Should have detected the AttributeError
            assert len(error_received) > 0, "Should emit error for AttributeError"
            assert any("Missing camera function" in msg or "AttributeError" in str(error_received) for msg in error_received), \
                f"Error should mention function issue, got: {error_received}"
    
    def test_disconnect_handles_attribute_error(self):
        """Worker must not crash if disconnect raises AttributeError."""
        worker = CameraPreviewWorker("3", 0.03, 2.0)
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_camera = MagicMock()
            mock_cam_lib.connect_camera.return_value = (mock_camera, {})
            mock_cam_lib.grab_single_frame.return_value = None
            mock_cam_lib.disconnect_camera.side_effect = AttributeError("bad disconnect")
            mock_import.return_value = mock_cam_lib
            
            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            # Should signal completion even if disconnect fails
            assert len(finished) >= 1, "Should complete even with disconnect error"
    
    def test_validates_camera_choice(self):
        """Worker must validate camera_choice at initialization."""
        with pytest.raises(ValueError, match="Invalid camera_choice"):
            CameraPreviewWorker("invalid_camera", 0.01, 0.0)
    
    def test_validates_exposure(self):
        """Worker must validate exposure > 0."""
        with pytest.raises(ValueError, match="exposure_s must be > 0"):
            CameraPreviewWorker("1", -0.01, 0.0)
    
    def test_validates_grayscale_method(self):
        """Worker must validate grayscale_method."""
        with pytest.raises(ValueError, match="grayscale_method must be"):
            CameraPreviewWorker("1", 0.01, 0.0, "invalid_method")
    
    def test_validates_module_has_required_functions(self):
        """Worker must verify camera module has all required functions."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            # Module is missing grab_single_frame
            del mock_cam_lib.grab_single_frame
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished_cleanly.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            # Should detect missing function
            assert len(error_received) > 0, "Should detect missing function"
            assert len(finished) >= 1, "Should complete"


class TestLiveMonitoringWorkerDefensive:
    """Test LiveMonitoringWorker defensive programming."""
    
    def test_handles_none_tuple_failure(self):
        """Monitoring worker must handle (None, {}) return."""
        worker = LiveMonitoringWorker("2", 0.02, 5.0, "standard")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = (None, {})
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            assert len(error_received) > 0, "Should emit error"
            assert len(finished) >= 1, "Should complete"
    
    def test_handles_invalid_tuple_type(self):
        """Monitoring worker must reject non-tuple return."""
        worker = LiveMonitoringWorker("3", 0.03, 0.0, "single_channel")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = {"bad": "type"}  # Dict instead of tuple
            mock_import.return_value = mock_cam_lib
            
            error_received = []
            worker.error.connect(lambda msg: error_received.append(msg))
            finished = []
            worker.finished.connect(lambda: finished.append(True))
            
            worker._stop = True
            worker.run()
            
            assert len(error_received) > 0, "Should detect invalid type"
            assert len(finished) >= 1, "Should complete"
    
    def test_validates_parameters_at_init(self):
        """Monitoring worker should validate parameters."""
        with pytest.raises(ValueError, match="Invalid camera_choice"):
            LiveMonitoringWorker("invalid", 0.01, 0.0, "standard")
        
        with pytest.raises(ValueError, match="exposure_s must be > 0"):
            LiveMonitoringWorker("1", -0.01, 0.0, "standard")
        
        with pytest.raises(ValueError, match="grayscale_method must be"):
            LiveMonitoringWorker("1", 0.01, 0.0, "invalid")

