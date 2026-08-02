# run_experiment_gui.py

**Purpose**: PyQt6 dashboard application for ESPI camera control. Replaces terminal-based run_experiment.py with a graphical multi-page interface (Setup, Preview, Sweep, Results, Settings) for configuring and running frequency sweeps.

---

## Main Components

### 1. Utility Functions (Top Level)

#### `_frame_to_pixmap(frame: np.ndarray) -> QPixmap`
Converts a grayscale numpy array (from camera grab) into a Qt image for display.
- Takes: 2D uint8 array (height x width)
- Returns: QPixmap object that can be displayed in QLabel
- Why: Camera frames are raw numpy arrays, but Qt widgets need QPixmap/QImage

#### `_total_sweep_steps(params) -> int`
Calculates total number of frequency steps in the sweep.
- Formula: (end_freq - start_freq) / step + 1
- Used by: SweepWorker to set progress bar maximum and calculate percentages

#### `_suppress_cv2_windows()`
Context manager that temporarily disables cv2.imshow() and cv2.waitKey() during sweep.
- Why: cv2 window functions crash when called from background threads. We stub them to do nothing.

---

### 2. EmittingStream Class

**Purpose**: Redirects sweep print() output into Qt signals so SweepWorker can show progress in the GUI.

#### `__init__()`
Initializes empty buffer for accumulating text.

#### `write(text: str)`
Called by print() statements. Accumulates text until a newline arrives, then emits the complete line.

#### `flush()`
Does nothing (required by stdout protocol).

#### `text_written` Signal
Emitted with each complete line of output. Connected to log console and progress parser.

---

### 3. SetupPage Class

**Purpose**: First page user sees. Mirrors run_experiment.py's terminal questions (camera, mode, frequencies, etc.) as GUI controls.

#### `__init__()`
Creates UI sections, laid out in a 2x2 grid (Camera / Mode on top,
Frequency sweep / Capture settings below), plus a third row spanning
both columns:
1. Camera selection (radio buttons: Basler, USB, Allied Vision)
2. Subtraction mode (radio buttons: Pair, Reference)
3. Frequency sweep parameters (spinboxes: start, end, step, n_averages)
4. Capture settings (spinboxes: exposure, gain, gain_factor, output folder)
5. Signal Generator (spinboxes: amplitude in Vpp, DC offset in Volts) —
   its own `QGroupBox`, spanning the full width of row 2 of the grid
   (`grid.addWidget(sg_group, 2, 0, 1, 2)`), since amplitude/offset are a
   distinct concern from camera capture settings. Range bounds come from
   `sdg_control.limits` (`MIN_AMPLITUDE`/`MAX_AMPLITUDE` = 0.002-20.0 Vpp;
   the offset spinbox itself uses a static +/-`VOLTAGE_RAIL` (10V) range —
   the real legal offset narrows as amplitude grows via
   `clamp_offset()`, but `configure_channel()` already enforces that
   dynamic clamp before anything reaches the instrument, so the spinbox
   does not need to track amplitude_spin live to stay hardware-safe).
   Defaults come from `default_amplitude`/`default_offset` in the shared
   settings file (1.0 Vpp / 0.0 V, matching `configure_channel()`'s own
   long-standing defaults).

Ends by calling `_apply_lock_state(settings)`: if `use_last_settings_as_default` is on (set from espi_app's Settings dialog, bridged into this shared settings file), the camera radios, mode radios, frequency spinboxes, n_averages, exposure, gain, gain_factor, amplitude, and offset are all disabled — those values are now auto-managed from whatever a real Preview/Sweep actually used, not typed in by hand (see `MainWindow._save_last_used_settings_if_enabled()`). `output_dir_edit`/`browse_button`/`continue_button` are not tracked defaults and always stay editable.

#### `camera_choice() -> str`
Returns selected camera ("1"=Basler, "2"=USB, "3"=Allied Vision)

#### `mode_choice() -> str`
Returns selected mode ("1"=Pair, "2"=Reference)

#### `get_params() -> dict`
Returns all sweep parameters as dict (start_freq, end_freq, step, exposure, gain, gain_factor, amplitude, offset, output_dir). `amplitude`/`offset` flow from here through `run_experiment.run_pipeline()`'s `base_params` (read with `.get(key, default)` so `run_experiment.py`'s own terminal CLI, whose `choose_sweep_params()` does not collect these yet, keeps working unchanged) into whichever of the six `complete_pipeline*.py` sweep functions is chosen, replacing what used to be a hardcoded `amplitude=1.0, offset=0.0` inside each one's own `configure_channel()` call.

