# monitor_gui.py

## Purpose

A PyQt6 dashboard for real-time live monitoring of camera frames and frame differences without running a full frequency sweep. Displays live camera feed, frame subtraction results, and optional intensity graphs. Lets the user choose between two frame-averaging strategies to reduce speckle noise.

## Main Components

**SetupPage** - Configuration interface for hardware capture settings: camera selection, exposure, gain, gain_factor, and frames to average.

**SettingsPage** - Processing strategy configuration where users choose frame-averaging method, intensity graph type, and difference amplification approach (none, or gain_factor) via radio buttons with hover tooltips.

**MonitorWorker** - Background thread that grabs frames from the camera, applies the chosen averaging strategy, and emits frame-ready signals to update the GUI. Also emits the raw, pre-amplification diff frame on its own signal so the Compare dialog can reuse it.

**LiveMonitorPage** - Displays the live camera feed and frame subtraction side by side, plus an optional intensity graph, plus a Compare Amplification Methods button and a Compare Grayscale Methods button, each opening a side by side comparison of every method in its own category.

**AmplificationComparisonDialog** - A popup window that runs every amplification method (none, gain_factor) on the same raw diff frame and displays them side by side with timing and contrast numbers, so the operator can pick a method by comparing outcomes instead of guessing and restarting the monitor. Normalize contrast, CLAHE, and gamma correction used to be options here too; they were removed along with camera_control*.py's amplify_difference() so the project has exactly one amplification story (gain_factor or none) everywhere.

**MainWindow** - Navigation shell with Setup and Live Monitor pages, plus a Settings page (accessed via button at bottom of nav rail).

## Detailed Descriptions

### SetupPage

Hardware capture configuration panel. Only shows settings that affect camera I/O: camera choice, exposure, gain, and frame averaging count.

**What it does:**

1. Display radio buttons for camera choice (Basler, USB, Allied Vision)
   - Only show camera index spinner for non-Basler cameras
   - Basler always uses index 0
   - Default selection comes from `settings_manager.load_settings()["default_camera_choice"]`

2. Exposure, gain, and gain_factor spin boxes
   - Exposure: 0.0001–10 seconds, default from `monitor_default_exposure` (0.06)
   - Gain: negative values allowed (in dB), default from `monitor_default_gain` (1.0). Hidden
     by default (label and spin box both, via `set_gain_visible()`) unless `show_gain` is
     True in the settings file; the "Show Gain (dB) control" checkbox that flips this lives
     on SettingsPage, not here, the same layout run_experiment_gui.py uses
   - gain_factor: 0.01–200 (scales difference amplification), default from `monitor_default_gain_factor` (10.0)
   - These are separate settings keys from run_experiment_gui.py's own `default_exposure` / `default_gain` / `default_gain_factor`, since the two dashboards have always used different historical defaults

3. Frames to average spinner (1–50)
   - How many frames (or frame pairs) to combine before display
   - Not settings-backed; always starts at 1 (no averaging)

4. Live summary label showing all current settings

