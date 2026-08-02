# ESPI Full Algorithm/theme.py - Shared Light/Dark Theme

## Purpose

Defines one shared set of light/dark color tokens and one stylesheet builder used by monitor_gui.py, run_experiment_gui.py, and (through espi_app/styles.py) espi_app's landing page and Settings dialog. This is what makes a single theme choice style every window in the project the same way, instead of each dashboard hardcoding its own separate dark-only look.

## Why This File Exists

Before this file existed, monitor_gui.py and run_experiment_gui.py each had their own copy of a "strictly monochrome dark theme" stylesheet, with the same colors typed out twice. Neither dashboard could ever look light, no matter what espi_app's Settings said, because they always forced their own dark stylesheet onto the whole application the moment they opened.

Putting the color tokens and stylesheet in one file, shared by both dashboards (and, through espi_app/styles.py, by espi_app too) means:
1. A color only ever needs to change in one place
2. Both dashboards automatically stay visually consistent with each other (which their own code comments already said was the goal)
3. Light mode becomes possible everywhere at once, instead of needing to be built three separate times

## DARK and LIGHT

Two dictionaries of named color tokens (`base_bg`, `surface_bg`, `text_primary`, `border`, and so on). Both dashboards' widgets use object names (like `#Sidebar`, `#PrimaryButton`, `#LogConsole`) that the stylesheet targets, so the same token names work for every widget in both files.

Light theme is deliberately never pure white (`#ffffff`) — every "light" surface is one of several distinct shades of light gray, the same way dark theme is never pure black. This keeps both themes feeling like a coherent design system instead of a plain color inversion.

## colors(theme_name)

Returns the DARK or LIGHT dictionary. Any value other than exactly "light" falls back to DARK, matching every window's original hardcoded look from before theming existed.

## icon_color(theme_name) and icon_color_secondary(theme_name)

Return the hex color qtawesome icons should use for this theme: the main (primary text) color, or the muted (secondary text) color for things like a "Learn More" button's small icon.

Icons are drawn once as a bitmap at whatever color they are given — unlike a stylesheet color, an already-created icon does not update itself when the theme changes. Anything that wants to follow a live theme switch has to re-create its icons using these functions, which both dashboards' `refresh_theme()` methods do.

## build_stylesheet(theme_name)

Returns the complete QSS stylesheet string for "light" or "dark", covering every object name and widget type used anywhere in the project: the sidebar and nav rail, group boxes, buttons (including the primary "call to action" button style), spin boxes and combo boxes, checkboxes, tabs, the log console, the progress bar, and more.

A selector that does not match anything in a particular window (for example, `QPlainTextEdit#LogConsole` only exists in run_experiment_gui.py) simply never triggers there. This is why one shared stylesheet is safe to apply to every window in the project, even though no single window uses every rule in it.

## How Each Window Uses This File

- **monitor_gui.py**: reads the current theme from `settings_manager.load_settings()["theme"]`, calls `build_stylesheet()` plus its own extra nav-item-height rule (see `monitor_gui._stylesheet_for()`), and re-colors its own icons using `icon_color()`/`icon_color_secondary()`
- **run_experiment_gui.py**: same pattern, without the extra height rule
- **espi_app/styles.py**: imports this module (adding `ESPI Full Algorithm` to `sys.path` first) and calls `build_stylesheet()` directly

## Why This Design

- `ESPI Full Algorithm` has no dependency on espi_app, so `python3 monitor_gui.py` and `python3 run_experiment_gui.py` still work completely standalone, with no espi_app installed
- espi_app depends on this file (the same direction it already depends on monitor_gui.py and run_experiment_gui.py themselves), not the other way around
- One theme choice, whichever window it was made from, now looks the same everywhere

## Related Files

- `monitor_gui.py`, `run_experiment_gui.py` - both import this module directly
- `espi_app/styles.py` - imports this module to apply the theme app-wide from the landing page
- `settings_manager.py` - stores the "theme" key both dashboards read from when run standalone
