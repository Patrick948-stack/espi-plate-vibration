"""
test_gui_settings_integration_diagnosis.py
==========================================
Diagnostic tests to verify run_experiment_gui actually uses settings_manager.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS


class TestSettingsManagerIsAvailable:
    """Verify settings_manager module exists and works."""

    def test_settings_manager_import(self):
        """Should be able to import settings_manager."""
        try:
            from settings_manager import (
                load_settings, save_settings, get_setting, set_setting,
                validate_settings, DEFAULT_SETTINGS
            )
        except ImportError as e:
            pytest.fail(f"Cannot import settings_manager: {e}")

    def test_default_settings_has_expected_keys(self):
        """DEFAULT_SETTINGS should have all required configuration keys."""
        required_keys = {
            "default_exposure",
            "default_camera_choice",
            "grayscale_method",
            "default_start_freq",
            "default_end_freq",
            "default_step_size",
            "show_live_feed_during_sweep",
            "show_saved_image_after_capture",
        }
        for key in required_keys:
            assert key in DEFAULT_SETTINGS, f"Missing required key: '{key}'"

    def test_default_values_are_sensible(self):
        """Default values should be valid (exposure > 0, etc)."""
        assert DEFAULT_SETTINGS["default_exposure"] > 0, "Exposure must be > 0"
        assert DEFAULT_SETTINGS["default_start_freq"] >= 0, "Start freq must be >= 0"
        assert DEFAULT_SETTINGS["default_camera_choice"] in ("1", "2", "3"), "Invalid camera"
        assert DEFAULT_SETTINGS["grayscale_method"] in ("standard", "single_channel"), "Invalid grayscale"


class TestSettingsWiredToGUI:
    """Test that run_experiment_gui actually loads and uses settings_manager."""

    def test_settings_manager_imported_in_gui(self):
        """run_experiment_gui should import settings_manager."""
        with open("ESPI Full Algorithm/run_experiment_gui.py") as f:
            gui_code = f.read()

        # Check if settings_manager is mentioned (imported or used)
        assert "settings_manager" in gui_code, \
            "run_experiment_gui.py should import settings_manager"

    def test_gui_uses_load_settings(self):
        """run_experiment_gui should call load_settings() somewhere."""
        with open("ESPI Full Algorithm/run_experiment_gui.py") as f:
            gui_code = f.read()

        assert "load_settings" in gui_code, \
            "run_experiment_gui.py should call load_settings()"

    def test_gui_uses_save_settings(self):
        """run_experiment_gui should call save_settings() to persist."""
        with open("ESPI Full Algorithm/run_experiment_gui.py") as f:
            gui_code = f.read()

        assert "save_settings" in gui_code, \
            "run_experiment_gui.py should call save_settings()"


class TestSettingsPersistFlow:
    """Test complete flow: defaults -> set -> save -> load -> verify."""

    def test_default_settings_complete_workflow(self):
        """Verify complete workflow: save defaults, load, modify, save, load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Step 1: Start with defaults
                defaults = DEFAULT_SETTINGS.copy()
                assert defaults["default_exposure"] == DEFAULT_SETTINGS["default_exposure"]

                # Step 2: Modify some settings
                modified = defaults.copy()
                modified["default_exposure"] = 0.077
                modified["default_camera_choice"] = "3"
                modified["default_start_freq"] = 333.0

                # Step 3: Save modifications
                assert save_settings(modified) is True

                # Step 4: Load fresh (simulate app restart)
                loaded = load_settings()

                # Step 5: Verify all modifications persisted
                assert loaded["default_exposure"] == 0.077, \
                    f"Exposure should be 0.077, got {loaded['default_exposure']}"
                assert loaded["default_camera_choice"] == "3", \
                    f"Camera choice should be '3', got {loaded['default_camera_choice']}"
                assert loaded["default_start_freq"] == 333.0, \
                    f"Start freq should be 333.0, got {loaded['default_start_freq']}"

    def test_settings_file_location(self):
        """Settings should be saved to ~/.espi/settings.json."""
        from settings_manager import _get_settings_path

        path = _get_settings_path()
        assert str(path).endswith(".espi/settings.json"), \
            f"Settings should be in ~/.espi/settings.json, got {path}"
        assert "espi" in str(path).lower(), "Path should contain 'espi'"

    def test_partial_settings_merge_with_defaults(self):
        """Loading partial settings should merge with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Save only one setting
            with open(settings_file, 'w') as f:
                json.dump({"default_exposure": 0.123}, f)

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                loaded = load_settings()

            # Should have the saved setting
            assert loaded["default_exposure"] == 0.123, "Saved value should be present"
            # Should also have all defaults for missing keys
            assert "default_camera_choice" in loaded, "Should have default camera choice"
            assert loaded["default_camera_choice"] == DEFAULT_SETTINGS["default_camera_choice"]


class TestSettingsValidation:
    """Verify settings are validated before saving."""

    def test_invalid_exposure_rejected(self):
        """Saving exposure <= 0 should fail validation."""
        from settings_manager import set_setting

        with patch("settings_manager._get_settings_path") as mock_path:
            mock_path.return_value = Path("/dev/null")

            # Try to set invalid exposure
            result = set_setting("default_exposure", -0.01)

            assert result is False, "Should reject negative exposure"

    def test_invalid_camera_choice_rejected(self):
        """Saving invalid camera choice should fail."""
        from settings_manager import set_setting

        with patch("settings_manager._get_settings_path") as mock_path:
            mock_path.return_value = Path("/dev/null")

            # Try to set invalid camera
            result = set_setting("default_camera_choice", "99")

            assert result is False, "Should reject invalid camera choice"

    def test_valid_settings_accepted(self):
        """Valid settings should pass validation and save."""
        from settings_manager import set_setting

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Save valid settings
                result = set_setting("default_exposure", 0.042)

            assert result is True, "Valid settings should save"
            with open(settings_file) as f:
                saved = json.load(f)
            assert saved["default_exposure"] == 0.042
