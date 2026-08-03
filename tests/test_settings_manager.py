"""
test_settings_manager.py
========================
Tests for settings_manager.py — configuration persistence and validation.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import (
    load_settings,
    save_settings,
    validate_settings,
    get_setting,
    set_setting,
    DEFAULT_SETTINGS,
    _get_settings_path,
)


class TestDefaultSettings:
    """Verify DEFAULT_SETTINGS contains all expected keys."""

    def test_default_settings_has_all_required_keys(self):
        """All required setting keys should be present in DEFAULT_SETTINGS."""
        required_keys = {
            "grayscale_method",
            "grayscale_color",
            "grayscale_backend",
            "default_camera_choice",
            "default_camera_index",
            "default_mode_choice",
            "show_gain",
            "default_start_freq",
            "default_end_freq",
            "default_step_size",
            "default_n_averages",
            "default_exposure",
            "default_gain",
            "default_gain_factor",
            "default_amplitude",
            "default_offset",
            "show_saved_image_after_capture",
            "theme",
            "preview_size",
            "monitor_default_exposure",
            "monitor_default_gain",
            "monitor_default_gain_factor",
            "use_last_settings_as_default",
            "last_used_dashboard",
        }
        assert set(DEFAULT_SETTINGS.keys()) == required_keys

    def test_default_values_are_sensible(self):
        """Default values should pass validation."""
        assert validate_settings(DEFAULT_SETTINGS)

    def test_default_exposure_is_positive(self):
        """Exposure should be > 0."""
        assert DEFAULT_SETTINGS["default_exposure"] > 0

    def test_default_gain_factor_is_positive(self):
        """Gain factor should be > 0."""
        assert DEFAULT_SETTINGS["default_gain_factor"] > 0


class TestLoadSettings:
    """Test loading settings from disk."""

    def test_load_defaults_when_file_not_found(self):
        """If settings file doesn't exist, should return DEFAULT_SETTINGS copy."""
        with patch("settings_manager._get_settings_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/path/settings.json")
            settings = load_settings()
            assert settings == DEFAULT_SETTINGS
            assert settings is not DEFAULT_SETTINGS

    def test_load_settings_from_valid_json(self):
        """Should load and merge settings from valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            test_settings = {"default_start_freq": 200.0, "default_exposure": 0.05}
            with open(settings_file, 'w') as f:
                json.dump(test_settings, f)

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                loaded = load_settings()

            assert loaded["default_start_freq"] == 200.0
            assert loaded["default_exposure"] == 0.05
            assert loaded["grayscale_method"] == DEFAULT_SETTINGS["grayscale_method"]

    def test_load_handles_corrupt_json(self, capsys):
        """Should print warning and return defaults if JSON is invalid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_file.write_text("{ invalid json }")

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                settings = load_settings()

            assert settings == DEFAULT_SETTINGS
            captured = capsys.readouterr()
            assert "Could not load settings" in captured.out

    def test_load_handles_file_read_error(self, capsys):
        """Should handle IOError gracefully."""
        with patch("settings_manager._get_settings_path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.open.side_effect = IOError("Permissions denied")
            mock_path.return_value = mock_file

            settings = load_settings()
            assert settings == DEFAULT_SETTINGS
            captured = capsys.readouterr()
            assert "Could not load settings" in captured.out


class TestSaveSettings:
    """Test saving settings to disk."""

    def test_save_creates_directory(self):
        """Should create parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "subdir" / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                result = save_settings({"test": "value"})

            assert result is True
            assert settings_file.exists()

    def test_save_writes_valid_json(self):
        """Should write settings as valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            test_settings = {"default_start_freq": 150.0, "grayscale_method": "standard"}

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                result = save_settings(test_settings)

            assert result is True
            with open(settings_file, 'r') as f:
                saved = json.load(f)
            assert saved["default_start_freq"] == 150.0

    def test_save_returns_false_on_io_error(self, capsys):
        """Should return False and print error if write fails."""
        with patch("settings_manager._get_settings_path") as mock_path:
            mock_file = MagicMock()
            mock_file.parent.mkdir.side_effect = IOError("Permission denied")
            mock_path.return_value = mock_file

            result = save_settings({"test": "value"})

            assert result is False
            captured = capsys.readouterr()
            assert "Could not save settings" in captured.out


class TestValidateSettings:
    """Test settings validation."""

    def test_valid_settings_pass(self):
        """Valid settings should pass all checks."""
        assert validate_settings(DEFAULT_SETTINGS)

    def test_exposure_must_be_positive(self, capsys):
        """Exposure <= 0 should fail validation."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["default_exposure"] = 0
        assert validate_settings(invalid) is False
        captured = capsys.readouterr()
        assert "Exposure must be > 0" in captured.out

    def test_frequencies_must_be_non_negative(self, capsys):
        """Frequencies < 0 should fail validation."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["default_start_freq"] = -1
        assert validate_settings(invalid) is False

    def test_step_size_must_be_positive(self, capsys):
        """Step size <= 0 should fail validation."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["default_step_size"] = 0
        assert validate_settings(invalid) is False

    def test_n_averages_must_be_at_least_one(self, capsys):
        """n_averages < 1 should fail validation."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["default_n_averages"] = 0
        assert validate_settings(invalid) is False

    def test_gain_factor_must_be_positive(self, capsys):
        """gain_factor <= 0 should fail validation."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["default_gain_factor"] = 0
        assert validate_settings(invalid) is False

    def test_grayscale_method_must_be_valid(self, capsys):
        """grayscale_method must be 'standard' or 'single_channel'."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["grayscale_method"] = "invalid"
        assert validate_settings(invalid) is False

    def test_camera_choice_must_be_valid(self, capsys):
        """camera_choice must be '1', '2', or '3'."""
        invalid = DEFAULT_SETTINGS.copy()
        invalid["default_camera_choice"] = "4"
        assert validate_settings(invalid) is False


class TestGetSetting:
    """Test single-setting getter."""

    def test_get_existing_setting(self):
        """Should return value of existing key."""
        with patch("settings_manager.load_settings") as mock_load:
            mock_load.return_value = {"test_key": "test_value"}
            result = get_setting("test_key")
            assert result == "test_value"

    def test_get_nonexistent_setting_returns_default(self):
        """Should return default for nonexistent key."""
        with patch("settings_manager.load_settings") as mock_load:
            mock_load.return_value = {}
            result = get_setting("nonexistent", default="fallback")
            assert result == "fallback"


class TestSetSetting:
    """Test single-setting setter."""

    def test_set_valid_setting_saves(self):
        """Should update and save valid setting."""
        with patch("settings_manager.load_settings") as mock_load:
            with patch("settings_manager.save_settings") as mock_save:
                mock_load.return_value = DEFAULT_SETTINGS.copy()
                mock_save.return_value = True

                result = set_setting("default_start_freq", 250.0)

                assert result is True
                called_settings = mock_save.call_args[0][0]
                assert called_settings["default_start_freq"] == 250.0

    def test_set_invalid_setting_does_not_save(self):
        """Should not save if validation fails."""
        with patch("settings_manager.load_settings") as mock_load:
            with patch("settings_manager.save_settings") as mock_save:
                mock_load.return_value = DEFAULT_SETTINGS.copy()

                result = set_setting("default_exposure", -0.1)

                assert result is False
                mock_save.assert_not_called()


class TestIntegration:
    """Integration tests with real files."""

    def test_save_and_load_roundtrip(self):
        """Save and load should produce identical results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            original = DEFAULT_SETTINGS.copy()
            original["default_start_freq"] = 333.0
            original["grayscale_method"] = "single_channel"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                save_settings(original)
                loaded = load_settings()

            assert loaded["default_start_freq"] == 333.0
            assert loaded["grayscale_method"] == "single_channel"