**Locked by "Use Last Settings as Default":** if `settings["use_last_settings_as_default"]` is True (set from espi_app's Settings dialog, bridged into this shared settings file), the camera radios, index spinner, exposure, gain, and gain_factor are all disabled — those values are now auto-managed from whatever was actually last used to start a session, not typed in by hand (see `MainWindow._save_last_used_settings_if_enabled()` below). Frames-to-average is not a tracked default and always stays editable.

**Methods:**

- `camera_choice()`: return currently selected camera ("1", "2", "3")
- `camera_index()`: return camera index (0 for Basler, user-set for others)
- `settings()`: return dict with exposure_s, gain_db, gain_factor, n_averages
- `_update_summary()`: update the summary label whenever any input changes

### SettingsPage

Processing strategy configuration panel. Lets users choose grayscale conversion method, frame-averaging method, intensity graph type, and difference amplification via radio buttons and combo boxes with hover tooltips. Each of the four groups also has a Learn More button that opens a plain language explanation of every option in that group, for someone who is not familiar with these algorithms.

The whole page is wrapped in a QScrollArea, the same way SetupPage already is. A QStackedWidget must be big enough to show every page it holds, even ones not currently visible, so an unscrolled SettingsPage's own minimum height was forcing the whole window, and every other page, to be at least that tall too. That is what cropped the Settings button and the Live Monitor page's control row off the bottom of a real screen. See tests/test_sidebar_layout.py (rules I10 and I11).

**What it does:**

1. Grayscale conversion method selector (radio buttons)
   - "Standard Full-RGB": use standard luminosity-based grayscale (default for most cameras)
   - "Single-Channel Extraction": extract one color channel only
     - When selected, shows two additional combo boxes:
       - Target Color Channel: Red (default), Green, or Blue
       - Processing Algorithm: NumPy slicing (default), Pillow, or OpenCV channel splitting
     - When not selected, hides color and algorithm controls for cleaner interface

2. Frame averaging method selector (radio buttons)
   - "Average of differences": grab pairs, subtract, collect differences, average them
   - "Difference of averages": collect raw frames, average them, then subtract
   - Each radio has a tooltip explaining its approach

3. Intensity graph type selector (radio buttons)
   - Histogram: updates on every frame
   - Log histogram: LabVIEW style, updates on every frame
   - 3D surface: updates a few times per second
   - None: no graph (fastest)
   - Each radio has a tooltip describing performance and output

4. Difference amplification method (radio buttons, default Gain factor)
   - No amplification: show raw pixel differences
   - Gain factor: multiply by gain_factor from SetupPage (default selection)
   - Each radio has a tooltip explaining its effect
   - Normalize contrast, CLAHE, and gamma correction used to be options here, each with
     its own parameter controls (Clip Limit, Tile Grid Size, Gamma). They were removed,
     along with camera_control*.py's amplify_difference() (which "normalize" delegated
     to), so this project has exactly one amplification story everywhere: gain_factor
     or none.

5. Advanced group: "Show Gain (dB) control" checkbox, unchecked by default
   - SettingsPage is constructed with a reference to the live SetupPage instance
     (`SettingsPage(setup_page)`), stored as `self._setup_page`
   - Toggling this checkbox calls `self._setup_page.set_gain_visible(checked)` directly,
     so Setup's Gain (dB) label and spin box show or hide immediately, with no need to
     navigate away and back
   - Also writes `show_gain` straight through to `settings_manager.save_settings()`, so
     the choice is remembered next time, and shared with run_experiment_gui.py's own
     "Show Gain (dB) control" checkbox (same settings key)

**Methods:**

- `grayscale_method()`: return "standard" or "single_channel"
- `grayscale_color()`: return "R", "G", or "B" (only used when single_channel is selected)
- `grayscale_backend()`: return "numpy", "pillow", or "opencv_hsv" (only used when single_channel is selected)
- `averaging_method()`: return "averaged_differences" or "frame_averaging"
- `graph_type()`: return "histogram", "log_histogram", "3d", or None
- `diff_amplification()`: return "none" or "gain_factor"
- `_on_show_gain_toggled(checked)`: apply visibility to SetupPage live and persist show_gain
- `_update_grayscale_ui_visibility()`: show/hide color and backend controls based on grayscale method selection
- `_make_learn_more_button(title, html_content)`: build one Learn More button wired to open a LearnMoreDialog with the given title and content
- `_learn_more_row(button)`: right align a Learn More button in its own row above a group's radio buttons

**Learn More buttons:**

Each of the four groups (Grayscale Conversion Method, Frame Averaging Strategy, Intensity Graph, Difference Amplification) has its own Learn More button at the top of the group, above the radio buttons. Clicking one opens a `LearnMoreDialog` containing a plain language explanation of every option in that group, written for whoever is operating the monitor, not for someone reading the source code. This is separate from the short hover tooltips already on each radio button: tooltips are a one line reminder, the Learn More dialog is a full explanation of what the option does and the reasoning behind it.

`LearnMoreDialog` is a small `QDialog` wrapping a `QTextBrowser`, chosen over a plain `QLabel` because the explanations are long enough to need scrolling and because `QTextBrowser` can render simple HTML (headings, bold text, paragraphs) without needing a separate widget for every line.

### Grayscale Conversion Functions

Helper functions that convert BGR camera frames to grayscale using different methods.

**What they do:**