#### `reload_settings()`
Loads saved settings from disk and updates all UI controls to match.
- Called when user navigates back to Setup from other pages
- Ensures Setup always shows current saved settings, not old UI state
- Updates: camera selection, mode, all frequencies, exposure, gain, etc.
- Also calls `_update_gain_visibility(settings)` (see below) so a
  `show_gain` value the user changed in Settings actually takes effect,
  not just the gain number itself
- Also calls `_apply_lock_state(settings)` so the current
  "Use Last Settings as Default" lock state is reflected too, not just
  the values

#### `_update_gain_visibility(settings)`
Shows or hides the Gain (dB) label and spin box based on
`settings.get("show_gain", False)`. Called both at construction and from
`reload_settings()`. Fixes a real reported bug: the Gain field previously
had no visibility logic connected to this setting at all — it was simply
always shown, regardless of what the "Show Gain (dB) control" checkbox on
the Settings page said.

---

### 4. CameraPreviewWorker Class

**Purpose**: Background thread that grabs camera frames continuously for preview display.

#### `__init__(camera_choice, exposure_s, gain, grayscale_method)`
Stores parameters for camera connection.
- Validates camera_choice, exposure > 0, grayscale_method in ["standard", "single_channel"]
- Sets up stop flag and internal state

#### `stop()`
Sets flag to exit grab loop on next iteration.

#### `run()`
Main worker loop:
1. Imports camera module (based on camera_choice)
2. Connects to camera (validates tuple return and unpacks correctly)
3. Sets exposure and gain
4. Grabs frames in loop (one every 66ms = ~15 fps)
5. Emits frame_ready signal for each frame
6. Handles exceptions (AttributeError, RuntimeError, ValueError)
7. Always disconnects camera in finally block (cleanup guarantee)

#### Signals
- `frame_ready`: Emitted with each grabbed numpy array
- `error`: Emitted on connection/runtime errors
- `finished_cleanly`: Emitted when worker stops (even if error occurred)

---

### 5. PreviewPage Class

**Purpose**: Shows live camera feed and lets user confirm settings before sweep.

#### `__init__()`
Creates UI: label for video feed, "Lock in settings & continue" button, instruction text.

#### `start_preview(camera_choice, exposure_s, gain, grayscale_method)`
Creates and starts CameraPreviewWorker with given parameters.

#### `is_running() -> bool`
Returns True if worker thread is still grabbing frames.

#### `stop_and_wait()`
Signals worker to stop and waits for thread to finish before returning.
- Ensures camera is disconnected before method returns
- Called by hideEvent (when user leaves page) as safety net

#### `hideEvent(event)`
Automatically stops preview if user navigates away without clicking "Lock in".

#### `_stop_and_continue()`
Stops preview worker and emits `continued` signal to trigger sweep stage.

#### `_on_frame(frame: np.ndarray)`
Called when frame_ready signal fires. Converts frame to pixmap and displays in label.

#### `_on_error(message: str)`
Shows error dialog if camera connection/grab fails.

#### `continued` Signal
Emitted when user clicks "Lock in settings & continue".

---

### 6. SweepWorker Class

**Purpose**: Background thread that runs frequency_sweep() from complete_pipeline*.py, capturing data and monitoring progress.

#### `__init__(camera_choice, mode_choice, params, stream)`
Stores all parameters. Stream is EmittingStream that captures print() output.

#### `stop()`
Sets cooperative stop flag checked by frequency_sweep() once per frequency.

#### `run()`
Main worker:
1. Imports correct pipeline module (complete_pipeline.py, inclusive, or allied_vision)
2. Suppresses cv2 windows (they crash in threads)
3. Redirects stdout to EmittingStream
4. Calls frequency_sweep() or reference_frequency_sweep()
5. Parses stdout for progress ("Sweeping frequency: X Hz")
6. Emits progress signal with parsed frequency
7. Emits finished_sweep when complete or if user stops

