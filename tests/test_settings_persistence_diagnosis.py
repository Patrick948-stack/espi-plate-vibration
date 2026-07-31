"""
test_settings_persistence_diagnosis.py
======================================
Diagnostic tests to reveal settings persistence failures.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ESPI Full Algorithm"))

from settings_manager import (
    load_settings, save_settings, get_setting, set_setting, DEFAULT_SETTINGS
)


class TestSettingsPersistenceOnDisk:
    """Verify settings actually persist to disk and are read back."""

    def test_save_creates_file_at_expected_location(self):
        """Settings should be written to ~/.espi/settings.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)

            with patch("settings_manager._get_settings_path") as mock_path:
                settings_file = fake_home / ".espi" / "settings.json"
                mock_path.return_value = settings_file

                # Save a setting
                result = save_settings({"default_exposure": 0.05})

                # Verify file was created
                assert result is True, "Save should return True"
                assert settings_file.exists(), f"File should exist at {settings_file}"

                # Verify file is valid JSON with the right content
                with open(settings_file) as f:
                    loaded = json.load(f)
                assert loaded["default_exposure"] == 0.05, "Saved value should match"

    def test_load_after_save_returns_same_values(self):
        """Save then load should preserve all settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            original = DEFAULT_SETTINGS.copy()
            original["default_exposure"] = 0.08
            original["default_start_freq"] = 250.0

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                save_settings(original)
                loaded = load_settings()

            # Verify all values round-trip correctly
            assert loaded["default_exposure"] == 0.08, f"Exposure mismatch: {loaded}"
            assert loaded["default_start_freq"] == 250.0, f"Freq mismatch: {loaded}"
            for key in DEFAULT_SETTINGS:
                assert key in loaded, f"Key '{key}' missing after load"

    def test_multiple_saves_overwrite_not_append(self):
        """Each save should overwrite previous, not append."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Save once
                save_settings({"default_exposure": 0.01})
                # Save again with different value
                save_settings({"default_exposure": 0.99})
                # Load
                loaded = load_settings()

            # Should have the latest value, not both
            assert loaded["default_exposure"] == 0.99, "Should have latest value"

    def test_settings_survive_application_restart_simulation(self):
        """Simulate app closing and reopening with same settings file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Session 1: Save settings
            with patch("settings_manager._get_settings_path", return_value=settings_file):
                original = DEFAULT_SETTINGS.copy()
                original["default_camera_choice"] = "3"
                original["default_exposure"] = 0.033
                save_settings(original)

            # Session 2: Load settings (simulating app restart)
            with patch("settings_manager._get_settings_path", return_value=settings_file):
                loaded = load_settings()

            assert loaded["default_camera_choice"] == "3", "Camera choice should persist across restart"
            assert loaded["default_exposure"] == 0.033, "Exposure should persist across restart"


class TestGetSetSingleSetting:
    """Verify get/set functions work correctly for individual settings."""

    def test_get_setting_reads_from_saved_file(self):
        """get_setting should read the actual saved value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Save specific value
                save_settings({"default_exposure": 0.042})
                # Get it back
                value = get_setting("default_exposure")

            assert value == 0.042, f"Should get saved value, got {value}"

    def test_set_setting_writes_to_disk(self):
        """set_setting should actually write to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Use set_setting
                result = set_setting("default_start_freq", 150.0)
                assert result is True, "set_setting should succeed"

                # Verify it's actually in the file
                with open(settings_file) as f:
                    saved = json.load(f)
                assert saved["default_start_freq"] == 150.0, "Value should be in disk file"

    def test_set_setting_persists_across_separate_load(self):
        """Value set with set_setting should survive separate load() call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                # Step 1: Set a value
                set_setting("default_exposure", 0.055)

                # Step 2: Load settings independently (simulating restart)
                loaded = load_settings()

            assert loaded["default_exposure"] == 0.055, "Set value should persist across load()"


class TestSettingsManagerEdgeCases:
    """Test edge cases that might break settings persistence."""

    def test_nonexistent_settings_file_loads_defaults(self):
        """If file doesn't exist, should return defaults (not crash)."""
        with patch("settings_manager._get_settings_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/path/settings.json")

            result = load_settings()

            assert isinstance(result, dict), "Should return dict"
            assert "default_exposure" in result, "Should have default keys"

    def test_corrupted_json_loads_defaults(self):
        """If JSON is corrupted, should print warning and return defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_file.write_text("{ invalid json }")

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                result = load_settings()

            # Should fall back to defaults instead of crashing
            assert isinstance(result, dict), "Should return dict even with corrupt file"
            assert "default_exposure" in result, "Should have defaults"

    def test_empty_settings_file_loads_defaults(self):
        """Empty settings file should return defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"
            settings_file.write_text("{}")

            with patch("settings_manager._get_settings_path", return_value=settings_file):
                result = load_settings()

            # Should have all default keys filled in
            for key in DEFAULT_SETTINGS:
                assert key in result, f"Key '{key}' should be in result after loading empty file"
