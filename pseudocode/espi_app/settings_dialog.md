# espi_app/settings_dialog.py - Settings Dialog

## Purpose

This file defines the SettingsDialog class, which is a window that lets users change application settings. It is opened when the user clicks the Settings button on the landing page.

## The SettingsDialog Class

The SettingsDialog is a PyQt6 QDialog, which is a pop-up window. Unlike the main window, dialogs are modal, meaning the user must close them before returning to the main application.

## What Users See

When a user clicks Settings, they see a window with tabs across the top:
- Hardware tab
- UI tab

(There used to be a third "Visualization" tab for choosing which graphs to show. It was removed entirely — it duplicated monitor_gui.py's own graph type picker, with no way for espi_app to actually apply the choice to either dashboard.)

At the bottom are Save and Cancel buttons.

## The Tabs Explained

### Hardware Tab

This tab lets users configure default camera and exposure settings:

1. Default Camera selection
   - Dropdown menu with three options: Basler, USB/webcam, Allied Vision
   - The choice code ("1", "2", or "3") is stored in settings

2. Default Exposure (seconds)
   - Number input box
   - Range: 0.001 to 10.0 seconds

3. Default Gain value
   - Number input box
   - Range: 0 to 100

4. Default Gain Factor value
   - Number input box
   - Range: 0 to 100

5. Preview Window Size
   - Dropdown: Small (640x480), Medium (1024x768), Large (1920x1080)
   - Sets the starting size of the live preview window. Default Medium. Always editable, regardless of "Use Last Settings as Default" — it is a window-size preference, not a measurement default.

**Locked by "Use Last Settings as Default":** When that UI-tab checkbox is on, fields 1-4 above (camera, exposure, gain, gain factor) are disabled and instead show whatever was actually last used to run a Monitor session or a Scan (Preview/Sweep), pulled from whichever dashboard ran most recently. See `_default_value_source()` below.

### UI Tab

This tab controls user interface preferences:

1. Theme selection
   - Dropdown with Light and Dark options
   - Light theme is several distinct shades of light gray (never pure white); dark theme is several shades of dark gray (never pure black)

2. Use Last Settings as Default checkbox
   - If checked: camera, exposure, gain, and gain factor (both here and in Monitor Mode's and Scan Mode's own Setup pages, plus Scan Mode's separate embedded Settings page) become auto-managed from whatever was actually last used in a real session, and all of those fields lock everywhere
   - If unchecked: those fields are manually editable here, and pushed out to both dashboards whenever this dialog is saved

3. Remember Window Position and Size checkbox
   - If checked, the app restores where the window was and how big it was last time
   - Default checked

4. Show Tooltips checkbox
   - If checked, hovering over a control shows a helper tooltip
   - Default checked

## How The Dialog Works

### __init__() - Initialization

1. Call parent class constructor (QDialog)
2. Set window title to "Settings"
3. Set window size to 500x400 pixels
4. Load the SettingsManager (to read current settings)
5. Create a vertical layout for the dialog
6. Create a tab widget
7. Build each tab by calling the create methods
8. Add each tab to the tab widget ("Hardware", "UI")
9. Add the tab widget to the main layout
10. Create bottom control buttons (Save, Cancel)
11. Add buttons to the layout
12. Set the layout on the dialog

### _create_hardware_tab() - Build Hardware Tab

1. Create a new widget (container)
2. Create a vertical layout
3. Read whether "Use Last Settings as Default" is on
4. Call `_default_value_source(locked)` to get (camera_choice, exposure, gain, gain_factor) to display — either espi_app's own saved values (unlocked) or the last-used-dashboard's values (locked)
5. Add label: "Default Camera:", build the dropdown, select the resolved camera choice, `setEnabled(not locked)`
6. Add label: "Default Exposure (s):", build the spinner, set the resolved value, `setEnabled(not locked)`
7. Add label: "Default Gain:", build the spinner (rounding a decimal source value, since this field is integer-only), set it, `setEnabled(not locked)`
8. Add label: "Default Gain Factor:", same as Gain
9. Add label and dropdown for Preview Window Size, load current value from settings — always enabled
10. Add a stretcher to fill remaining space
11. Set the layout on the widget
12. Return the widget

### _default_value_source(locked) - Where Hardware Tab Values Come From

1. If not locked: return espi_app's own saved `hardware.default_camera_choice`, `hardware.exposure_s`, `persistence.default_gain`, `persistence.default_gain_factor` — the plain, editable case
2. If locked: read the shared ESPI Full Algorithm settings file (`~/.espi/settings.json`) and check `last_used_dashboard`
   - `"monitor"` → return `default_camera_choice`, `monitor_default_exposure`, `monitor_default_gain`, `monitor_default_gain_factor` (monitor_gui.py's own keys, separate from Scan Mode's, since the two dashboards have different historical defaults)
   - `"scan"` → return `default_camera_choice`, `default_exposure`, `default_gain`, `default_gain_factor` (run_experiment_gui.py's own keys)
   - neither yet (nothing auto-saved so far) → fall back to espi_app's own values, same as the unlocked case

### _create_ui_tab() - Build UI Tab

1. Create a new widget
2. Create a vertical layout
3. Add label: "Theme:"
4. Create a dropdown with "Light" and "Dark" options
5. Load current theme from settings
6. Set dropdown to current theme
7. Create a checkbox: "Use Last Settings as Default"
8. Load and set its checked state
9. Create checkbox: "Remember Window Position and Size", load checked state
10. Create checkbox: "Show Tooltips", load checked state
11. Add a stretcher
12. Set layout and return widget

### _on_save() - Save Settings

When the user clicks the Save button:

1. Remember the old theme (to detect if it changed)
2. Remember whether the Hardware tab's fields were actually editable (`camera_combo.isEnabled()`) before this save — this is what decides whether `hardware_defaults_changed` fires at the end
3. Collect all values from the Hardware tab (camera, exposure, gain, gain factor, preview size) and set them via SettingsManager
4. Collect UI tab values (theme, remember-window-geometry, show-tooltips, use-last-settings-as-default) and set them
5. Write all settings to disk by calling SettingsManager.save()
6. If theme changed: emit `theme_changed` with the new theme name
7. If the Hardware tab's fields were editable in step 2: emit `hardware_defaults_changed` (no args) — not emitted when those fields were locked, since locked values are auto-managed, not something this Save actually set
8. Close the dialog with accept() (success status)

## PyQt6 Concepts Used

### QDialog
A modal window that must be closed before the user can interact with other windows.

### QTabWidget
A widget that shows tabs across the top. Each tab can contain different widgets.

### QCheckBox
A checkbox that users can click to toggle a boolean value.

### QComboBox
A dropdown menu that lets users select one option from a list.

### QSpinBox and QDoubleSpinBox
Number input boxes. QSpinBox is for integers, QDoubleSpinBox is for decimals.

### pyqtSignal
A signal is a message sent when something happens.
- `theme_changed(str)`: emitted when the user saves a new theme. The landing page listens for this and re-applies the theme app-wide.
- `hardware_defaults_changed()`: emitted when the Hardware tab's camera/exposure/gain/gain_factor were actually editable and just got saved. The landing page listens for this and pushes those values out to both dashboards — but only from this explicit Save, never just from opening a dashboard, so a value set locally inside a dashboard's own settings isn't silently overwritten by simply reopening it.

## Why This Design

By using tabs, the dialog keeps settings organized into logical groups: Hardware settings together, UI settings together. This makes it easier for users to find what they need.

By emitting signals instead of the dialog reaching into the main window directly, the dialog stays decoupled from what the main window does with the new values — it just announces "the theme changed" or "the hardware defaults changed," and the main window (`main_window.py`) decides what to do about it.

## Related Files

- main_window.py - Opens the SettingsDialog when Settings is clicked; connects both signals; owns `_sync_settings_to_espi_full_algorithm()` and `_push_hardware_defaults_to_espi_full_algorithm()`
- settings.py - Stores and retrieves settings
- styles.py - Applies the theme that users select here
- ESPI Full Algorithm/settings_manager.py - the shared settings file `_default_value_source()` reads from when locked