#### Signals
- `progress`: Emitted with (frequency_hz, total_steps, current_step) for progress bar
- `error`: Emitted on sweep runtime errors
- `finished_sweep`: Emitted with (results_dict, output_dir) when sweep complete

#### Why stdout parsing?
Adding callback parameter to 6 sweep call sites would require modifying tested code. Parsing print() output needs zero changes to complete_pipeline*.py.

---

### 7. SweepPage Class

**Purpose**: Shows sweep progress, start/stop buttons, and a Live Monitoring
section with exactly two possible windows: Live Feed and Saved Image.

**What changed**: `LiveMonitoringWorker` (a class that opened its own,
second connection to the camera while `SweepWorker` already held it
exclusively — the SDK does not allow that, and it crashed) has been
deleted entirely. It was never actually instantiated anywhere in the app,
just dead scaffolding sitting next to a permanently-hidden 4-window grid
(Live Feed, Captured Frame, Difference, Averaged Result). The monitoring
section has been rebuilt from scratch around the two settings the app
actually defines: `show_live_feed_during_sweep` and
`show_saved_image_after_capture`.

#### `__init__()`
Creates UI sections:
1. Summary box (shows camera, mode, frequency range, exposure, etc.)
2. Progress box (progress bar, frequency label, Start/Stop buttons)
3. `_monitoring_container` — an empty placeholder `QWidget` that
   `_setup_monitoring_ui()` fills in every time `begin()` runs

#### `begin(camera_choice, mode_choice, params)`
Called when user continues from Preview.
- Stores all parameters
- Calculates total frequency steps
- Updates summary display
- Enables Start button
- Reads `show_live_feed_during_sweep` / `show_saved_image_after_capture`
  fresh from disk (not cached from `__init__`) and calls
  `_setup_monitoring_ui()`

#### `_setup_monitoring_ui()`
Clears whatever was in `_monitoring_container` and rebuilds it:
- Neither setting enabled: leaves the container completely empty. No
  `QGroupBox`, no reserved space.
- Exactly one enabled: a single window, centered (stretches added on
  both sides of the row).
- Both enabled: Live Feed and Saved Image side by side, no centering
  needed.

#### `_add_monitoring_window(row_layout, title, description)`
Builds one "card": a title label, a `QLabel` image display (starts with
placeholder text "Waiting for the first frame…"), and a short description
label underneath. Returns the display `QLabel` so callers can update its
pixmap later.

#### `is_running() -> bool`
Returns True if sweep worker is active.

#### `stop_and_wait()`
Stops the sweep worker and waits for it to finish.

#### `_start_sweep()`
Called when user clicks "Start Sweep": disables Start button, shows Stop
button, creates and starts `SweepWorker`, connects its signals.

#### `_on_progress(frequency_hz, current, total)`
Called when sweep emits progress signal.
- Updates progress bar and frequency label
- If Saved Image is enabled, schedules `_refresh_saved_image()` to run
  200ms later (`QTimer.singleShot`) — a short debounce so the pipeline's
  file save (which happens in the same iteration as the progress print
  this reacts to, but not in a guaranteed order relative to it) has time
  to finish first

#### `_refresh_saved_image()`
Looks at every `.png`/`.tif`/`.tiff` file in the sweep's output folder,
picks whichever has the newest modification time, and loads it into the
Saved Image display, scaled to fit while keeping its aspect ratio. Reads
the output folder directly rather than asking any pipeline module to
report its own filename back up — those modules were never designed to
report that, and this needs no changes to them at all.

**Why not a real camera connection for Saved Image?** Because it doesn't
need one: the pipeline already writes a result file per frequency step
regardless of whether anyone is watching. Reading that file back off disk
cannot conflict with the camera connection SweepWorker already holds,
which is exactly the problem that crashed the old `LiveMonitoringWorker`.

**Live Feed has no frame source yet.** Its window builds and shows/hides
correctly based on settings, but nothing ever calls
`self._live_feed_display.setPixmap(...)`, so it just displays "Waiting
for the first frame…" for the whole sweep. Getting real frames onto
screen during a sweep needs either a second camera connection (already
proven unsafe) or a `frame_callback` parameter threaded through the six
sweep functions in complete_pipeline.py / complete_pipeline_inclusive.py
/ complete_pipeline_allied_vision.py — additive and opt-in, so no
existing caller would change behavior, but real hardware is needed to
verify it, which this session did not have. Left for the next session
rather than guessed at.

