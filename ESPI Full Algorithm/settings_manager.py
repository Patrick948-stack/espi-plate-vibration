"""
settings_manager.py
===================
Persistent configuration storage for run_experiment_gui.

Manages loading/saving user preferences (default camera, grayscale method,
capture defaults, etc.) to a JSON file. Provides a single point of truth
for all settings across the application, with validation and sensible defaults.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


# Default settings that apply if no config file exists
DEFAULT_SETTINGS = {
    "grayscale_method": "standard",
    "grayscale_color": "R",
    "default_camera_choice": "2",
    "default_camera_index": 0,
    "default_mode_choice": "1",  # "1"=pair subtraction, "2"=reference subtraction
    "show_gain": False,
    "show_compare_amplification_button": False,
    "show_compare_grayscale_button": False,
    "default_start_freq": 100.0,
    "default_end_freq": 1000.0,
    "default_step_size": 100.0,
    "default_n_averages": 5,
    "default_exposure": 0.01,
    "default_gain": 0.0,
    "default_gain_factor": 1.0,
    "default_amplitude": 1.0,  # Vpp, matches configure_channel()'s own default
    "default_offset": 0.0,     # Volts, matches configure_channel()'s own default
    "show_saved_image_after_capture": False,
    "theme": "dark",  # "light" or "dark" — espi_app writes its own choice here
    "preview_size": "Medium",  # "Small", "Medium", or "Large"
    # monitor_gui.py's own capture defaults, kept separate from
    # default_exposure/default_gain/default_gain_factor above (those are
    # run_experiment_gui's) since monitor mode has always used different
    # historical defaults (0.06s exposure vs 0.01s, for example) — sharing
    # one key between the two would silently change one dashboard's
    # defaults whenever the other's were bridged in.
    "monitor_default_exposure": 0.06,
    "monitor_default_gain": 1.0,
    "monitor_default_gain_factor": 10.0,
    # "Use Last Settings as Default", mirrored from espi_app's own
    # persistence.user_last_settings_as_default. When True, monitor_gui.py
    # and run_experiment_gui.py auto-save whatever was actually used in a
    # session as the new default (instead of a human typing a default in
    # manually), and lock their own default-value fields accordingly.
    "use_last_settings_as_default": False,
    # Which dashboard last auto-saved its settings while the flag above
    # was True — "monitor", "scan", or None if neither has yet. Lets
    # espi_app's own Hardware tab show the actual last-used values instead
    # of a stale, frozen number.
    "last_used_dashboard": None,
}

# Preview/dashboard window starting size, keyed by the same "Small",
# "Medium", "Large" labels espi_app's Settings dialog shows. The single
# source of truth for what each label means in pixels — espi_app imports
# this dict rather than keeping its own separate copy.
PREVIEW_SIZES = {
    "Small": (640, 480),
    "Medium": (1024, 768),
    "Large": (1920, 1080),
}


def _get_settings_path() -> Path:
    """
    Return the path to the settings JSON file.

    Uses ~/.espi/settings.json for user home directory storage.
    Returns a Path object pointing to the file.

    Time: O(1), Space: O(1)
    """
    return Path.home() / ".espi" / "settings.json"


def load_settings() -> Dict[str, Any]:
    """
    Load settings from disk, or return defaults if file doesn't exist.

    Attempts to read the settings JSON file. If it doesn't exist, returns
    a copy of DEFAULT_SETTINGS. If the file exists but is invalid JSON,
    prints a warning and falls back to defaults.

    Returns:
        dict: Settings with all keys from DEFAULT_SETTINGS, plus any
              extra keys that were in the saved file.

    Time: O(1) for default, O(keys) for validation merge
    Space: O(settings size)
    """
    settings_file = _get_settings_path()

    if not settings_file.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        with open(settings_file, 'r') as f:
            loaded = json.load(f)

        result = DEFAULT_SETTINGS.copy()
        result.update(loaded)
        return result

    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Could not load settings from {settings_file}: {e}")
        print("  Using default settings instead.")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    Save settings to disk as JSON.

    Ensures the directory exists, then writes the settings dict to the
    JSON file. Returns True on success, False on failure.

    Args:
        settings: Dictionary of settings to save

    Returns:
        bool: True if save succeeded, False otherwise

    Time: O(settings size) for JSON serialization
    Space: O(settings size) for the JSON string
    """
    settings_file = _get_settings_path()

    try:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except IOError as e:
        print(f"❌ Could not save settings to {settings_file}: {e}")
        return False


def validate_settings(settings: Dict[str, Any]) -> bool:
    """
    Validate that settings have reasonable values.

    Checks that numeric fields are in sensible ranges (e.g., exposure > 0,
    frequencies >= 0, camera index >= 0). Returns True if all checks pass,
    False otherwise. Prints warnings for invalid values.

    Args:
        settings: Dictionary of settings to validate

    Returns:
        bool: True if valid, False if any value is out of range

    Time: O(1) — fixed number of checks
    Space: O(1)
    """
    valid = True

    if settings.get("default_exposure", 0) <= 0:
        print(f"❌ Exposure must be > 0, got {settings.get('default_exposure')}")
        valid = False

    if settings.get("default_start_freq", 0) < 0:
        print(f"❌ Start frequency must be >= 0")
        valid = False
    if settings.get("default_end_freq", 0) < 0:
        print(f"❌ End frequency must be >= 0")
        valid = False
    if settings.get("default_step_size", 0) <= 0:
        print(f"❌ Step size must be > 0")
        valid = False

    if settings.get("default_n_averages", 1) < 1:
        print(f"❌ Frames per frequency must be >= 1")
        valid = False

    if settings.get("default_camera_index", 0) < 0:
        print(f"❌ Camera index must be >= 0")
        valid = False

    if settings.get("default_gain_factor", 1) <= 0:
        print(f"❌ Gain factor must be > 0")
        valid = False

    if settings.get("grayscale_method") not in ("standard", "single_channel"):
        print(f"❌ Grayscale method must be 'standard' or 'single_channel'")
        valid = False

    if settings.get("default_camera_choice") not in ("1", "2", "3"):
        print(f"❌ Camera choice must be '1', '2', or '3'")
        valid = False

    return valid


def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a single setting value by key, loading from disk if needed.

    Convenience function for accessing one setting without loading
    the entire settings dict. Useful for one-off reads.

    Args:
        key: Setting key to retrieve
        default: Value to return if key doesn't exist

    Returns:
        The setting value, or default if not found

    Time: O(settings size) — loads entire settings dict
    Space: O(settings size)
    """
    settings = load_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> bool:
    """
    Update a single setting and save to disk.

    Loads current settings, updates one key, validates, and saves.
    Returns True on success, False on failure.

    Args:
        key: Setting key to update
        value: New value for that key

    Returns:
        bool: True if update succeeded, False otherwise

    Time: O(settings size) — loads, updates, saves
    Space: O(settings size)
    """
    settings = load_settings()
    settings[key] = value

    if not validate_settings(settings):
        return False

    return save_settings(settings)
