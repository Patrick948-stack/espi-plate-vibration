"""
test_phase_3b_grayscale_wiring.py
==================================
Tests for Phase 3B: Wire grayscale_method through camera operations.
Verifies that grayscale_method setting is passed correctly through:
1. CameraPreviewWorker
2. PreviewPage
3. MainWindow._start_preview
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from run_experiment_gui import CameraPreviewWorker, PreviewPage
from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestCameraPreviewWorkerGrayscaleMethod:
    """Test that CameraPreviewWorker accepts and passes grayscale_method."""
    
    def test_preview_worker_accepts_grayscale_method(self):
        """CameraPreviewWorker constructor should accept grayscale_method parameter."""
        worker = CameraPreviewWorker("1", 0.01, 0.0, grayscale_method="single_channel")
        assert worker._grayscale_method == "single_channel"
    
    def test_preview_worker_defaults_to_standard(self):
        """CameraPreviewWorker should default to 'standard' if not specified."""
        worker = CameraPreviewWorker("1", 0.01, 0.0)
        assert worker._grayscale_method == "standard"
    
    def test_preview_worker_passes_to_connect_camera(self):
        """CameraPreviewWorker.run() should pass grayscale_method to connect_camera()."""
        worker = CameraPreviewWorker("1", 0.01, 0.0, grayscale_method="single_channel")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = MagicMock()
            mock_cam_lib.grab_single_frame.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True  # Stop immediately after setup
            worker.run()
            
            # Verify connect_camera was called with grayscale_method
            mock_cam_lib.connect_camera.assert_called_with(grayscale_method="single_channel")


class TestPreviewPageGrayscaleMethod:
    """Test that PreviewPage accepts and passes grayscale_method."""
    
    def test_preview_page_start_preview_accepts_grayscale_method(self, qapp):
        """PreviewPage.start_preview should accept grayscale_method parameter."""
        page = PreviewPage()
        page.start_preview("1", 0.01, 0.0, grayscale_method="single_channel")
        assert page._worker is not None
        assert page._worker._grayscale_method == "single_channel"
        # Clean up
        page._worker.stop()
        page._worker.wait()
    
    def test_preview_page_defaults_grayscale_method(self, qapp):
        """PreviewPage.start_preview should default to 'standard'."""
        page = PreviewPage()
        page.start_preview("1", 0.01, 0.0)
        assert page._worker is not None
        assert page._worker._grayscale_method == "standard"
        # Clean up
        page._worker.stop()
        page._worker.wait()


class TestGrayscaleMethodPersistence:
    """Test that grayscale_method persists across app restarts."""
    
    def test_grayscale_method_survives_save_load_cycle(self, tmp_path):
        """Grayscale method set in settings should persist across save/load."""
        settings_file = tmp_path / "settings.json"
        
        # Save a setting with specific grayscale_method
        original_settings = DEFAULT_SETTINGS.copy()
        original_settings["grayscale_method"] = "single_channel"
        original_settings["grayscale_color"] = "G"
        
        with patch("settings_manager._get_settings_path", return_value=settings_file):
            save_settings(original_settings)
            loaded = load_settings()
        
        # Verify persistence
        assert loaded["grayscale_method"] == "single_channel"
        assert loaded["grayscale_color"] == "G"


class TestCameraControlModuleSelection:
    """Test that correct camera module is selected based on choice."""
    
    def test_camera_module_mapping(self):
        """Verify camera choice to module mapping is correct."""
        import run_experiment
        
        assert "1" in run_experiment.CAMERA_LIBRARY
        assert "2" in run_experiment.CAMERA_LIBRARY
        assert "3" in run_experiment.CAMERA_LIBRARY
        
        # Each should map to a valid camera module name
        for choice in ["1", "2", "3"]:
            module_name = run_experiment.CAMERA_LIBRARY[choice]
            assert isinstance(module_name, str)
            assert len(module_name) > 0