#### `_on_finished(results)`
Called when sweep worker finishes: hides Stop button, re-enables Start
button, updates status label (results count or "no results"), emits
`sweep_finished` signal with results.

#### `_confirm_stop()`
Shows confirmation dialog before stopping sweep.

#### Signals
- `sweep_started`: Emitted when sweep begins (disables other pages)
- `sweep_finished`: Emitted with (results, output_dir) when complete

---

### 8. ResultsPage Class

**Purpose**: Shows grid of frequency sweep results with matplotlib graphs.

#### `show_results(results_dict, output_dir)`
Creates matplotlib figure from results and displays with navigation controls (Prev/Next buttons for browsing images).

---

### 9. MainWindow Class

**Purpose**: Top-level application window. Manages page navigation, settings persistence, and signal flow between pages.

#### `__init__()`
Creates:
1. Left navigation sidebar (Setup, Preview, Sweep, Results, Settings tabs)
2. QStackedWidget with all pages
3. Log console at bottom (140px fixed height)
4. Connections between pages and buttons

#### `_on_nav_changed(row)`
Called when user clicks navigation tab.
- Changes displayed page
- If navigating to Setup (row==0): reload settings from disk
- This ensures Setup always shows current saved values when user returns

**Settings persistence, corrected**: `SettingsPage` (see settings_dialog.md)
now has its own Save button and reloads from disk in its own `showEvent()`
whenever it becomes visible — `MainWindow` does not need to do anything
special for the Settings tab itself. Previously, `SettingsPage.save_settings()`
was never called from anywhere in this file at all, so changes made on the
Settings page never reached disk, and `reload_settings()` above — which
worked correctly on its own — had nothing new to actually pick up. That
was the real cause behind "I change a setting, go to Setup, and Setup
still shows the old value."

#### `_start_preview()`
Called when user clicks "Continue to Preview":
1. Reads current Setup UI values (camera, exposure, frequencies, etc.)
2. Saves all settings to disk
3. Enables Preview tab, navigates to it
4. Calls preview_page.start_preview() to begin camera grab

#### `_start_sweep_stage()`
Called when preview page emits `continued` signal (user clicks "Lock in settings & continue"):
1. Reads Setup UI again (in case user changed anything in Preview)
2. Saves settings to disk
3. Calls sweep_page.begin() to populate summary
4. Enables Sweep tab, navigates to it

