"""
settings.py

Manages application-wide settings — saving them to disk, loading them,
and providing a clean API to get/set individual values.

All settings are stored in ~/.espi_app/settings.json so they persist
across app restarts.
"""

import json
import os
from pathlib import Path


class SettingsManager:
    """
    Central manager for all app settings.

    Usage:
        mgr = SettingsManager()
        exposure = mgr.get("hardware.exposure_s")  # Get a value
        mgr.set("hardware.exposure_s", 0.01)       # Set a value
        mgr.save()                                  # Write to disk
    """

    def __init__(self):
        """
        Initialize the settings manager.

        - Creates ~/.espi_app/ directory if it doesn't exist
        - Loads settings from disk if they exist
        - Uses factory defaults on first run

        Example:
            mgr = SettingsManager()
            # Settings are now loaded from disk or defaults
        """
        # Use Path() for cross-platform path handling
        # Path.home() returns /Users/patrick on Mac, C:\Users\patrick on Windows, etc.
        self.config_dir = Path.home() / ".espi_app"
        self.config_file = self.config_dir / "settings.json"

        # Create directory if it doesn't exist
        # exist_ok=True means: don't error if it already exists
        self.config_dir.mkdir(exist_ok=True)

        # Load settings from disk, or use defaults if this is first run
        self.settings = self._load_settings()

    def _load_settings(self) -> dict:
        """
        Load settings from ~/.espi_app/settings.json.

        If the file doesn't exist (first run), return factory defaults.
        If the file exists, load and return it.

        Returns:
            dict: Settings dictionary with all user preferences

        Example:
            mgr = SettingsManager()
            # _load_settings() is called automatically in __init__()
            # On first run: returns factory defaults
            # On subsequent runs: loads saved settings from disk
        """
        if self.config_file.exists():
            # File exists — load it
            with open(self.config_file, "r") as f:
                return json.load(f)
        else:
            # First run — return defaults
            return self._default_settings()

    def _default_settings(self) -> dict:
        """
        Return factory default settings.

        These are the settings a new user gets on first run.
        Structure mirrors what the UI expects.

        Returns:
            dict: Default settings dictionary

        Example:
            defaults = mgr._default_settings()
            exposure = defaults['hardware']['exposure_s']  # 0.05 seconds
            theme = defaults['ui']['theme']  # 'light'
        """
        return {
            "hardware": {
                "default_camera_choice": "1",  # "1"=Basler, "2"=USB/webcam, "3"=Allied Vision
                "exposure_s": 0.05,
                "control_gain": False,
                "control_gain_factor": True,
                "preview_size": "Medium",  # "Small", "Medium", or "Large"
            },
            "persistence": {
                "user_last_settings_as_default": False,
                "default_exposure_s": 0.05,
                "default_camera_choice": "1. Basler",
                "default_gain": 1,
                "default_gain_factor": 1,
            },
            "ui": {
                "theme": "light",
                "window_width": 1200,
                "window_height": 800,
                "window_geometry": "",  # base64 QByteArray from saveGeometry(), set on close
                "remember_window_geometry": True,
                "show_tooltips": True,
            },
        }

    def get(self, key_path: str):
        """
        Fetch a setting using dot-notation path.

        If a key doesn't exist (e.g., after a settings migration), return the
        default value for that key instead.

        Args:
            key_path: Dot-separated path (e.g., "hardware.exposure_s")

        Returns:
            The value at that path, or the default if missing

        Example:
            mgr = SettingsManager()
            exposure = mgr.get("hardware.exposure_s")  # 0.05
            theme = mgr.get("ui.theme")  # "light"
            gain = mgr.get("persistence.default_gain")  # 1

            # If a setting is missing (migration case):
            # Returns the default value for that setting automatically
        """
        # Split by dots to navigate nested dicts
        keys = key_path.split(".")

        # Start at the root of settings
        value = self.settings

        # Navigate through each key
        try:
            for key in keys:
                value = value[key]
            return value
        except KeyError:
            # Key doesn't exist — return default instead
            # This handles settings migrations gracefully
            default_value = self._default_settings()
            for key in keys:
                default_value = default_value[key]
            return default_value

    def set(self, key_path: str, value):
        """
        Set a setting using dot-notation path.

        Changes only the in-memory copy. Call save() to persist to disk.

        Args:
            key_path: Dot-separated path (e.g., "hardware.exposure_s")
            value: The new value to set

        Raises:
            KeyError: If the path doesn't exist

        Example:
            mgr = SettingsManager()
            mgr.set("hardware.exposure_s", 0.01)
            mgr.set("ui.theme", "dark")
            mgr.set("persistence.default_gain", 25)
            mgr.save()  # Write changes to disk
        """
        # Split by dots: "hardware.exposure_s" → ["hardware", "exposure_s"]
        keys = key_path.split(".")

        # Navigate to the parent of the final key
        # For ["hardware", "exposure_s"]:
        # keys[-1] means "the last element"
        # (negative indices count from the end in Python).
        # keys[:-1] means "everything except the last element"
        # (a slice from the start up to, but not including, index -1).
        #   - keys[:-1] is ["hardware"]
        #   - keys[-1] is "exposure_s"
        obj = self.settings
        for key in keys[:-1]:
            obj = obj[key]

        # Set the final key to the new value
        obj[keys[-1]] = value

    def save(self):
        """
        Write current settings to disk.

        Saves to ~/.espi_app/settings.json with nice indentation
        so it's human-readable if someone opens it in a text editor.

        Example:
            mgr = SettingsManager()
            mgr.set("hardware.exposure_s", 0.1)
            mgr.set("ui.theme", "dark")
            mgr.save()  # Writes to ~/.espi_app/settings.json
        """
        with open(self.config_file, "w") as f:
            # indent=2 makes it readable (not all on one line)
            json.dump(self.settings, f, indent=2)
