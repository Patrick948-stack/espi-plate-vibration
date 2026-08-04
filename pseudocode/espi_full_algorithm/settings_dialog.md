# settings_dialog.py

## Purpose

The Settings page for `run_experiment_gui.py`: four groups of controls (Grayscale Conversion Method, Default Camera, Capture Settings Defaults, Live Monitoring During Sweep) that read from and save to `settings_manager`'s JSON file.

## Main Components

**LearnMoreDialog** — a small popup showing a plain-language explanation for a settings group, opened by that group's "Learn More" button.

**SettingsPage** — the page itself. Every control's current value maps to one key in `settings_manager.DEFAULT_SETTINGS`.

## Detailed Descriptions

### SettingsPage

#### `__init__()`

Builds the four groups described above, each wired so changing a radio button or checkbox that affects layout (grayscale method, camera choice, the gain checkbox) immediately shows/hides its dependent controls via `toggled` signals connected to `_update_grayscale_visibility()` / `_update_camera_visibility()` / `_update_capture_visibility()`. Ends with a **Save Settings** button and a status label.

**A real bug fixed here**: the constructor used to end with `if not self.isVisible(): self.setVisible(True)` — a leftover attempt to make Qt visibility signals "work better" in tests. In practice this made every `SettingsPage()` construction implicitly show itself as a real top-level window (since it has no parent yet at construction time), and — more importantly — it meant the widget was already "shown" before any test or real navigation event ever called `.show()` on it, so there was no hidden-to-visible transition left for `showEvent()` (see below) to ever fire from. Removed entirely; the page now behaves like every other bare `QWidget` until something actually shows it.

#### `showEvent(event)`

Calls `self.load_settings()` every time the page becomes visible — not just at construction. This is what makes the page always reflect the current file on disk, including changes another part of the app might have made, instead of showing stale state from whenever it happened to be constructed.

#### `_on_save_clicked()`

Wired to the Save Settings button. Calls `self.save_settings()` (below) and shows a one-line confirmation or failure message.

**The actual propagation bug**: before this button existed, `save_settings()` worked correctly on its own (round-trip tested), but nothing anywhere in `MainWindow` ever called it — no button, no signal. Every change a user made on this page was silently discarded the instant they navigated to a different tab. `SetupPage.reload_settings()` was reading the settings file correctly the whole time; it simply never had anything new to read, because this page never wrote anything.

#### `load_settings()` / `save_settings() -> bool`

Straightforward two-way mapping between every widget on the page and one key in the settings dict — grayscale method/color, default camera + index, `show_gain`, all the capture defaults, and the two Live Monitoring checkboxes (`show_live_feed_during_sweep`, `show_saved_image_after_capture`). `save_settings()` validates before writing and returns whether the write succeeded.

#### `_update_grayscale_visibility()` / `_update_camera_visibility()` / `_update_capture_visibility()`

Each shows or hides one group's dependent controls (the color combo, camera index spinner, gain label+spin) based on the relevant radio/checkbox state. Called once at the end of `__init__()` after the whole widget tree exists, and again automatically any time the relevant control's `toggled` signal fires.

#### `_apply_lock_state(settings)`

Called at the end of `load_settings()` (so every time the page becomes visible, not just at construction). Reads `settings.get("use_last_settings_as_default", False)` and, if True, calls `.setEnabled(False)` on the camera radios, `_index_spin`, `start_freq_spin`, `end_freq_spin`, `step_spin`, `n_averages_spin`, `exposure_spin`, `gain_spin`, `gain_factor_spin`, and the **Save Settings** button itself, since there is nothing left to hand-edit and save while these are auto-managed from a real sweep. If False, every one of those widgets is re-enabled instead.

Grayscale method/color, `show_gain`, and the two Live Monitoring checkboxes are deliberately left untouched either way, since those are display/processing preferences, not measurement defaults, and stay out of scope for this feature. Disabling the Save button does not stop `showEvent()`/`load_settings()` from keeping the displayed values current; it only stops the human from overwriting them by hand while `run_experiment_gui.py`'s own `MainWindow._save_last_used_settings_if_enabled()` is the sole writer of these keys.

## Key Concepts

### Why isVisible() is the wrong thing to test here

`QWidget.isVisible()` reflects real, on-screen visibility, which requires every ancestor up to the top-level window to actually be shown. A bare, unshown `SettingsPage()` — exactly what every test in this file constructs — reports every child widget's `isVisible()` as False regardless of what `setVisible()` calls were made internally. A test asserting a control "is hidden" using plain `isVisible()` on an unshown page will pass whether or not the underlying visibility logic is actually correct. `isVisibleTo(page)` (used in the newer tests) checks the same internal "would this be visible if page were shown" state `setVisible()` actually controls, without needing a real window.

## Why This Design

An explicit Save button, rather than autosaving on every keystroke, matches the pattern `SetupPage` already uses (it saves when the user clicks "Continue to Preview"): one predictable action that always writes the complete current form state, instead of guessing which single field change should trigger a write.

## Related Files

- [settings_manager.md](settings_manager.md) — the JSON load/save/validate functions this page calls
- [run_experiment_gui.md](run_experiment_gui.md) — SetupPage (reads the same settings, including the `show_gain` visibility this page's checkbox controls) and SweepPage (reads the two Live Monitoring checkboxes)