#### `_on_sweep_started()`
Called when sweep page emits sweep_started signal.
- Disables all navigation tabs (user shouldn't switch pages during sweep)
- Updates status bar

#### `_on_sweep_finished(results, output_dir)`
Called when sweep worker finishes.
- Re-enables all navigation tabs
- If results exist: enables Results tab and shows results
- Updates status bar with result count

#### `_on_run_again()`
Called from Results page when user clicks "Run Again".
- Calls setup_page.reload_settings() to refresh UI
- Disables Preview tab (will be re-enabled when Continue is clicked)

---

## Data Flow

### User Workflow
```
START
  ↓
Setup Page (user chooses camera, mode, frequencies)
  ↓ clicks "Continue to Preview"
Preview Page (user sees live feed, aims camera)
  ↓ clicks "Lock in settings & continue"
Sweep Page (sweep runs, collects data)
  ↓ sweep completes
Results Page (shows frequency grid)
  ↓ clicks "Run Again"
← back to Setup
```

### Settings Flow
```
Setup UI → save_settings() → disk
           ↓
Preview starts → load_settings() → use grayscale_method
                  ↓
           Sweep starts → load_settings() → pass to pipeline
                          ↓
           User navigates to Setup → reload_settings() → update UI
```

### Camera Connection
```
Preview: connect_camera() → tuple (camera, format_info)
         ↓ (unpack defensively)
         camera, format_info = result
         ↓ (check if None)
         if camera is None: error
         ↓ grab frames
         disconnect_camera() [in finally]

Sweep: connect_camera() → tuple (camera, format_info)
       ↓ (same unpacking pattern)
       camera, format_info = result
       ↓ (run frequency loop)
       disconnect_camera() [in finally]
```

---

## Key Design Decisions

### Why defensive tuple unpacking?
Camera modules return `(camera, format_info)` or `(None, {})`. Must validate type and length before unpacking, then check if camera is None. This prevents AttributeError crashes.

### Why monitoring disabled?
LiveMonitoringWorker tried to connect to camera while SweepWorker held lock. Only one connection allowed. Need architectural redesign for dual-camera or display-only monitoring.

### Why reload_settings in _on_nav_changed?
Users expect Setup to always show current saved values when they return from Settings or Preview. Without reload, stale UI state persists.

### Why finally blocks for camera disconnect?
Ensures camera always released even if error occurs. Prevents camera lock on subsequent runs.

### Why settings persistence before Preview AND before Sweep?
User might change UI controls while on Preview page. Must save before handing off to next stage.

---

## Recent Changes (July 31, 2026)

1. **Settings reload on Setup navigation** (_on_nav_changed): SetupPage.reload_settings() now called when user navigates to Setup tab, ensuring UI shows current saved settings.

2. **LiveMonitoringWorker disabled** (_start_sweep): Monitoring worker creation removed to prevent camera lock conflicts with SweepWorker. No longer creates competing camera connections.

3. **Start Sweep button re-enable** (_on_finished): Added `start_button.setEnabled(True)` so users can run multiple sweeps in same session without restarting app.

4. **Shared light/dark theme** (MainWindow.__init__): The stylesheet and icon colors (previously a hardcoded dark-only `_STYLESHEET` string and hardcoded `"#e0e0e0"` icon colors in this file) now come from the shared `theme.py`, also used by monitor_gui.py and, through espi_app/styles.py, espi_app's own windows. MainWindow reads which theme to use from `settings_manager.load_settings()["theme"]` (defaulting to "dark", this file's original look), and its starting window size from `settings_manager.PREVIEW_SIZES[settings["preview_size"]]` instead of a fixed `resize(1150, 820)`. A new `refresh_theme(theme_name)` method lets espi_app switch this window's theme live while it is already open, re-applying the stylesheet and re-coloring the brand icon and all five nav icons (a QIcon does not follow stylesheet changes on its own, so it has to be re-created).

5. **"Use Last Settings as Default" actually gates the settings auto-save** (`_start_preview`, `_start_sweep_stage`): Previously, starting a Preview or a Sweep *always* silently overwrote the saved defaults with whatever SetupPage currently showed, unconditionally, with no way to turn it off. The duplicated save block in both methods is now one shared `_save_last_used_settings_if_enabled(camera_choice, params, mode_choice=None, extra=None)`, which does nothing unless `use_last_settings_as_default` is on, and also stamps `last_used_dashboard = "scan"` when it does save. When that flag is on, `SetupPage` (via a new `_apply_lock_state()`, called from both `__init__` and `reload_settings()`) and the separate embedded `SettingsPage` in `settings_dialog.py` (including its own Save button) disable their camera/mode/frequency/capture fields, since those values are now auto-managed from whatever a real run actually used, not typed in by hand.

6. **Signal Generator amplitude/offset controls, wired all the way to hardware**: Added a new "Signal Generator" group box (amplitude, DC offset) to `SetupPage`, persisted as `default_amplitude`/`default_offset` in the shared settings file, and included in `_apply_lock_state()`/`_save_last_used_settings_if_enabled()` alongside the existing capture defaults. These values now flow through `get_params()` -> `run_experiment.run_pipeline()`'s `base_params` -> whichever of the six `complete_pipeline*.py` sweep functions is chosen (all six gained real `amplitude`/`offset` parameters, defaulting to the same 1.0/0.0 every function already hardcoded, so no existing terminal caller changes behavior). While wiring this, added an explicit `turn_on_output()` call and a real success check to all six sweep functions (`complete_pipeline_inclusive.py`/`complete_pipeline_allied_vision.py` used to check a `sg_settings.get("channel output")` key). This was NOT fixing a bug in the code as it stood at the time — `signal_generator_control.configure_channel()` (which all six functions were still importing at that point) already turns the output on internally and already returns that key, so the old check was correct against it. The fix was preparation for the sdg_control migration that followed in the same session (see `complete_pipeline.md`'s "Recent Changes" and `MIGRATION_PLAN.md`): `sdg_control.waveform.configure_channel()` deliberately does neither, by design, so the explicit call and real check are what actually enable output correctly once each file's imports point at `sdg_control` instead.

