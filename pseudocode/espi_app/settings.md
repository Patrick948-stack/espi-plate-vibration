# espi_app/settings.py - Settings Manager

## Purpose

This module manages all application settings. It handles loading settings from disk on startup, saving changes when the user updates preferences, and providing a clean interface for other parts of the app to read and write settings.

All settings are stored in a JSON file at ~/.espi_app/settings.json so they persist across app restarts.

## The SettingsManager Class

### What It Does

The SettingsManager is a single object that other parts of the application use to access settings. It works like this:

1. Reads settings from disk when created
2. Provides methods to get and set individual settings
3. Writes changes back to disk when asked
4. Handles missing settings gracefully by returning defaults

### Key Methods

#### __init__()
When you create a SettingsManager:
1. Determine the config directory path (~/.espi_app)
2. Create the directory if it doesn't exist yet
3. Load settings from settings.json if it exists
4. If the file doesn't exist, use factory default settings

#### _load_settings()
Loads settings from ~/.espi_app/settings.json:
1. Check if the file exists
2. If yes, read the JSON and return it
3. If no, return factory defaults

#### _default_settings()
Returns a dictionary with all default settings. This is used on first run. The defaults include:

**Hardware Settings:**
- default_camera_choice: Which camera to use ("1" for Basler, "2" for USB, "3" for Allied Vision)
- exposure_s: How long the camera sensor captures light (in seconds)
- control_gain: Whether to adjust the camera gain
- control_gain_factor: Whether to adjust the gain factor
- preview_size: "Small", "Medium", or "Large", the preview window's starting size. Default "Medium"

(There used to be a Visualization category here — show_intensity_graph, show_histogram, show_3d_graph, show_log_histogram, show_live_feed, auto_rescale — removed entirely along with the Visualization tab, since it duplicated monitor_gui.py's own graph type picker with no way to actually apply the choice to either dashboard.)

**Persistence Settings:**
- user_last_settings_as_default: If true, camera/exposure/gain/gain_factor (here and in both dashboards' own Setup pages) become auto-managed from whatever was actually last used in a real Monitor session or Scan, and those fields lock everywhere. Bridged into the shared `ESPI Full Algorithm/settings_manager.py` file as `use_last_settings_as_default`, which both dashboards read to decide their own lock state. If false, values are set by hand here (and in Scan Mode's own separate Settings page) and pushed out to both dashboards on Save.
- default_exposure_s: Default exposure time in seconds
- default_camera_choice: Default camera choice code
- default_gain: Default gain value
- default_gain_factor: Default gain factor value

**UI Settings:**
- theme: "light" or "dark"
- window_width: Default window width in pixels, used when no geometry has been saved yet
- window_height: Default window height in pixels, used when no geometry has been saved yet
- window_geometry: Base64-encoded QByteArray from the window's saveGeometry(), written on close. Default "" (nothing saved yet)
- remember_window_geometry: Whether to restore window position/size from the last session. Default True
- show_tooltips: Whether hovering over controls shows helper tooltips. Default True

#### get(key_path)
Retrieves a single setting value using dot notation:
- Input: a path like "hardware.exposure_ms" or "ui.theme"
- Process: Split by dots and navigate through nested dictionaries
- Output: The value at that path
- If the key doesn't exist: Return the default value instead

Example:
```
mgr.get("hardware.exposure_ms") returns 5.0
mgr.get("ui.theme") returns "light"
```

#### set(key_path, value)
Changes a single setting value:
- Input: a path like "hardware.exposure_ms" and a new value like 10.0
- Process: Split the path by dots, navigate to the parent dictionary, set the final key
- Output: The value is now changed in memory

Example:
```
mgr.set("hardware.exposure_ms", 10.0)
mgr.set("ui.theme", "dark")
```

Note: This only changes the value in memory. To save it to disk, call save().

#### save()
Writes all current settings to ~/.espi_app/settings.json:
1. Open the file for writing
2. Convert the settings dictionary to JSON format
3. Write it with nice indentation (2 spaces) so it is human-readable
4. Close the file

## Settings Structure (JSON Format)

The settings file looks like this:

```json
{
  "hardware": {
    "default_camera_choice": "1",
    "exposure_ms": 5.0,
    "control_gain": false,
    "control_gain_factor": false
  },
  "persistence": {
    "remember_last_settings": true,
    "last_used_exposure": 5.0,
    "last_used_camera_choice": "1"
  },
  "ui": {
    "theme": "light",
    "window_width": 1200,
    "window_height": 800
  }
}
```

## Why This Design

By centralizing all settings in one SettingsManager class:
- Other parts of the app don't need to know about JSON file handling
- Settings are loaded once at startup and kept in memory for speed
- Changes are simple: just call set() and save()
- Missing settings are handled gracefully (return defaults)
- Settings are human-readable in the JSON file

## Key Concepts

### Dot Notation
Instead of writing:
```
settings["hardware"]["exposure_ms"]
```

We use dot notation:
```
settings_mgr.get("hardware.exposure_ms")
```

This is cleaner and easier to read.

### Nested Dictionaries
Settings are organized into categories using nested dictionaries:
- hardware: All camera-related settings
- persistence: What to remember between sessions
- ui: User interface preferences

This organization makes settings easier to find and understand.

### Graceful Degradation
If a setting is missing (maybe from an older version of the app), the get() method returns the default value instead of crashing. This allows the app to upgrade smoothly.

## Related Files

- main.py - Uses SettingsManager to load settings at startup
- main_window.py - Passes SettingsManager to other dialogs
- settings_dialog.py - Allows users to modify settings
- styles.py - Uses theme setting to apply colors
