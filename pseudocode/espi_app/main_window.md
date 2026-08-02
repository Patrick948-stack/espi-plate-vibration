# espi_app/main_window.py - Landing Page (Main Window)

## Purpose

This file defines the LandingPage class, which is the first window users see when they open the application. The landing page shows two mode choices and provides access to settings and help.

## The LandingPage Class

The LandingPage is a PyQt6 QMainWindow, which is a main application window. It has a title bar, buttons, and other widgets organized in a layout.

### What The Landing Page Displays

When the app starts, users see, top to bottom:

1. The ESPI logo (see `logo.md`), centered
2. A title: "ESPI Camera System"
3. A subtitle: "Electronic Speckle Pattern Interferometry Control"
4. A small horizontal divider line
5. Two large mode selection cards side by side (stacked instead, one
   above the other, if the window is narrower than 800px wide, see
   `_apply_responsive_layout()` below):
   - Monitor Mode card: icon, title, divider, two line description
   - Scan Mode card: icon, title, divider, two line description
6. At the bottom, two control buttons: Settings and Help
7. A footer line, "Select a mode to begin", flanked by two small dots

The two cards are not plain buttons. They are `ModeCard`, a custom
widget defined in `mode_card.py` (see `mode_card.md`), since a
QPushButton can only show one line of text and each card needs an icon,
a title, and a separate description line.

### __init__() - Initialization

When the landing page is created:

1. Call the parent class constructor (QMainWindow)
2. Load the SettingsManager to access saved settings
3. Set window properties:
   - Window title: "ESPI Camera Control"
   - Window position and size: restored from the last session if
     "Remember Window Position and Size" is on and geometry was saved
     before, otherwise the configured default width/height (see
     _restore_or_default_geometry())
4. Create a central widget
5. Create a vertical layout (widgets stack top to bottom)
6. Set spacing and margins (padding) for a clean look
7. Build all the UI components, using the current theme's icon color,
   and this file's own landing-page accent colors (see
   `styles.md`'s `landing_accent_colors()`), for everything below:
   - Create and add the logo (an `ESPILogo`, see `logo.md`)
   - Create and add the title label and subtitle label
   - Create and add a small divider line
   - Create a horizontal layout (`self._card_layout`) for the two
     `ModeCard` widgets (see `mode_card.md`), Monitor Mode and Scan
     Mode, each with a tooltip
   - Connect both cards' `clicked` signal to their handler functions
   - Call `_apply_card_stylesheet()` to color the two cards
   - Add the card layout to the main layout
   - Add a stretcher (pushes bottom buttons down)
   - Create the bottom control buttons (Settings, Help)
   - Connect control button handlers
   - Create the footer label and its two flanking dot labels
8. Set the layout on the central widget
9. Make the central widget the window's main content
10. Apply "Show Tooltips": if off, clear the Monitor/Scan card tooltips
    that step 7 just set (see _apply_tooltip_settings())
11. Call `_apply_responsive_layout()` once, so the cards start in the
    correct side-by-side or stacked arrangement for the window's
    starting size

### resizeEvent(event) / _apply_responsive_layout() - Responsive Card Layout

Qt calls `resizeEvent()` automatically whenever the window is resized;
this override just calls `_apply_responsive_layout()` again after the
default handling. That method checks the window's current width against
`_NARROW_WIDTH_BREAKPOINT` (800px): at or below it, the card layout's
direction is switched to top-to-bottom (cards stack vertically); above
it, left-to-right (cards sit side by side). A `QHBoxLayout`'s direction
can be changed live with `setDirection()`, which is what makes this
possible without rebuilding the layout from scratch.

### _apply_card_stylesheet(theme_name, accents) - Style the Mode Cards

Builds one small stylesheet string, using the accent colors passed in,
for the two cards' background, border, hover background, and
description text color, and applies it to both `ModeCard` widgets. Kept
separate from the shared `ESPI Full Algorithm/theme.py` stylesheet
(monitor_gui.py and run_experiment_gui.py never see these colors) since
the mode cards are a landing-page-only visual element.

### _restore_or_default_geometry() - Window Position and Size

1. Resize to the configured default width/height (`ui.window_width`,
   `ui.window_height`) as a baseline
