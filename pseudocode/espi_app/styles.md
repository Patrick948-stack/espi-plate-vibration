# espi_app/styles.py - Theme Application

## Purpose

This file applies a light or dark theme to the whole espi_app QApplication. The actual color tokens and stylesheet text now live in `ESPI Full Algorithm/theme.py`, shared with monitor_gui.py and run_experiment_gui.py, so one theme choice styles the landing page, the Settings dialog, and both dashboards together.

## Why The Colors Moved Out Of This File

Originally this file had its own separate LIGHT_THEME and DARK_THEME strings, and monitor_gui.py and run_experiment_gui.py each had their own separate, hardcoded, dark-only stylesheet. That meant three different color definitions to keep in sync, and no way for espi_app's theme choice to affect the other two windows at all (opening Monitor or Scan mode always looked dark, regardless of what the user picked in Settings).

Now there is one shared stylesheet builder in `ESPI Full Algorithm/theme.py`. `styles.py` is just the thin espi_app-side entry point to it.

## _ensure_espi_algorithm_on_path()

Adds the `ESPI Full Algorithm` folder to `sys.path` so `theme.py` can be imported, the same way `main_window.py` does for `monitor_gui.py` and `run_experiment_gui.py`. See that file's copy of this helper for the full explanation.

## apply_theme(app, theme_name)

1. Make sure `ESPI Full Algorithm` is on `sys.path`
2. Import `theme`
3. Normalize theme_name to exactly "light" or "dark"
4. Call `theme.build_stylesheet(normalized_name)` and set it as the whole QApplication's stylesheet

Every widget in every open window (landing page, Settings dialog, Monitor mode, Scan mode) immediately re-renders with the new colors, since Qt stylesheets apply at the application level.

## icon_color(theme_name)

Returns the hex color espi_app's own qtawesome icons (Monitor Mode, Scan Mode, Settings, Help buttons) should use for the given theme. Delegates to `theme.icon_color()`. Icons are static bitmaps, not stylesheet-driven, so `main_window.py` has to re-create them (see its `refresh_theme_icons()`) whenever the theme changes — this function is what supplies the correct color to re-create them with.

## LANDING_ACCENTS, landing_accent_colors(theme_name)

The mode cards on the landing page (see `mode_card.md`) use a small set
of colors of their own, card background, card border, hover background,
icon badge background, and divider color, one set for light and one for
dark. These live in a plain dictionary, `LANDING_ACCENTS`, in this file
rather than in `ESPI Full Algorithm/theme.py`, because they are scoped
to espi_app's landing page alone; monitor_gui.py and run_experiment_gui.py
never use them. `landing_accent_colors(theme_name)` just looks up and
returns the right half of that dictionary for "light" or "dark".

## text_secondary_color(theme_name)

Returns the shared theme's muted, secondary text color (used for the
mode card descriptions and the landing page's footer text) for the
given theme, by reading `theme.colors(normalized)["text_secondary"]`
from the shared `ESPI Full Algorithm/theme.py`.

## Why This Design

- One color palette, defined once, used everywhere (landing page, Settings dialog, Monitor mode, Scan mode)
- Light theme is always several shades of gray, never pure white; dark theme is always several shades of gray, never pure black
- `ESPI Full Algorithm/theme.py` has no dependency on espi_app, so `monitor_gui.py` and `run_experiment_gui.py` keep working standalone (`python3 monitor_gui.py`) with no espi_app installed at all
- espi_app is the one that depends on `ESPI Full Algorithm/theme.py` (the same direction espi_app already depends on monitor_gui.py and run_experiment_gui.py themselves), not the other way around

## Related Files

- `ESPI Full Algorithm/theme.py` - the actual color tokens and stylesheet builder
- `main.py` - calls apply_theme() at startup
- `main_window.py` - calls apply_theme() when theme changes, reads landing_accent_colors() and text_secondary_color() to style the logo, mode cards, and footer, and bridges the theme choice into `ESPI Full Algorithm`'s own settings file so Monitor/Scan mode agree even when opened standalone
- `mode_card.py` - its cards are colored from landing_accent_colors()
- `logo.py` - the logo widget itself picks which pre-rendered pixmap to show per theme, not a color from this file
- `settings.py` - stores the user's theme preference
- `settings_dialog.py` - lets users change the theme setting