1. `_apply_grayscale_conversion(frame, method, color, backend)`: dispatcher function
   - Takes a BGR numpy array
   - Applies standard grayscale (method="standard") or single-channel (method="single_channel")
   - Returns a 2D grayscale uint8 array
   - Raises ValueError for invalid method or backend

2. `_grayscale_numpy(bgr_frame, color_code)`: NumPy slicing approach (fastest)
   - Extracts channel directly from BGR array using indexing (B=0, G=1, R=2)
   - Returns 2D array of selected channel intensities
   - Time: O(H×W), Space: O(H×W)

3. `_grayscale_pillow(bgr_frame, color_code)`: Pillow Image library approach
   - Converts BGR to RGB for Pillow compatibility
   - Uses PIL Image.getchannel() to extract the target channel
   - Returns 2D numpy array of selected channel
   - Time: O(H×W), Space: O(H×W)

4. `_grayscale_opencv_hsv(bgr_frame, color_code)`: OpenCV HSV hue-masking approach
   - Converts BGR to HSV color space
   - Creates a binary mask for the hue range of the target color:
     - Red: Hue 0-10 and 170-180 (wraps around in hue space)
     - Green: Hue 35-85
     - Blue: Hue 100-140
   - Extracts the V (Value/Brightness) channel from the HSV frame
   - Applies the mask to get the brightness of only target-color pixels, zeroing everything else
   - Returns 2D array of masked brightness values
   - Time: O(H×W), Space: O(H×W)

5. `_compare_grayscale_methods(frame, color)`: runs Standard Full-RGB and all three single-channel backends on the same raw frame
   - Loops over "standard", "numpy", "pillow", "opencv_hsv", timing each call and recording the result's average brightness
   - Returns a dict mapping method name to (result_image, elapsed_seconds, mean_brightness)
   - Backs the Compare Grayscale Methods button on LiveMonitorPage

6. `_compare_grayscale_difference_methods(frame1, frame2, color, cam_lib, amplification_method, gain_factor)`: compares grayscale methods on the difference between two consecutive frames
   - Takes two raw frames (frame1 and frame2) and applies each grayscale method to both, computes the absolute difference, then applies the selected amplification method
   - Loops over "standard", "numpy", "pillow", "opencv_hsv", timing each call and recording the result's average brightness
   - Returns a dict mapping method name to (difference_image, elapsed_seconds, mean_brightness)
   - Backs the Compare Grayscale Methods button on LiveMonitorPage (new functionality showing frame differences instead of single frame)
   - The amplification step is critical: raw differences have very low pixel values (0-50), so without amplification all methods look equally dark; applying the monitor's current amplification method makes the differences visible and fair to compare

**Why three backends?**

- NumPy is fastest (simple array indexing, no color space conversion)
- Pillow provides Image format compatibility for PIL-based pipelines
- OpenCV HSV is specialized for monochromatic light sources: it isolates pixels whose hue matches the laser color, returning only their true brightness. This produces a cleaner signal than raw channel extraction for single-color illumination (e.g., a red laser on a surface).

The NumPy and Pillow backends are equivalent (both return raw channel intensities), while OpenCV HSV is qualitatively different: it masks by hue before extracting brightness. Choose HSV when you have a colored laser and want noise-free intensity; choose NumPy or Pillow for general-purpose frames.

### Difference Amplification Functions

Helper functions that make a subtracted diff frame easier to see. Every one of these is only ever called on the post-averaging diff array (raw_diff or raw_change inside MonitorWorker), never on the live feed frame, since the point is to make the fringe pattern visible without changing what the operator sees in the live feed.

Normalize contrast, CLAHE, and gamma correction used to live here too (`_apply_clahe`, `_apply_gamma_correction`, plus the extra parameters they needed on every function below). They were removed, along with `camera_control*.py`'s `amplify_difference()` (which "normalize" delegated to). This project now has exactly one amplification story everywhere: gain_factor or none.

**What they do:**

1. `_apply_diff_amplification(raw_diff, method, gain_factor)`: single dispatcher for every amplification method
   - "none" returns the raw diff unchanged
   - "gain_factor" calls cv2.convertScaleAbs with the configured gain factor
   - Both MonitorWorker capture strategies call this same function instead of repeating the if/elif chain, so adding a new amplification method only means adding one branch here

