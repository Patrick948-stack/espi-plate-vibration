# settings_manager.py

## Purpose

Reads and writes the one JSON file (`~/.espi/settings.json`) that stores every persisted preference shared by `run_experiment_gui.py` and `monitor_gui.py`: default camera, grayscale method, capture defaults (exposure, gain, frequencies), the theme, the preview window size, and the two Live Monitoring checkboxes. Plain functions, no class — every caller imports `load_settings`, `save_settings`, `validate_settings` directly. `espi_app` also reads and writes this same file (see `main_window.py`'s `_sync_settings_to_espi_full_algorithm()`), which is how a choice made in espi_app's Settings dialog reaches Monitor Mode and Scan Mode.

## Main Functions

### `DEFAULT_SETTINGS` (dict)

The factory defaults used whenever no settings file exists yet, or a saved file is missing a key. Includes `show_gain` (False), `show_compare_amplification_button` (False), `show_compare_grayscale_button` (False, both control whether monitor_gui.py's Live Monitor page shows its two optional Compare buttons), `show_saved_image_after_capture` (False), `theme` ("dark" — matches both dashboards' original, only look before theming existed), `preview_size` ("Medium"), `default_mode_choice` ("1", pair subtraction), `default_amplitude` (1.0, Vpp) and `default_offset` (0.0, V) — run_experiment_gui.py's Signal Generator defaults, matching `configure_channel()`'s own long-standing hardcoded values, now threaded all the way through `run_experiment.run_pipeline()` into the six `complete_pipeline*.py` sweep functions instead of being frozen there — and monitor_gui.py's own capture defaults `monitor_default_exposure` (0.06), `monitor_default_gain` (1.0), and `monitor_default_gain_factor` (10.0).

These `monitor_default_*` keys are kept separate from `default_exposure` / `default_gain` / `default_gain_factor` above (which are run_experiment_gui.py's own) because the two dashboards have always used different historical defaults — sharing one key between them would silently change one dashboard's defaults whenever the other's were bridged in from espi_app.

Also includes two keys that make "Use Last Settings as Default" (a checkbox in espi_app's own Settings dialog) actually mean something here:

- `use_last_settings_as_default` (False): mirrored from espi_app's `persistence.user_last_settings_as_default`, bridged in every time espi_app syncs. Both dashboards read this at Setup-page construction time (and `reload_settings()`) to decide whether to lock their own camera/exposure/gain/frequency fields — while locked, those fields are auto-managed from whatever a real session actually used, not typed in by hand.
- `last_used_dashboard` (None): set to `"monitor"` or `"scan"` by whichever dashboard just auto-saved its current values (only happens while the flag above is True — see `MainWindow._save_last_used_settings_if_enabled()` in both `monitor_gui.py` and `run_experiment_gui.py`). Lets espi_app's own Hardware tab know which dashboard's specific keys (`monitor_default_*` vs `default_*`) to show.

### `PREVIEW_SIZES` (dict)

Maps "Small", "Medium", "Large" labels to pixel dimensions (for example, "Medium" → (1024, 768)). Both dashboards' `MainWindow.__init__` import this dict directly to size their starting window. espi_app's Settings dialog shows the same three labels but keeps its own separate copy of the dict (not imported from here), since coupling that dialog to `ESPI Full Algorithm`'s sys.path just to share three tuples was not worth the added dependency — keep both in sync by hand if the pixel values ever change.

### `load_settings() -> dict`

1. If `~/.espi/settings.json` does not exist, return a copy of `DEFAULT_SETTINGS`.
2. If it exists, load it and layer it on top of a fresh `DEFAULT_SETTINGS` copy, so any key added to `DEFAULT_SETTINGS` after a user's file was last saved still has a sensible value.
3. If the file exists but is not valid JSON, print a warning and fall back to defaults instead of crashing.

### `save_settings(settings: dict) -> bool`

Writes the whole dict to `~/.espi/settings.json` as pretty-printed JSON, creating the parent directory if needed. Returns True on success, False if the write failed (e.g. permissions).

### `validate_settings(settings: dict) -> bool`

Sanity-checks numeric ranges (exposure > 0, frequencies >= 0, step > 0, n_averages >= 1, camera index >= 0, gain_factor > 0) and that `grayscale_method` / `default_camera_choice` are one of the allowed values. Prints a specific warning for each failing field. Called by `SettingsPage.save_settings()` before writing to disk, so an invalid value never overwrites a good saved file.

### `get_setting(key, default=None)` / `set_setting(key, value) -> bool`

Convenience one-off read/write helpers that load the whole file, touch one key, and (for `set_setting`) validate and save again. Not the primary path — `SettingsPage` and `SetupPage` both load/save the whole dict at once instead, since they always have several fields to update together.

## Key Concepts

### One shared file, many readers

`SettingsPage`, `SetupPage`, and `SweepPage` all call `load_settings()` independently, at the moment each of them actually needs current values (construction, `reload_settings()`, or `begin()`) rather than caching a value from earlier. That is what makes a change on one page visible to another: the file is the single source of truth, and every page re-reads it instead of being told about changes by another page directly.

### Why this file needed test isolation

Every test in this project that touches settings used to read and write the real `~/.espi/settings.json` on whatever machine ran the suite, with no isolation. `tests/conftest.py`'s autouse `_isolate_settings_file` fixture now monkeypatches `_get_settings_path()` to a per-test temporary file, so tests can never see or corrupt a developer's real saved settings, and never depend on whatever was left on disk from a previous run.

## Related Files

- [settings_dialog.md](settings_dialog.md) — the Settings page UI that reads/writes through this module
- [run_experiment_gui.md](run_experiment_gui.md) — SetupPage and SweepPage, two of the readers
- [monitor_gui.md](monitor_gui.md) — SetupPage, another reader (its own defaults are the `monitor_default_*` keys)
- [theme.md](theme.md) — reads the `theme` key this file stores to decide which stylesheet to apply
- `espi_app/main_window.py`'s `_sync_settings_to_espi_full_algorithm()` — writes into this same file from espi_app's own Settings dialog
