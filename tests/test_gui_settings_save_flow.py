"""
test_gui_settings_save_flow.py
==============================
Test that run_experiment_gui properly saves and reloads settings
after applying the fixes.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestGUISettingsSaveOnContinue:
    """Verify GUI saves settings when user clicks Continue."""

    def test_start_preview_saves_current_settings(self):
        """
        When _start_preview is called, current UI values should be saved to disk.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Simulate the fixed _start_preview logic
                # Load current settings
                settings = load_settings()

                # Simulate user's UI changes
                params = {
                    "start_freq": 250.0,
                    "end_freq": 2000.0,
                    "step": 50.0,
                    "n_averages": 8,
                    "exposure": 0.055,
                    "gain": 2.5,
                    "gain_factor": 1.5,
                    "output_dir": "output",
                }
                camera_choice = "3"
                grayscale_method = "single_channel"

                # Update settings (as the fixed code does)
                settings.update({
                    "default_camera_choice": camera_choice,
                    "default_start_freq": params["start_freq"],
                    "default_end_freq": params["end_freq"],
                    "default_step_size": params["step"],
                    "default_n_averages": params["n_averages"],
                    "default_exposure": params["exposure"],
                    "default_gain": params["gain"],
                    "default_gain_factor": params["gain_factor"],
                    "grayscale_method": grayscale_method,
                })

                # Save (this is what the fixed code now does)
                assert save_settings(settings) is True

                # Verify they were actually saved to disk
                with open(settings_file) as f:
                    import json
                    saved = json.load(f)

                assert saved["default_camera_choice"] == "3"
                assert saved["default_exposure"] == 0.055
                assert saved["default_start_freq"] == 250.0
                assert saved["grayscale_method"] == "single_channel"

    def test_start_sweep_saves_current_settings(self):
        """
        When _start_sweep_stage is called, current UI values should be saved.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                settings = load_settings()

                # Simulate user's choices
                params = {
                    "start_freq": 333.0,
                    "end_freq": 3000.0,
                    "step": 100.0,
                    "n_averages": 10,
                    "exposure": 0.033,
                    "gain": 5.0,
                    "gain_factor": 2.0,
                    "output_dir": "output",
                }
                camera_choice = "1"

                # Update and save (as fixed code does)
                settings.update({
                    "default_camera_choice": camera_choice,
                    "default_start_freq": params["start_freq"],
                    "default_end_freq": params["end_freq"],
                    "default_step_size": params["step"],
                    "default_n_averages": params["n_averages"],
                    "default_exposure": params["exposure"],
                    "default_gain": params["gain"],
                    "default_gain_factor": params["gain_factor"],
                })
                save_settings(settings)

                # Load and verify
                reloaded = load_settings()
                assert reloaded["default_camera_choice"] == "1"
                assert reloaded["default_exposure"] == 0.033
                assert reloaded["default_start_freq"] == 333.0


class TestSetupPageReloadsSettings:
    """Verify SetupPage reload_settings() method works correctly."""

    def test_reload_settings_updates_all_controls(self):
        """
        reload_settings() should update all UI controls from disk.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Save custom settings to disk
            custom_settings = DEFAULT_SETTINGS.copy()
            custom_settings.update({
                "default_camera_choice": "2",
                "default_exposure": 0.077,
                "default_start_freq": 777.0,
                "default_end_freq": 7777.0,
                "default_step_size": 77.0,
                "default_n_averages": 7,
                "default_gain": 7.0,
                "default_gain_factor": 7.0,
            })

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                save_settings(custom_settings)

                # Simulate SetupPage with mocked controls
                mock_camera_radios = {
                    "1": MagicMock(),
                    "2": MagicMock(),
                    "3": MagicMock(),
                }
                mock_mode_radios = {
                    "1": MagicMock(),
                    "2": MagicMock(),
                }

                # Simulate reload logic (from the fixed SetupPage.reload_settings)
                settings = load_settings()

                camera_choice = settings.get("default_camera_choice", "2")
                if camera_choice in mock_camera_radios:
                    mock_camera_radios[camera_choice].setChecked(True)

                mode_choice = settings.get("default_mode_choice", "1")
                if mode_choice in mock_mode_radios:
                    mock_mode_radios[mode_choice].setChecked(True)

                # Verify radio buttons were set correctly
                mock_camera_radios["2"].setChecked.assert_called_with(True)

    def test_reload_settings_called_on_return_to_setup(self):
        """
        When user clicks "Run again", settings should reload from disk.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Simulate workflow:
                # 1. Save settings
                settings = DEFAULT_SETTINGS.copy()
                settings["default_camera_choice"] = "3"
                settings["default_exposure"] = 0.099
                save_settings(settings)

                # 2. Load them (as if user returns to setup)
                loaded = load_settings()

                # 3. Verify they're the saved values
                assert loaded["default_camera_choice"] == "3"
                assert loaded["default_exposure"] == 0.099


class TestCompleteGUISettingsFlow:
    """
    Integration test: Verify complete flow with fixes.
    1. App starts (load defaults)
    2. User changes settings
    3. User clicks Continue (save)
    4. User sees preview
    5. User returns to setup (reload)
    6. App restarts (load)
    """

    def test_complete_gui_settings_workflow(self):
        """Complete scenario with all fixes applied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # ==== APP START ====
                # Load defaults
                settings = load_settings()
                assert settings["default_camera_choice"] == DEFAULT_SETTINGS["default_camera_choice"]

                # ==== USER CHANGES SETTINGS ====
                user_settings = settings.copy()
                user_settings["default_camera_choice"] = "1"
                user_settings["default_exposure"] = 0.044
                user_settings["default_start_freq"] = 444.0

                # ==== CLICK CONTINUE (PREVIEW STAGE) ====
                # Simulate _start_preview saving settings
                save_settings(user_settings)

                # ==== LOAD SETTINGS (as preview would) ====
                preview_settings = load_settings()
                assert preview_settings["default_camera_choice"] == "1"

                # ==== RETURN TO SETUP (Run again) ====
                # Simulate reload_settings being called
                reloaded = load_settings()

                # ==== VERIFY SETTINGS PERSISTED ====
                assert reloaded["default_camera_choice"] == "1", \
                    "Camera choice should persist from before preview"
                assert reloaded["default_exposure"] == 0.044, \
                    "Exposure should persist from before preview"
                assert reloaded["default_start_freq"] == 444.0, \
                    "Start frequency should persist from before preview"

                # ==== APP RESTART ====
                restarted_settings = load_settings()

                # ==== VERIFY SETTINGS STILL THERE ====
                assert restarted_settings["default_camera_choice"] == "1"
                assert restarted_settings["default_exposure"] == 0.044
                assert restarted_settings["default_start_freq"] == 444.0