2. `_compare_amplification_methods(raw_diff, gain_factor)`: runs every method on the same raw diff frame
   - Loops over every amplification method, times each call, and records the result's standard deviation as a rough contrast number
   - Returns a dict mapping method name to (result_image, elapsed_seconds, contrast_std)
   - Backs the Compare Amplification Methods button on LiveMonitorPage

### MonitorWorker

Background thread that runs the actual live-monitoring loop with frame grabbing and averaging.

**What it does:**

1. Load and connect to the appropriate camera control module
   - Pass the grayscale_method ("standard" or "single_channel") to connect_camera()
   - This sets the camera's pixel format: Mono8 for standard (fast, small), BayerRG8 for single-channel (preserves color data)
2. Set exposure and gain based on settings
3. Initialize grayscale conversion settings (method, color, backend)
4. Branch to the appropriate averaging strategy:
   - `_run_frame_averaging()` for classic method
   - `_run_averaged_differences()` for new method
5. In both strategies, convert each grabbed frame using the selected grayscale method
6. Emit frame_ready signal with (averaged_frame, difference_frame) for each completed average

**Grayscale Integration:**

The worker stores the grayscale settings from SettingsPage:
- `_grayscale_method`: "standard" or "single_channel"
- `_grayscale_color`: "R", "G", or "B"
- `_grayscale_backend`: "numpy", "pillow", or "opencv_hsv"

**Amplification Integration:**

The worker also stores the amplification setting from SettingsPage:
- `_diff_amplification`: "none" or "gain_factor" (default "gain_factor")

Every raw diff frame is emitted on `raw_diff_ready` before amplification is applied, then passed through `_apply_diff_amplification()` to get the frame that actually gets shown. The Compare dialog listens to `raw_diff_ready` so it always compares methods against the same underlying data the live diff view is currently based on.

When grabbing a frame, the worker calls its own `_grab_frame(cam_lib, camera)` helper, not `cam_lib.grab_single_frame(camera)` directly, then:
1. Gets the raw frame back exactly as the camera driver produced it (a real (H, W, 3) BGR array for a color camera, or a plain (H, W) array for a mono camera)
2. Immediately applies `_apply_grayscale_conversion()` to get a 2D grayscale frame, using whichever method, color, and backend the operator picked
3. Proceeds with normal frame averaging logic on the grayscale output

**Why grab_single_frame_color_with_retry() and not grab_single_frame():** grab_single_frame() reduces a color frame to greyscale internally, before this worker ever sees it. That is fine for every other caller in this project, but it used to break single-channel Red/Green/Blue extraction here specifically: by the time `_apply_grayscale_conversion()` ran, the frame was already flattened to 2D, so it hit the "already grayscale" early return and the color choice never had any effect at all. grab_single_frame_color() is a sibling function (added to camera_control_inclusive.py, camera_control_allied_vision.py, and camera_control.py) that returns the real color data untouched, so this worker's own grayscale conversion step is the only place color gets reduced.

**Why the _with_retry variant specifically:** the worker originally called the plain, non-retrying grab_single_frame_color(), and a real USB webcam then failed on the very first grab with "Failed to grab frame, check camera connection", even though the camera had opened successfully moments earlier. Some USB webcams need a brief moment to warm up right after connect_camera() opens them, and a single unretried read() attempt can fail even on a camera that works fine immediately after. grab_single_frame_with_retry() already existed in this project for exactly this reason, used by other callers, but MonitorWorker was never using it, or its color-preserving counterpart. grab_single_frame_color_with_retry() closes that gap: it mirrors grab_single_frame_with_retry()'s retry loop while preserving color, the same relationship grab_single_frame_color() has to grab_single_frame().

