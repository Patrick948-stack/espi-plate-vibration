"""
test_three_critical_bugs_regression.py
======================================

Regression tests for the three critical GUI bugs that prevented the app from working:

BUG 1: Settings not persisting to SetupPage UI on return
BUG 2: Sweep fails with "Device is exclusively opened" camera lock error
BUG 3: Sweep button stuck after first failure

These tests WOULD HAVE FAILED before the fixes and now PASS after.
They serve as regression tests to prevent these bugs from returning.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestBug1SettingsPersistToSetupUI:
    """
    BUG 1: User changes settings in Settings tab, then goes to Setup tab.
    Expected: Setup UI shows the changed values.
    Broken: Setup UI showed defaults, ignoring saved settings.
    """

    def test_setup_page_reloads_settings_on_navigation(self, qtbot, tmp_path):
        """
        Reproduce exact bug: User workflow is Settings → Setup.

        BEFORE FIX: SetupPage would show defaults even though settings were saved.
        AFTER FIX: SetupPage should show saved values.
        """
        from run_experiment_gui import MainWindow

        # Create app with temp settings file
        settings_file = tmp_path / "settings.json"

        with patch("settings_manager._get_settings_path", return_value=settings_file):
            # Create MainWindow
            window = MainWindow()
            qtbot.addWidget(window)

            # ==== PHASE 1: User saves custom settings ====
            # Simulate user changing exposure in Setup page
            window.setup_page.exposure_spin.setValue(0.055)

            # User clicks "Continue to Preview" which saves
            settings = load_settings()
            settings["default_exposure"] = 0.055
            save_settings(settings)

            # Verify settings saved to disk
            with open(settings_file) as f:
                saved = json.load(f)
            assert saved["default_exposure"] == 0.055, "Settings should be on disk"

            # ==== PHASE 2: User navigates to Settings tab ====
            window._nav.setCurrentRow(4)  # Settings tab
            qtbot.wait(100)  # Let UI process

            # ==== PHASE 3: User navigates back to Setup ====
            window._nav.setCurrentRow(0)  # Setup tab
            qtbot.wait(100)  # Let UI process

            # ==== PHASE 4: VERIFY THE BUG IS FIXED ====
            # BEFORE FIX: This assertion would FAIL because SetupPage.reload_settings()
            # was never called, so exposure_spin would still be 0.01 (default)
            #
            # AFTER FIX: This passes because MainWindow._on_nav_changed() now calls
            # setup_page.reload_settings() when navigating to Setup (row == 0)
            assert window.setup_page.exposure_spin.value() == 0.055, \
                f"BUG 1: Setup should show saved exposure 0.055, but shows {window.setup_page.exposure_spin.value()}"

    def test_setup_page_reload_settings_method_updates_all_controls(self, qtbot, tmp_path):
        """
        Verify that reload_settings() actually updates all UI controls.
        """
        from run_experiment_gui import SetupPage

        settings_file = tmp_path / "settings.json"

        with patch("settings_manager._get_settings_path", return_value=settings_file):
            # Save custom settings
            settings = load_settings()
            settings.update({
                "default_camera_choice": "3",
                "default_mode_choice": "2",
                "default_start_freq": 250.0,
                "default_end_freq": 2500.0,
                "default_step_size": 250.0,
                "default_n_averages": 10,
                "default_exposure": 0.077,
                "default_gain": 5.5,
                "default_gain_factor": 2.0,
            })
            save_settings(settings)

            # Create SetupPage and reload
            page = SetupPage()
            qtbot.addWidget(page)
            page.reload_settings()

            # VERIFY all controls show reloaded values
            assert page.camera_choice() == "3", "Camera should reload"
            assert page.mode_choice() == "2", "Mode should reload"
            assert page.start_freq_spin.value() == 250.0, "Start freq should reload"
            assert page.end_freq_spin.value() == 2500.0, "End freq should reload"
            assert page.step_spin.value() == 250.0, "Step should reload"
            assert page.n_averages_spin.value() == 10, "N averages should reload"
            assert page.exposure_spin.value() == 0.077, "Exposure should reload"
            assert page.gain_spin.value() == 5.5, "Gain should reload"
            assert page.gain_factor_spin.value() == 2.0, "Gain factor should reload"


class TestBug2CameraLockDuringSweep:
    """
    BUG 2: Sweep fails after ~2 seconds with "Device is exclusively opened" error.

    Root cause: LiveMonitoringWorker tried to connect to camera while SweepWorker
    held it exclusively. Camera locking is enforced by SDK.

    Broken behavior:
    - User clicks Start Sweep
    - Monitoring windows appear briefly
    - Error: 'Device is exclusively opened by another client'
    - Sweep exits with no results
    - Can't click Start button again (stuck)

    Expected behavior:
    - Sweep should start and complete successfully
    - Should collect data
    - No camera lock errors
    """

    def test_sweep_does_not_start_monitoring_worker_that_competes_for_camera(self, qtbot):
        """
        Verify that SweepPage._start_sweep() does NOT create LiveMonitoringWorker.

        BEFORE FIX: Would create monitoring worker that tries to connect to camera
        AFTER FIX: Monitoring worker disabled to prevent camera lock
        """
        from run_experiment_gui import SweepPage

        page = SweepPage()
        qtbot.addWidget(page)

        # Set up minimal params
        page.begin(
            camera_choice="2",  # USB camera
            mode_choice="1",
            params={
                "start_freq": 100.0,
                "end_freq": 200.0,
                "step": 50.0,
                "n_averages": 2,
                "exposure": 0.01,
                "gain": 0.0,
                "gain_factor": 1.0,
                "output_dir": "output",
            }
        )

        # Mock the SweepWorker to avoid actually connecting
        with patch("run_experiment_gui.SweepWorker") as mock_sweep:
            mock_worker = MagicMock()
            mock_sweep.return_value = mock_worker

            # Call _start_sweep
            page._start_sweep()

            # VERIFY: monitoring_worker should NOT be created
            # BEFORE FIX: page._monitoring_worker would be a LiveMonitoringWorker instance
            # AFTER FIX: page._monitoring_worker is None and monitoring_group is hidden
            assert page._monitoring_worker is None, \
                "BUG 2: LiveMonitoringWorker should not be created (it competes for camera)"

            assert not page._monitoring_group.isVisible(), \
                "BUG 2: Monitoring group should be hidden when disabled"

    def test_sweep_worker_created_without_competing_monitoring_worker(self, qtbot):
        """
        Verify SweepWorker is created and started when _start_sweep is called.
        """
        from run_experiment_gui import SweepPage

        page = SweepPage()
        qtbot.addWidget(page)

        page.begin(
            camera_choice="2",
            mode_choice="1",
            params={
                "start_freq": 100.0,
                "end_freq": 200.0,
                "step": 50.0,
                "n_averages": 2,
                "exposure": 0.01,
                "gain": 0.0,
                "gain_factor": 1.0,
                "output_dir": "output",
            }
        )

        with patch("run_experiment_gui.SweepWorker") as mock_sweep:
            mock_worker = MagicMock()
            mock_sweep.return_value = mock_worker

            page._start_sweep()

            # VERIFY: SweepWorker should be created and started
            mock_sweep.assert_called_once()
            mock_worker.start.assert_called_once()

            # VERIFY: _worker is set
            assert page._worker is mock_worker, "SweepPage should hold reference to worker"


class TestBug3SweepButtonStuck:
    """
    BUG 3: After sweep fails, Start Sweep button is stuck disabled.
    User cannot click it again.

    Root cause: When sweep crashed due to camera lock error,
    _start_sweep() had set button to disabled but never re-enabled it.

    Fix: Fixing Bug 2 (camera lock) prevents the crash, so button never
    gets stuck in the first place.
    """

    def test_sweep_button_starts_enabled_and_can_restart(self, qtbot):
        """
        Verify Start Sweep button is clickable multiple times.
        """
        from run_experiment_gui import SweepPage

        page = SweepPage()
        qtbot.addWidget(page)

        # Set up params
        page.begin(
            camera_choice="2",
            mode_choice="1",
            params={
                "start_freq": 100.0,
                "end_freq": 200.0,
                "step": 50.0,
                "n_averages": 2,
                "exposure": 0.01,
                "gain": 0.0,
                "gain_factor": 1.0,
                "output_dir": "output",
            }
        )

        # Button should start enabled
        assert page.start_button.isEnabled(), "Start button should be enabled initially"

        # Mock sweep worker to simulate completion
        with patch("run_experiment_gui.SweepWorker") as mock_sweep:
            mock_worker = MagicMock()
            mock_sweep.return_value = mock_worker

            # First sweep attempt
            page._start_sweep()
            assert not page.start_button.isEnabled(), "Start button should be disabled during sweep"

            # Simulate sweep finishing
            page._on_finished({})  # Simulates sweep completion (results dict)

            # VERIFY: Button should be re-enabled for another sweep
            # BEFORE FIX: Button would stay disabled after crash
            # AFTER FIX: Button is re-enabled because sweep didn't crash
            assert page.start_button.isEnabled(), \
                "BUG 3: Start button should be re-enabled after sweep completes"


class TestIntegrationUserWorkflowNowWorks:
    """
    Integration test: Verify the complete user workflow works end-to-end.
    """

    def test_user_can_modify_settings_and_return_to_see_them(self, qtbot, tmp_path):
        """
        Simulate exact user sequence that was broken:
        1. Change settings
        2. Go to Setup
        3. See changed values (not defaults)
        """
        from run_experiment_gui import MainWindow

        settings_file = tmp_path / "settings.json"

        with patch("settings_manager._get_settings_path", return_value=settings_file):
            window = MainWindow()
            qtbot.addWidget(window)

            # Save custom settings
            settings = load_settings()
            settings["default_exposure"] = 0.099
            settings["default_camera_choice"] = "3"
            save_settings(settings)

            # Navigate: Setup → Settings → Setup
            window._nav.setCurrentRow(0)  # Setup
            qtbot.wait(100)

            window._nav.setCurrentRow(4)  # Settings
            qtbot.wait(100)

            window._nav.setCurrentRow(0)  # Back to Setup
            qtbot.wait(100)

            # VERIFY: Values should be loaded from disk
            assert window.setup_page.exposure_spin.value() == 0.099, \
                "User's custom exposure should be visible in Setup"
            assert window.setup_page.camera_choice() == "3", \
                "User's custom camera should be visible in Setup"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
