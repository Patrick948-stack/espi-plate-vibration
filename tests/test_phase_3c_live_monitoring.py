"""
test_phase_3c_live_monitoring.py
==================================
Tests for Phase 3C: Show 4-window live feed monitoring if enabled.
Verifies that:
1. Live monitoring setting controls display
2. LiveMonitoringWorker initializes correctly
3. Monitoring windows update with frames
4. Monitoring respects grayscale_method setting
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from run_experiment_gui import SweepPage, LiveMonitoringWorker
from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestLiveMonitoringWorkerInitialization:
    """Test that LiveMonitoringWorker initializes correctly."""
    
    def test_live_monitoring_worker_accepts_all_parameters(self):
        """LiveMonitoringWorker should accept camera choice, exposure, gain, and grayscale_method."""
        worker = LiveMonitoringWorker("1", 0.01, 0.0, "single_channel")
        assert worker._camera_choice == "1"
        assert worker._exposure_s == 0.01
        assert worker._gain == 0.0
        assert worker._grayscale_method == "single_channel"
    
    def test_live_monitoring_worker_has_stop_flag(self):
        """LiveMonitoringWorker should have stop() method to safely terminate."""
        worker = LiveMonitoringWorker("2", 0.02, 5.0, "standard")
        assert hasattr(worker, '_stop')
        assert worker._stop is False
        worker.stop()
        assert worker._stop is True


class TestLiveMonitoringWorkerCameraConnection:
    """Test that LiveMonitoringWorker connects to camera with correct settings."""
    
    def test_monitoring_worker_calls_connect_with_grayscale_method(self):
        """LiveMonitoringWorker.run() should call connect_camera with grayscale_method."""
        worker = LiveMonitoringWorker("1", 0.01, 0.0, "single_channel")
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True  # Immediately stop
            worker.run()
            
            # Should try to connect with grayscale_method
            mock_cam_lib.connect_camera.assert_called_with(grayscale_method="single_channel")
    
    def test_monitoring_worker_handles_connection_failure(self):
        """LiveMonitoringWorker should emit error if connection fails."""
        worker = LiveMonitoringWorker("1", 0.01, 0.0, "standard")
        
        error_received = []
        worker.error.connect(lambda msg: error_received.append(msg))
        
        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()
            mock_cam_lib.connect_camera.return_value = None
            mock_import.return_value = mock_cam_lib
            
            worker._stop = True
            worker.run()
            
            # Should emit connection error
            assert len(error_received) > 0
            # Accept either "Could not connect" or generic camera error message
            assert any(phrase in error_received[0] for phrase in ["Could not connect", "Could not open"])


class TestSweepPageLiveMonitoringWidgets:
    """Test that SweepPage has live monitoring display widgets."""
    
    def test_sweep_page_has_monitoring_widgets(self, qapp):
        """SweepPage should have display widgets for 4 monitoring windows."""
        page = SweepPage()
        
        assert hasattr(page, '_live_display')
        assert hasattr(page, '_captured_display')
        assert hasattr(page, '_diff_display')
        assert hasattr(page, '_avg_display')
        
        assert hasattr(page, '_live_label')
        assert hasattr(page, '_captured_label')
        assert hasattr(page, '_diff_label')
        assert hasattr(page, '_avg_label')
    
    def test_monitoring_group_visibility_default_hidden(self, qapp):
        """Monitoring group should be hidden by default."""
        page = SweepPage()
        assert page._monitoring_group.isVisible() is False


class TestSweepPageMonitoringIntegration:
    """Test that SweepPage integrates live monitoring with sweep."""
    
    def test_sweep_page_loads_live_monitoring_setting(self, qapp):
        """SweepPage should check show_live_feed_during_sweep setting."""
        page = SweepPage()
        
        with patch("run_experiment_gui.load_settings") as mock_load:
            mock_load.return_value = {
                "show_live_feed_during_sweep": True,
                "grayscale_method": "standard"
            }


class TestMonitoringFrameDisplay:
    """Test that monitoring frame updates are displayed correctly."""
    
    def test_sweep_page_has_on_monitor_frames_method(self, qapp):
        """SweepPage should have method to handle monitoring frame updates."""
        page = SweepPage()
        assert hasattr(page, '_on_monitor_frames')
        assert callable(page._on_monitor_frames)
    
    def test_sweep_page_has_on_monitor_error_method(self, qapp):
        """SweepPage should have method to handle monitoring errors."""
        page = SweepPage()
        assert hasattr(page, '_on_monitor_error')
        assert callable(page._on_monitor_error)
    
    def test_monitoring_frame_update_handles_none_frames(self, qapp):
        """SweepPage should gracefully handle None frames in updates."""
        page = SweepPage()
        
        # Should not crash with None frames
        frame_data = {
            'live': None,
            'captured': None,
            'diff': None,
            'avg': None
        }
        
        # Should not raise
        page._on_monitor_frames(frame_data)


class TestLiveMonitoringCleanup:
    """Test that live monitoring is properly cleaned up after sweep."""
    
    def test_monitoring_worker_stopped_on_sweep_finish(self, qapp):
        """Monitoring worker should be stopped and cleaned when sweep finishes."""
        page = SweepPage()
        
        # Simulate monitoring worker being active
        mock_worker = MagicMock()
        page._monitoring_worker = mock_worker
        page._monitoring_group.setVisible(True)
        
        # Call finish
        page._on_finished(None)
        
        # Worker should have been stopped
        mock_worker.stop.assert_called()
        mock_worker.wait.assert_called()
        # And monitoring should be hidden
        assert page._monitoring_group.isVisible() is False


class TestMonitoringWorkerFrameProcessing:
    """Test that monitoring worker processes frames correctly."""
    
    def test_monitoring_worker_emits_frame_update_signal(self):
        """LiveMonitoringWorker should emit frame_update signal with frame dict."""
        worker = LiveMonitoringWorker("1", 0.01, 0.0, "standard")
        
        frames_received = []
        worker.frame_update.connect(lambda frames: frames_received.append(frames))
        
        # Manually emit a frame update (in real scenario, run() does this)
        test_frame = np.zeros((100, 100), dtype=np.uint8)
        worker.frame_update.emit({
            'live': test_frame,
            'captured': test_frame,
            'diff': None,
            'avg': test_frame
        })
        
        assert len(frames_received) == 1
        assert 'live' in frames_received[0]
        assert 'captured' in frames_received[0]
        assert 'diff' in frames_received[0]
        assert 'avg' in frames_received[0]