**`_grab_frame(cam_lib, camera)` helper and the elapsed-time retry budget:** even after the retry variant above was wired in, the real USB webcam kept failing once the monitor actually started, because a fixed attempt count could not bridge how long the camera actually took to warm up. A diagnostic that mirrored the real startup order (connect, then set_exposure_manual(), then set_gain_manual(), then start reading) measured about 3.4 seconds before the first successful read(), and caught a second, shorter drop happening again mid-session, after the initial warm-up had already succeeded. grab_single_frame_color_with_retry() gained a `max_total_wait_s` parameter (see camera_control.md for the full explanation) that keeps retrying based on real elapsed time instead of a fixed count. `_grab_frame()` is a small private helper that calls it with this worker's `_frame_grab_retry_delay_s` and `_frame_grab_max_total_wait_s`, both read from the settings dict in `__init__()` (keys `frame_grab_retry_delay_s`, `frame_grab_max_total_wait_s`), falling back to module-level constants `DEFAULT_FRAME_GRAB_RETRY_DELAY_S` (0.3s) and `DEFAULT_FRAME_GRAB_MAX_TOTAL_WAIT_S` (6.0s, about 1.75x the measured 3.4s stall) if the settings dict does not have them. Both loops (`_run_frame_averaging` and `_run_averaged_differences`) call `_grab_frame()` instead of `cam_lib.grab_single_frame_color_with_retry(camera)` directly, so this budget applies to every frame grab in a live session, not only the very first one after connecting.

This ensures all downstream processing (averaging, subtraction, display) works with the chosen grayscale representation, and that the chosen representation is actually reachable in the first place.

**Pixel Format Switching (Dynamic Format Selection):**

The monitor worker passes `grayscale_method` to `connect_camera()` in camera_control.py, camera_control_inclusive.py, and camera_control_allied_vision.py. This controls which pixel format the camera uses:

- "standard" method → Mono8 format (single channel, grayscale)
  - Faster frame grabbing (1/3 the bandwidth)
  - Smaller file storage
  - Ideal when user wants standard full-RGB luminosity conversion

- "single_channel" method → BayerRG8 format (three channels, color)
  - Preserves raw RGB data from camera
  - Enables single-channel extraction (Red/Green/Blue) to work correctly
  - Critical for monochromatic light sources (e.g., red laser): extracts only the red channel data, avoiding noise from green and blue sensors

Why this matters: If the camera is left in Mono8 (single channel), extracting "Red" returns the same data as "Green" and "Blue"—they're all identical single values. By switching to BayerRG8 when single-channel extraction is selected, the camera delivers all three channels, and single-channel extraction produces different intensity values for each color, enabling proper laser-based vibration measurement.

For Allied Vision cameras, this also resets the "stale format memory" bug that occurred in prior development: cameras remember their pixel format in onboard memory across power cycles. By always explicitly setting the format in connect_camera() and verifying it was applied (with retry logic in set_pixel_format()), we prevent mysterious failures where previous session's format state would interfere with the current session.

**Strategies:**

#### Frame Averaging (Classic)

1. Grab a raw frame from camera
2. Add it to frame_buffer
3. When frame_buffer reaches n_averages frames:
   - Compute np.mean() across all frames (element-wise pixel average)
   - Clear frame_buffer
   - If there's a previous averaged frame, compute difference
   - Emit raw_diff_ready with the raw difference (pre-amplification)
   - Apply amplification (none or gain_factor) via _apply_diff_amplification()
   - Emit frame_ready with both the averaged frame and the amplified difference

#### Averaged Differences (New)

1. Grab frame1 from camera
2. Grab frame2 from camera
3. Subtract: raw_diff = frame2 - frame1 (absolute value)
4. Add raw_diff to diff_buffer
5. When diff_buffer reaches n_averages differences:
   - Compute np.mean() across all differences (element-wise average of differences)
   - Clear diff_buffer
   - If there's a previous averaged difference, compute change
   - Emit raw_diff_ready with the raw change (pre-amplification)
   - Apply amplification (none or gain_factor) via _apply_diff_amplification()
   - Emit frame_ready with both the averaged difference and the amplified change

**Why two strategies?**

- Frame averaging spreads speckle noise across both frames, leaving it in the difference
- Averaged differences collects the noise in the frame pairs, then averages it away—resulting in cleaner difference images

**Signals:**

- `frame_ready(np.ndarray, object)`: emitted when averaging is complete; payload is (averaged_frame, diff_or_None)
- `raw_diff_ready(np.ndarray)`: emitted whenever a new pre-amplification diff frame is computed, so the Compare dialog can run every method against the same underlying data
- `error(str)`: emitted if camera connection fails or frames stop arriving
- `finished_cleanly()`: emitted when thread exits (error or stop requested)

**Lifecycle:**