2. If "Remember Window Position and Size" is off, stop here
3. If no geometry has ever been saved yet, stop here (keep the default)
4. Otherwise, decode the saved base64 QByteArray and call
   restoreGeometry() with it, which restores exact position and size
   from the last session (a monitor no longer connected just falls back
   to Qt's own on-screen placement)

### _apply_tooltip_settings() - Show Tooltips

If "Show Tooltips" is on, set the Monitor/Scan buttons' descriptive
tooltips; if off, clear them to empty strings. Called once during
__init__(), and again after the Settings dialog closes (whether saved or
cancelled) so a change takes effect immediately.

### closeEvent(event) - Save Window Geometry

If "Remember Window Position and Size" is on, encode the current
saveGeometry() as base64 and save it to `ui.window_geometry` before
closing. If the setting is off, geometry is left untouched (an old
saved geometry from before the user turned this off is not cleared,
just ignored until re-enabled).

### _on_monitor_clicked() - Monitor Button Handler

When the user clicks the Monitor Mode button:
1. Call _launch_child_window(), telling it to track the window in
   self._monitor_window, disable self.monitor_button while it is open,
   and build the window using _create_monitor_window()

### _create_monitor_window() - Builds monitor_gui's Dashboard

1. Call _sync_settings_to_espi_full_algorithm() so monitor_gui.py's own
   MainWindow.__init__ picks up espi_app's current theme, preview size,
   and "Use Last Settings as Default" flag the moment it reads settings
   (camera/exposure/gain are not touched here — see
   _push_hardware_defaults_to_espi_full_algorithm())
2. Add the "ESPI Full Algorithm" folder to sys.path (see
   _ensure_espi_algorithm_on_path() below), since monitor_gui.py imports
   its own helper modules with plain names like `import monitor`
3. Import monitor_gui.MainWindow only now, not at the top of the file,
   so camera and matplotlib libraries are not loaded until Monitor Mode
   is actually opened
4. Construct and return a monitor_gui.MainWindow instance

### _on_scan_clicked() - Scan Button Handler

When the user clicks the Scan Mode button:
1. Call _launch_child_window(), telling it to track the window in
   self._scan_window, disable self.scan_button while it is open, and
   build the window using _create_scan_window()

### _create_scan_window() - Builds run_experiment_gui's Dashboard

1. Call _sync_settings_to_espi_full_algorithm() (same as monitor mode)
2. Add the "ESPI Full Algorithm" folder to sys.path
3. Import run_experiment_gui.MainWindow, whose own __init__ now reads
   the just-synced theme, preview size, and hardware defaults itself
   (no need to poke its stylesheet from outside anymore)
4. Construct and return a run_experiment_gui.MainWindow instance

### _sync_settings_to_espi_full_algorithm(theme_override=None) - Look-and-Feel Bridge

monitor_gui.py and run_experiment_gui.py read their own defaults from a
separate settings file (`~/.espi/settings.json`, via
`ESPI Full Algorithm/settings_manager.py`) that espi_app's own settings
(`~/.espi_app/settings.json`) never touched before. This method bridges
the two, but only for things safe to re-push every time a dashboard is
opened or the theme changes:

1. Load the other settings file's current contents
2. Copy espi_app's theme and preview size into it — purely how-it-looks
   / how-big-it-starts preferences that should always match the landing
   page
3. Copy "Use Last Settings as Default" into it too, unconditionally,
   as `use_last_settings_as_default` — both dashboards read this to
   decide whether to lock their own default-value fields and whether to
   auto-save on a run
4. Save the merged settings back to the other file

Camera/exposure/gain/gain_factor are deliberately **not** touched here —
see `_push_hardware_defaults_to_espi_full_algorithm()` below. Called from
`_create_monitor_window`, `_create_scan_window`, and `_on_theme_changed`.

`theme_override` lets `_on_theme_changed()` pass the just-changed theme
directly, since it fires before self.settings_manager necessarily
reflects a theme just saved from the Settings dialog (see that method).

### _push_hardware_defaults_to_espi_full_algorithm() - Hardware Defaults Bridge

Pushes espi_app's own Hardware tab values (camera, exposure, gain, gain
factor) into both dashboards' settings keys — the same value into
run_experiment_gui.py's `default_*` keys and monitor_gui.py's own
`monitor_default_*` keys (camera choice is one key already shared by
both).

Only ever called from a Settings Save that actually had these fields
editable (connected to the `hardware_defaults_changed` signal in
`_on_settings_clicked`, see below) — never from opening a dashboard, and
never while "Use Last Settings as Default" has them locked. That is what
makes a value the user set locally inside a dashboard's own settings
stick, instead of getting silently overwritten the next time that
dashboard is simply reopened from espi_app.

1. Reload self.settings_manager from disk first (this fires from inside
   the Settings dialog's still-running modal loop, same staleness
   concern as `_on_theme_changed()`)
2. Read camera choice, exposure, gain, gain_factor from
   self.settings_manager
3. Write them into both dashboards' keys in the shared settings file
4. Save

### _launch_child_window(attr_name, button, window_factory, label) - Shared Launch Logic

Both Monitor Mode and Scan Mode need the same bookkeeping, so this one
helper does it for both:

1. If a window is already open for this mode (self._monitor_window or
   self._scan_window is not None), just raise and focus that window
   instead of opening a second one
2. Disable the button that was clicked, so the user cannot start a
   second launch while the first one is still being built
3. Build the window (window_factory already synced settings and applied
   the shared theme by this point). If building it raises an exception
   (for example, a camera SDK is not installed), re-enable the button
   and show an error message box instead of crashing
4. Mark the window WA_DeleteOnClose, so that closing it actually
   destroys the Qt object (and fires the destroyed signal) instead of
   just hiding it
5. Store the window on self (self._monitor_window or self._scan_window)
   and show it
6. Connect the window's destroyed signal to a small cleanup function
   that clears the stored reference and re-enables the button

### refresh_theme_icons(theme_name) - Re-color Landing Page Icons

Re-creates the Monitor/Scan/Settings/Help button icons at the given
theme's color. A QIcon is a static bitmap baked at one fixed color, so
it does not follow along when the stylesheet changes — this is what
actually makes the landing page's own icons match a live theme switch.

### _ensure_espi_algorithm_on_path() - Module-Level Helper

monitor_gui.py and run_experiment_gui.py live in the "ESPI Full
Algorithm" folder and use flat imports (`import monitor`,
`import live_graphs`) that only resolve when that folder is on
sys.path. Running either script directly adds its own folder
automatically; since espi_app launches them as a library instead, this
function adds the folder to sys.path itself, once, the first time
either mode is opened.

### _on_settings_clicked() - Settings Button Handler

When the user clicks the Settings button:
1. Create a SettingsDialog (from settings_dialog.py)
2. Connect the dialog's theme_changed signal to _on_theme_changed
3. Connect the dialog's hardware_defaults_changed signal to
   _push_hardware_defaults_to_espi_full_algorithm
4. Show the dialog as a modal window (user must close it before returning to main window)
5. If an error occurs, show an error message box
6. Either way (finally): reload self.settings_manager from disk — the
   dialog owns its own separate SettingsManager instance, so this
   window's copy would otherwise stay stale after a save — and
   re-apply _apply_tooltip_settings() in case Show Tooltips changed

### _on_theme_changed(new_theme) - Theme Change Handler

When the user changes the theme in settings:
1. Reload self.settings_manager from disk (see why in
   _on_settings_clicked above — this fires from inside the dialog's
   still-running modal loop, before that method's own reload runs)
2. Get the current PyQt6 application instance and call apply_theme() —
   every open window's stylesheet updates immediately, since Qt
   stylesheets apply at the whole-application level
3. Call refresh_theme_icons(new_theme) for this window's own icons
4. Call _sync_settings_to_espi_full_algorithm(theme_override=new_theme)
   so a Monitor/Scan window opened later also starts on the new theme
5. If self._monitor_window is open, call its refresh_theme(new_theme)
6. If self._scan_window is open, call its refresh_theme(new_theme)

### _on_help_clicked() - Help Button Handler

When the user clicks the Help button:
1. Create a help text string explaining the two modes and Settings
   (plain text, no emoji, so it renders consistently everywhere)
2. Show a message box with this information

## Why This Design

By centralizing mode selection in one place:
- Users have a clear entry point
- They understand their options immediately
- Switching between modes is simple (just come back to this page)
- Settings can be accessed from anywhere in the app
- The application has a consistent, professional appearance

## Key PyQt6 Concepts

### QMainWindow
A QMainWindow is PyQt6's standard main application window. It has:
- A title bar (shows "ESPI Camera Control")
- A central widget (the main content area)
- Optional menu bars and tool bars

### QWidget
A QWidget is a container for other widgets. It can hold buttons, labels, layouts, etc.

### Layouts
Layouts organize widgets:
- QVBoxLayout stacks widgets vertically (top to bottom)
- QHBoxLayout stacks widgets horizontally (left to right)

### Signals and Slots
PyQt6 uses a signal/slot system for handling events:
- Signal: Something happens (button clicked, value changed)
- Slot: A function to call when the signal occurs
- Connect: Link a signal to a slot with clicked.connect()

### addStretch()
This adds an invisible expandable space that pushes other widgets to the edges.

## Related Files

- main.py - Creates and shows the LandingPage
- settings.py - Manages application settings
- settings_dialog.py - Lets users modify settings
- styles.py - Provides theme styling (delegates to ESPI Full Algorithm/theme.py)
- monitor_gui.py - Monitor mode dashboard, launched by _on_monitor_clicked()
- run_experiment_gui.py - Scan mode dashboard, launched by _on_scan_clicked()
- ESPI Full Algorithm/settings_manager.py - the settings file _sync_settings_to_espi_full_algorithm() bridges into
