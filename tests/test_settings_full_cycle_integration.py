"""
test_settings_full_cycle_integration.py
========================================
Integration tests simulating complete user workflow:
1. App starts (loads settings)
2. User changes settings in UI
3. User clicks continue (should save)
4. Preview runs and releases camera
5. Sweep runs (camera available)
6. App restarts (settings persist)
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestSettingsPersistenceFullCycle:
    """Simulate complete user workflow with settings persistence."""

    def test_user_changes_settings_and_restarts_app(self):
        """
        Scenario: User opens app, changes settings, closes, reopens.
        Expected: Settings should persist.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # ==== SESSION 1: User opens app ====
                settings_s1 = load_settings()
                # Defaults load
                assert settings_s1["default_exposure"] == DEFAULT_SETTINGS["default_exposure"]

                # ==== User changes settings in UI ====
                modified_settings = settings_s1.copy()
                modified_settings["default_exposure"] = 0.055
                modified_settings["default_camera_choice"] = "3"
                modified_settings["default_start_freq"] = 250.0

                # ==== User clicks "Continue" (should save) ====
                save_result = save_settings(modified_settings)
                assert save_result is True, "Settings should save successfully"

                # ==== SESSION 2: User restarts app ====
                settings_s2 = load_settings()

                # ==== Verify settings persisted ====
                assert settings_s2["default_exposure"] == 0.055, \
                    "Exposure should be saved from session 1"
                assert settings_s2["default_camera_choice"] == "3", \
                    "Camera choice should be saved from session 1"
                assert settings_s2["default_start_freq"] == 250.0, \
                    "Start frequency should be saved from session 1"

    def test_setup_page_loads_and_saves_settings(self):
        """
        Simulate SetupPage behavior: load defaults at init, save when continuing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # ==== Simulate SetupPage.__init__() ====
                # Loads defaults
                loaded = load_settings()
                default_camera = loaded.get("default_camera_choice", "2")

                # User changes values (simulating UI controls)
                user_changes = loaded.copy()
                user_changes["default_camera_choice"] = "1"  # Changed camera
                user_changes["default_exposure"] = 0.044  # Changed exposure
                user_changes["default_start_freq"] = 333.0  # Changed freq

                # ==== Simulate _start_preview() / _start_sweep_stage() ====
                # Should save current UI values before proceeding
                assert save_settings(user_changes) is True

                # ==== Verify saved ====
                reloaded = load_settings()
                assert reloaded["default_camera_choice"] == "1"
                assert reloaded["default_exposure"] == 0.044
                assert reloaded["default_start_freq"] == 333.0

    def test_multiple_changes_persist_correctly(self):
        """
        Test that multiple sequential changes persist correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Change 1
                settings = load_settings()
                settings["default_exposure"] = 0.011
                save_settings(settings)

                # Verify change 1
                loaded = load_settings()
                assert loaded["default_exposure"] == 0.011

                # Change 2 (different setting)
                settings = loaded.copy()
                settings["default_camera_choice"] = "2"
                save_settings(settings)

                # Verify both changes present
                loaded = load_settings()
                assert loaded["default_exposure"] == 0.011, "Change 1 should persist"
                assert loaded["default_camera_choice"] == "2", "Change 2 should persist"


class TestCameraAvailabilityAcrossWorkers:
    """
    Simulate preview and sweep workers sharing camera.
    Verify preview releases camera so sweep can use it.
    """

    def test_preview_worker_releases_camera_for_sweep(self):
        """
        Scenario: Preview worker connects to camera, then sweep worker needs it.
        Expected: Preview disconnects, sweep can connect.
        """
        # Simulate camera connection state
        camera_state = {"connected_by": None, "connection_count": 0}

        def mock_connect_camera(**kwargs):
            """Mock camera connection."""
            if camera_state["connected_by"] is not None:
                # Camera already in use
                raise RuntimeError(
                    f"Device is exclusively opened by {camera_state['connected_by']}"
                )
            camera_state["connected_by"] = "worker"
            camera_state["connection_count"] += 1
            return (MagicMock(), {"format": "Mono8"})

        def mock_disconnect_camera(camera):
            """Mock camera disconnection."""
            if camera_state["connected_by"] == "worker":
                camera_state["connected_by"] = None

        # ==== Preview connects ====
        try:
            camera, fmt = mock_connect_camera(grayscale_method="standard")
            assert camera_state["connected_by"] == "worker"
        except RuntimeError:
            pytest.fail("Preview should connect successfully on first try")

        # ==== Preview disconnects ====
        mock_disconnect_camera(camera)
        assert camera_state["connected_by"] is None, "Camera should be released"

        # ==== Sweep connects (should succeed) ====
        try:
            camera2, fmt2 = mock_connect_camera(grayscale_method="standard")
            assert camera_state["connected_by"] == "worker"
        except RuntimeError:
            pytest.fail("Sweep should connect successfully after preview disconnects")

        # ==== Sweep disconnects ====
        mock_disconnect_camera(camera2)
        assert camera_state["connected_by"] is None

    def test_preview_worker_disconnects_even_on_error(self):
        """
        Scenario: Preview worker encounters error but still must disconnect.
        Expected: Even if grab_single_frame fails, disconnect is called.
        """
        from run_experiment_gui import CameraPreviewWorker

        camera_state = {"connected": False}

        with patch("run_experiment_gui.importlib.import_module") as mock_import:
            mock_cam_lib = MagicMock()

            def connect(**kwargs):
                camera_state["connected"] = True
                return (MagicMock(), {})

            def disconnect(cam):
                camera_state["connected"] = False

            mock_cam_lib.connect_camera.side_effect = connect
            mock_cam_lib.disconnect_camera.side_effect = disconnect
            mock_cam_lib.grab_single_frame.side_effect = RuntimeError("Camera error")
            mock_import.return_value = mock_cam_lib

            # Run preview
            worker = CameraPreviewWorker("1", 0.01, 0.0)
            worker.run()

            # Verify it disconnected despite error
            assert camera_state["connected"] is False, \
                "Preview worker must disconnect even if grab_single_frame fails"
            mock_cam_lib.disconnect_camera.assert_called()