- `stop()` sets a cooperative flag; the loop checks it and exits cleanly between averages
- `run()` is called by Qt when `start()` is invoked
- `finished_cleanly()` is guaranteed exactly once, even on error

### LiveMonitorPage

The display panel showing live results.

**What it does:**

1. Create two side-by-side QLabel widgets (live feed and difference frame)
2. Start the MonitorWorker thread
3. Connect worker signals to slots that update the labels, including raw_diff_ready
4. Show/hide graph canvas based on graph_type setting
5. Update graph on every frame_ready signal
6. Provide Stop button to safely shut down the worker
7. Provide a Compare Amplification Methods button, disabled until the first raw diff arrives
8. Provide a Compare Grayscale Methods button, disabled until the first raw frame arrives

**Graph Support:**

- If graph_type is None: hide canvas (fastest)
- If histogram: show live histogram updating every frame
- If log_histogram: show log-scale histogram (LabVIEW style)
- If 3d: show 3D surface plot (updates every few frames)

**Compare Amplification Methods button:**

1. Disabled at startup and immediately after Stop Monitor, since there is no diff frame yet
2. `_on_raw_diff(raw_diff)` stores the latest raw diff and enables the button the first time one arrives
3. Clicking the button opens an `AmplificationComparisonDialog` built from the stored raw diff and the current gain_factor
4. This is a manual, on-demand comparison rather than an always-on panel, so it costs nothing while the operator is not using it

### AmplificationComparisonDialog

A modal popup that answers "which amplification method should I actually use" without restarting the monitor.

**What it does:**

1. Take the same raw diff frame and gain_factor the live monitor is currently configured with
2. Call `_compare_amplification_methods()` to run both methods against that one frame
3. Lay out one column per method: the resulting image, plus a caption with elapsed time in milliseconds and the result's standard deviation as a quick contrast number
4. A Close button dismisses the dialog; nothing here mutates the running monitor's settings

**Why a modal dialog instead of a permanently visible panel:**

Running every image-processing pass on every single frame just in case the operator wants to compare would waste CPU on every frame the vast majority of the time nobody is looking. A button that runs the comparison once, on demand, keeps the live monitor loop exactly as fast as before for everyone who never clicks it.

**Compare Grayscale Methods button:**

1. Disabled at startup and immediately after Stop Monitor, since there are not yet two raw frames to compare
2. `_on_raw_frame(raw_frame)` keeps a rolling list of the last 2 pre-grayscale-conversion frames and enables the button once 2 frames are available
3. Clicking the button opens a `GrayscaleDifferenceComparisonDialog` built from the stored frame pair and whichever color channel (Red, Green, or Blue) is currently selected in Settings
4. The dialog applies the same amplification method (gain_factor or none) that the main monitor is using, so all four grayscale methods can be fairly compared
5. Same on-demand, no cost when unused design as the Compare Amplification Methods button

### GrayscaleComparisonDialog

A modal popup that answers "does switching to single-channel extraction actually make a visible difference" without restarting the monitor and re-checking Settings four times. Added after a real bug: color data was being destroyed before single-channel extraction ever ran (see camera_control.md and the "single-channel extraction end to end" note in this file), so this dialog also doubles as visible proof the fix works, since Standard Full-RGB and the three single-channel backends will look genuinely different on a colored scene now.

**What it does:**

1. Take the same raw frame and color channel choice the live monitor is currently configured with
2. Call `_compare_grayscale_methods()` to run Standard Full-RGB and all three single-channel backends against that one frame
3. Lay out one column per method: the resulting image, plus a caption with elapsed time in milliseconds and the result's average brightness
4. A Close button dismisses the dialog; nothing here mutates the running monitor's settings

### GrayscaleDifferenceComparisonDialog

