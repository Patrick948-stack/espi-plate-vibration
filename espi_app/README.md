# espi_app — Unified Landing Page GUI

A single PyQt6 window that ties the two existing dashboards together:
Monitor Mode (`monitor_gui.py`) and Scan Mode (`run_experiment_gui.py`),
both of which live in `ESPI Full Algorithm/`. Instead of remembering
which script to run for which task, you run one app and pick a mode.

## Running it

From the project root, using the same virtual environment that has
PyQt6, qtawesome, cv2, and matplotlib installed (see
`ESPI Full Algorithm/venv_physics`):

```bash
python -m espi_app.main
```

## What it does

The landing page shows two mode buttons, plus Settings and Help:

* **Monitor Mode** — opens `monitor_gui.py`'s dashboard for watching the
  live camera feed and frame subtraction, without running a full
  frequency sweep.
* **Scan Mode** — opens `run_experiment_gui.py`'s dashboard for running
  a full frequency sweep experiment (Setup, Preview, Sweep, Results).
* **Settings** — configure default camera, exposure, gain, and theme.
  Settings persist to `~/.espi_app/settings.json`.
* **Help** — a short summary of what each mode does.

Both dashboards open in their own window, independent of the landing
page. Clicking a mode button again while its window is already open just
brings that window to the front instead of opening a second one. Closing
a dashboard window re-enables its button on the landing page.

## Theme

Light and dark theme (and every icon color) is shared across all three
windows — the landing page, Monitor Mode, and Scan Mode — via
`ESPI Full Algorithm/theme.py`. Changing the theme in Settings updates
every currently open window immediately, and is saved so a dashboard
opened later (or run standalone with `python3 monitor_gui.py`, with no
espi_app involved at all) starts on the same theme. Light mode is always
several distinct shades of light gray, never pure white; dark mode is
always several shades of dark gray, never pure black.

## Settings

Configurable from the Settings dialog, organized into two tabs:

**Hardware** — default camera, exposure, gain, gain factor, preview
window size. (The old Visualization tab was removed entirely — it only
duplicated Monitor Mode's own graph type picker, with no way to actually
apply the choice to either dashboard.)

**UI** — light/dark theme, "Use Last Settings as Default", whether to
remember window position and size, and whether to show tooltips.

Theme and preview size always bridge into
`ESPI Full Algorithm/settings_manager.py`'s own settings file
(`~/.espi/settings.json`), the same one Monitor Mode and Scan Mode read
their own defaults from. Camera, exposure, gain, and gain factor bridge
too, but how depends on "Use Last Settings as Default":

* **Off (default)** — the Hardware tab's values are the starting
  defaults for both dashboards. Editing them here and saving pushes them
  out immediately. A change made *inside* a dashboard's own Setup page
  or Settings page stays local to that dashboard and is not overwritten
  just by reopening it from espi_app.
* **On** — the Hardware tab (and both dashboards' own Setup/Settings
  fields for camera, exposure, gain, gain factor, and — in Scan Mode —
  frequencies/step/averages) become read-only. Whichever dashboard you
  actually run (a Monitor session or a Scan sweep) auto-saves its
  current values as the new shared defaults the moment it starts, and
  the Hardware tab live-pulls and displays whichever dashboard ran most
  recently. To edit any of these by hand again, turn the toggle off
  first.

## Tests

```bash
python -m pytest espi_app/tests/ -v
```

Tests run with `QT_QPA_PLATFORM=offscreen` automatically (set in
`espi_app/tests/conftest.py`), so no display is needed. They also
redirect `~/.espi_app/settings.json` to a temporary per-test directory,
so running the suite never touches your real saved settings.

## Files

* `main.py` — application entry point
* `main_window.py` — `LandingPage`, including the Monitor/Scan launch logic
* `settings.py` — `SettingsManager`, reads and writes `~/.espi_app/settings.json`
* `settings_dialog.py` — the Settings window
* `styles.py` — applies the shared theme (`ESPI Full Algorithm/theme.py`) app-wide
* `tests/` — pytest-qt regression tests