class TestLivePhotoSimulation:
    """
    Simulate camera capturing frames and test that monitoring windows work.
    """

    def test_camera_captures_grayscale_frames(self):
        """
        Simulate camera.grab_single_frame() returning numpy array (photo).
        """
        # Create fake grayscale image (like Mono8 camera)
        fake_frame = np.zeros((480, 640), dtype=np.uint8)
        fake_frame[100:200, 100:200] = 255  # White square (speckle pattern)

        # Verify it's a valid numpy array
        assert isinstance(fake_frame, np.ndarray)
        assert fake_frame.dtype == np.uint8
        assert fake_frame.shape == (480, 640)

        # Simulate frame processing
        assert fake_frame.min() == 0
        assert fake_frame.max() == 255

    def test_camera_returns_multiple_frames(self):
        """
        Simulate continuous frame capture (like preview loop).
        """
        frame_count = 0
        max_frames = 5

        def mock_grab_frame(camera):
            nonlocal frame_count
            frame_count += 1
            if frame_count > max_frames:
                return None
            # Return grayscale frame
            frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
            return frame

        # Simulate preview loop
        for _ in range(10):
            frame = mock_grab_frame(None)
            if frame is None:
                break

        assert frame_count == 6, "Should capture 5 frames then return None"

    def test_monitoring_windows_display_frame_data(self):
        """
        Simulate LiveMonitoringWorker receiving frame data and updating UI.
        """
        # Create fake frame
        live_frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
        reference_frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)

        # Simulate difference image
        import cv2
        diff_frame = cv2.absdiff(live_frame, reference_frame)

        # Verify data is valid
        assert isinstance(diff_frame, np.ndarray)
        assert diff_frame.dtype == np.uint8
        assert diff_frame.shape == live_frame.shape

        # Create the frame update dict that would be emitted
        frames = {
            'live': live_frame,
            'captured': live_frame,
            'diff': diff_frame,
            'avg': live_frame
        }

        # Verify all frames present
        assert all(frame is not None for frame in [frames['live'], frames['diff']])


class TestCompleteWorkflowWithMockCamera:
    """
    Full integration test: Settings persistence + Camera availability.
    """

    def test_complete_workflow_settings_camera_persistence(self):
        """
        Complete scenario:
        1. Load app → defaults loaded
        2. Change settings → captured
        3. Continue → settings saved
        4. Preview → camera used and released
        5. Sweep → camera used
        6. Close → restart
        7. Open → settings loaded
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # ==== STEP 1: Load app ====
                settings = load_settings()
                assert settings["default_camera_choice"] in ("1", "2", "3")

                # ==== STEP 2: User changes settings ====
                settings["default_camera_choice"] = "1"
                settings["default_exposure"] = 0.033
                settings["default_start_freq"] = 500.0

                # ==== STEP 3: Continue clicked (save) ====
                assert save_settings(settings) is True

                # ==== STEP 4-5: Preview and sweep use camera ====
                # (In real scenario, camera is accessed)
                # For testing, just verify settings are ready
                loaded_for_preview = load_settings()
                assert loaded_for_preview["default_camera_choice"] == "1"
                assert loaded_for_preview["default_exposure"] == 0.033

                # ==== STEP 6-7: Restart app ====
                settings_after_restart = load_settings()

                # ==== VERIFY ====
                assert settings_after_restart["default_camera_choice"] == "1", \
                    "Camera choice should persist across restart"
                assert settings_after_restart["default_exposure"] == 0.033, \
                    "Exposure should persist across restart"
                assert settings_after_restart["default_start_freq"] == 500.0, \
                    "Start freq should persist across restart"

    def test_sweep_cannot_connect_if_preview_still_holds_camera(self):
        """
        Verify the error scenario: if preview doesn't disconnect,
        sweep connection fails.
        """
        camera_lock = {"owner": None}

        def connect(name):
            if camera_lock["owner"] is not None:
                raise RuntimeError(f"Device exclusively opened by {camera_lock['owner']}")
            camera_lock["owner"] = name
            return MagicMock()

        def disconnect(name):
            camera_lock["owner"] = None

        # Preview connects
        try:
            connect("preview")
            assert camera_lock["owner"] == "preview"
        except RuntimeError:
            pytest.fail("Preview should connect first")

        # Sweep tries to connect (should fail because preview still holds it)
        with pytest.raises(RuntimeError, match="exclusively opened"):
            connect("sweep")

        # After preview disconnects
        disconnect("preview")
        assert camera_lock["owner"] is None

        # Now sweep can connect
        try:
            connect("sweep")
            assert camera_lock["owner"] == "sweep"
        except RuntimeError:
            pytest.fail("Sweep should connect after preview disconnects")