A modal popup that answers "which grayscale method produces the clearest difference visualization" by comparing how each method handles the difference between two consecutive frames. Shows Standard Full-RGB and the three single-channel backends side by side, all with the same amplification applied (matching the monitor's current amplification method and settings).

**What it does:**

1. Take the last two raw frames captured and whichever color channel is currently selected in Settings
2. For each grayscale method (Standard, NumPy, Pillow, OpenCV HSV):
   - Convert both frames using that method
   - Compute the absolute pixel-wise difference between them
   - Apply the same amplification (gain_factor or none) that the monitor is currently using
3. Lay out one column per method: the resulting difference image, plus timing and average intensity metrics
4. A Close button dismisses the dialog; nothing here mutates the running monitor's settings
5. The amplification visibility is critical: raw differences are nearly black (pixel values 0-50), so without amplification all four methods look equally dim and useless; applying the same amplification the monitor uses makes the differences visible and comparable

### MainWindow

Navigation shell tying everything together.

**What it does:**

0. Read the current theme ("light" or "dark") from `settings_manager.load_settings()["theme"]`, defaulting to "dark" if never saved, and apply the matching stylesheet from `theme.py` (see `_stylesheet_for()`, which adds this file's own nav-item-height rule on top of the shared one) — this is also where the starting window size comes from `PREVIEW_SIZES[settings["preview_size"]]`, clamped to the actual screen
1. Show a small brand header at the top of the sidebar (a camera icon and the "ESPI Monitor" title), so the panel reads as an app shell rather than two plain text links
2. Create a left navigation rail with Setup and Live Monitor items, each with its own icon (a tune icon for Setup, a video camera icon for Live Monitor), colored for the current theme
3. Add a Settings button at the bottom (separate from nav rail)
4. Setup page always enabled at startup
5. Live Monitor disabled until monitor starts
6. When a nav item is clicked:
   - Navigate to that page (Setup or Live Monitor)
   - Uses itemClicked signal so navigation always works, even after returning from Settings
7. When Settings button is clicked:
   - Show Settings page (nav selection unchanged, since Settings is not a nav item)
8. When Setup's "Start Monitor" button clicked:
   - Call `_save_last_used_settings_if_enabled()` with the camera choice and settings about to be used
   - Enable Live Monitor in nav
   - Disable Setup
   - Switch to Live Monitor page
   - Start the worker thread
9. When monitor stops:
   - Re-enable Setup
   - Disable Live Monitor
   - Return to Setup page

**Navigation Design (Critical for Reliability):**

- Uses `itemClicked` signal (action-based) instead of `currentRowChanged` (state-based)
- This ensures clicking a nav item **always navigates**, even when Settings page is shown
- Settings page is separate from nav rail, so nav state remains stable
- Why this matters: if we relied on currentRowChanged, clicking Setup when currentRow is already 0 (Setup) would fail because the row didn't "change"
- Navigation gating prevents invalid states (can't reach Live Monitor until monitor starts)

**Safety Features:**

- Responsive to worker signals (frame_ready, error, finished_cleanly)
- Safe close: prompts user and waits for worker if running

**refresh_theme(theme_name):**

Called by espi_app when the user changes theme in Settings while this window is already open (espi_app keeps a reference to it and calls this directly — it is not a signal). Re-applies the stylesheet for the new theme and re-creates the brand icon, both nav item icons, and the Settings button's icon at the new color, since a QIcon is a static bitmap that does not follow stylesheet changes on its own.

**_save_last_used_settings_if_enabled(camera_choice, settings):**

If `settings_manager.load_settings()["use_last_settings_as_default"]` is False, does nothing — whatever defaults were last explicitly configured stay untouched. If True, writes the camera choice and this session's exposure/gain/gain_factor into the shared settings file as `default_camera_choice` / `monitor_default_exposure` / `monitor_default_gain` / `monitor_default_gain_factor`, plus `last_used_dashboard = "monitor"`, and saves. This is the file's first-ever settings write — previously it only ever read.

**Sidebar resize behavior (no resizeEvent override):**

MainWindow has no resizeEvent() override. The nav list's own Expanding vertical size policy (set once in SettingsPage's sibling, the nav list built in MainWindow.__init__) is what makes it grow taller as the window grows taller, recalculated fresh by Qt's layout engine on every resize.

A previous version did override resizeEvent() to force the nav list's minimum and maximum height every time the window resized, computed from the sidebar's own current height. That computation was a ratchet: setMinimumHeight() does not just describe a widget's size, it raises the floor Qt will ever let that widget (and the window containing it) shrink below, and each resize fed the sidebar's already-grown height back into the next minimum, so it only ever grew, never shrank. A real maximize/fullscreen transition fires several resize events while the OS animates it, each one raising the floor further before the window finished growing, which is what caused the window to visibly squeeze itself down as it was maximized. See tests/test_sidebar_layout.py (rules I8 and I9) and the changelog entry titled "Fix the sidebar squeezing itself to nothing at full screen size" for the full story.

## Key Concepts

### Frame Averaging vs. Averaged Differences

Both reduce speckle noise, but differently:

- **Speckle noise** is random granular variation in the raw frame due to laser interference
- **Frame averaging**: reduces noise equally in both frames → noise remains in the difference
- **Averaged differences**: averages the differences themselves → noise averaged out of the result

For ESPI, where you care about the difference patterns, averaged differences typically produces cleaner fringe visibility.

### Cooperative Stopping

The worker checks `self._stop` once per average cycle, not per frame. This is safe because:

1. An average cycle involves grabbing multiple frames (or frame pairs)
2. Between averages, no hardware operation is in progress
3. Stopping between averages guarantees clean disconnect

This is safer than `terminate()`, which could stop mid-frame-grab and leave hardware open.

### Averaging in NumPy

`np.mean(array, axis=0)` on a 3D array of shape (N, height, width) produces a 2D array where each pixel is the mean across all N layers. Then `.astype(np.uint8)` clips to 0–255 range.

### Settings Dict Flow

SetupPage.settings() → MonitorWorker.__init__() → stored in _settings → read throughout run() to control behavior.

### Amplification Only Touches the Diff, Never the Live Feed

`_apply_diff_amplification()` is only ever called with `raw_diff` or `raw_change`, the arrays computed after averaging and subtraction. The live feed frame (`averaged` in frame averaging, `frame2` in averaged differences) is emitted through `frame_ready` completely untouched by whichever amplification method is selected. This holds for gain_factor the same way it held for the methods since removed (normalize, CLAHE, gamma), since both remaining methods are dispatched from the same single call site in each strategy method.

### One Dispatcher Instead of a Repeated if/elif

Both `_run_frame_averaging` and `_run_averaged_differences` call the same `_apply_diff_amplification()` instead of each keeping their own copy of the `if method == "gain_factor": ... else: ...` block, so a bug fix or a new method only needs to change in one place.

## Why This Design

1. **Two averaging methods** let users experiment with which produces better results for their setup.
2. **Separate strategy methods** (_run_frame_averaging, _run_averaged_differences) make each approach crystal clear and easy to modify.
3. **Cooperative stopping** is safer than forceful termination for hardware-dependent loops.
4. **Settings dict** keeps configuration flowing one direction (Setup → Worker) without tight coupling.
5. **Signal-based updates** keep camera I/O off the main Qt thread while safely updating the GUI.
6. **Navigation gating** prevents invalid states (e.g., viewing Live Monitor when no monitor is running).
7. **Only gain_factor or none**: normalize contrast (which delegated to each camera_control*.py module's own amplify_difference()), CLAHE, and gamma correction were removed to keep exactly one amplification story across the whole project.
8. **Compare Amplification Methods is a button, not an always-on panel**, so comparing costs CPU only when the operator actually asks for it, not on every frame for everyone.

## Related Files

- **camera_control*.py** — Actual camera connection, frame grabbing, and subtraction
- **live_graphs.py** — Graph objects that update() on each frame
- **monitor.py** — Terminal version of live monitoring (defines CAMERA_NAMES, GRAPH_TYPES constants)
- **run_experiment_gui.py** — Sister dashboard for frequency sweeps (shares theme.py, layout patterns)
- [theme.md](theme.md) — the shared stylesheet and icon colors this file applies
- [settings_manager.md](settings_manager.md) — where the theme, preview size, and monitor_default_* capture defaults come from

## Usage Example

```python
from monitor_gui import MainWindow
from PyQt6.QtWidgets import QApplication

app = QApplication([])
window = MainWindow()
window.show()
app.exec()
```

User flow:
1. Launch app → Setup page appears
2. Choose camera (default: USB camera)
3. Set exposure, gain, graph type, averaging method
4. Click "Start Monitor" → Live Monitor page with camera feed appears
5. Watch live frames and differences; graph updates in real-time
6. Click "Stop Monitor" → return to Setup
7. Change settings and start again, or close the app
