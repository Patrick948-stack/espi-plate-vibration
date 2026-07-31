"""
test_settings.py

Tests for the SettingsManager class.

Verifies that settings can be loaded, saved, and retrieved correctly
from ~/.espi_app/settings.json.
"""

import json
import tempfile
from pathlib import Path
import pytest

# We need to add the parent directory to the path so we can import espi_app
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from espi_app.settings import SettingsManager


@pytest.fixture
def temp_config_dir(monkeypatch):
    """
    Create a temporary directory for settings during testing.

    This fixture:
    1. Creates a temporary directory
    2. Monkeypatches SettingsManager to use it instead of ~/.espi_app/
    3. Cleans up after the test

    This way, tests don't interfere with the user's real settings.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        # Monkeypatch Path.home() to return our temp directory
        # This makes SettingsManager think ~/.espi_app/ is actually our tmpdir/.espi_app/
        monkeypatch.setattr(
            "espi_app.settings.Path.home",
            lambda: tmppath,
        )
        yield tmppath


def test_settings_creates_default_on_first_run(temp_config_dir):
    """
    Test that a fresh SettingsManager creates default settings.

    When there's no ~/.espi_app/settings.json file yet,
    SettingsManager should load factory defaults.
    """
    mgr = SettingsManager()

    # Verify defaults are loaded
    assert mgr.get("hardware.exposure_ms") == 5.0
    assert mgr.get("ui.theme") == "light"
    assert mgr.get("visualization.show_histogram") is True


def test_settings_get_with_dot_notation(temp_config_dir):
    """
    Test that dot-notation get() works correctly.

    Should be able to navigate nested dicts with "a.b.c" syntax.
    """
    mgr = SettingsManager()

    # Get nested values
    exposure = mgr.get("hardware.exposure_ms")
    assert exposure == 5.0

    theme = mgr.get("ui.theme")
    assert theme == "light"


def test_settings_set_with_dot_notation(temp_config_dir):
    """
    Test that dot-notation set() works correctly.

    Should be able to update nested values.
    """
    mgr = SettingsManager()

    # Set a value
    mgr.set("hardware.exposure_ms", 15.0)

    # Verify it changed
    assert mgr.get("hardware.exposure_ms") == 15.0

    # Verify other values weren't affected
    assert mgr.get("ui.theme") == "light"


def test_settings_save_and_load(temp_config_dir):
    """
    Test that settings persist to disk and reload correctly.

    When you save(), the settings should be written to JSON.
    When you create a new SettingsManager, it should load from that JSON.
    """
    # Create first manager and modify a setting
    mgr1 = SettingsManager()
    mgr1.set("hardware.exposure_ms", 20.0)
    mgr1.set("ui.theme", "dark")
    mgr1.save()
    # Now settings.json should exist with these values

    # Create a second manager — it should load from the saved file
    mgr2 = SettingsManager()

    # Verify the settings were loaded
    assert mgr2.get("hardware.exposure_ms") == 20.0
    assert mgr2.get("ui.theme") == "dark"


def test_settings_file_is_valid_json(temp_config_dir):
    """
    Test that saved settings.json is valid, readable JSON.

    Someone might open settings.json in a text editor.
    We should make sure it's formatted nicely and parseable.
    """
    mgr = SettingsManager()
    mgr.set("hardware.exposure_ms", 12.5)
    mgr.save()

    # Read the file directly
    with open(mgr.config_file, "r") as f:
        content = f.read()

    # Parse it as JSON (will raise if invalid)
    data = json.loads(content)

    # Verify the value is there
    assert data["hardware"]["exposure_ms"] == 12.5


def test_settings_multiple_sets_before_save(temp_config_dir):
    """
    Test that multiple set() calls work correctly.

    You can call set() multiple times before calling save().
    """
    mgr = SettingsManager()

    # Make multiple changes
    mgr.set("hardware.exposure_ms", 10.0)
    mgr.set("hardware.frame_rate_fps", 60)
    mgr.set("ui.theme", "dark")
    mgr.set("visualization.show_histogram", False)

    # All should be in memory
    assert mgr.get("hardware.exposure_ms") == 10.0
    assert mgr.get("hardware.frame_rate_fps") == 60
    assert mgr.get("ui.theme") == "dark"
    assert mgr.get("visualization.show_histogram") is False

    # Save once
    mgr.save()

    # New manager should have all changes
    mgr2 = SettingsManager()
    assert mgr2.get("hardware.exposure_ms") == 10.0
    assert mgr2.get("ui.theme") == "dark"


def test_settings_directory_created_if_missing(temp_config_dir):
    """
    Test that SettingsManager creates ~/.espi_app/ if it doesn't exist.

    This is important because ~/.espi_app/ might not exist on first run.
    """
    # Before creating SettingsManager, directory shouldn't exist
    config_dir = Path(temp_config_dir) / ".espi_app"
    assert not config_dir.exists()

    # Create manager
    mgr = SettingsManager()

    # Directory should now exist
    assert config_dir.exists()


def test_settings_graceful_fallback_for_missing_keys(temp_config_dir):
    """
    Test that missing keys fall back to defaults (for settings migrations).

    When a key doesn't exist in the saved settings (e.g., after a schema
    change), get() should return the default value instead of crashing.
    """
    mgr = SettingsManager()

    # Manually remove a key from settings to simulate schema mismatch
    del mgr.settings["hardware"]["default_camera_choice"]
    mgr.save()

    # Create a new manager that loads the incomplete settings
    mgr2 = SettingsManager()

    # Getting the missing key should return the default, not crash
    camera_choice = mgr2.get("hardware.default_camera_choice")
    assert camera_choice == "1"  # Should be the default
