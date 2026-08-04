# Pseudocode Documentation Index

This index lists all pseudocode files and helps you find what you need.

## Quick Navigation

- **New to the project?** Start with [README.md](README.md)
- **Want to understand how the app starts?** Read [espi_app/main.md](espi_app/main.md)
- **Want to understand the frequency sweep GUI?** Read [espi_full_algorithm/run_experiment_gui.md](espi_full_algorithm/run_experiment_gui.md)
- **Want to understand camera control?** Read [espi_full_algorithm/camera_control.md](espi_full_algorithm/camera_control.md)
- **Want to understand experiments?** Read [espi_full_algorithm/complete_pipeline.md](espi_full_algorithm/complete_pipeline.md)
- **Want to understand the signal generator?** Read [espi_full_algorithm/sdg_control.md](espi_full_algorithm/sdg_control.md)

## All Pseudocode Files by Category

### ESPI App (PyQt6 GUI Application Framework)

The modern GUI application that users interact with, the unified landing page. Entry point is `espi_app.main`.

| File | Purpose |
|------|---------|
| [espi_app/main.md](espi_app/main.md) | Application entry point that initializes PyQt6, loads settings, shows landing page |
| [espi_app/settings.md](espi_app/settings.md) | Persistent settings manager (loads/saves to ~/.espi_app/settings.json) |
| [espi_app/main_window.md](espi_app/main_window.md) | Landing page with mode selection (Monitor vs. Scan) |
| [espi_app/mode_card.md](espi_app/mode_card.md) | The clickable mode selection card widget behind the two landing page buttons |
| [espi_app/logo.md](espi_app/logo.md) | The ESPI logo widget, rendered from logo.svg |
| [espi_app/background_decoration.md](espi_app/background_decoration.md) | Subtle corner dot decoration painted behind the landing page |
| [espi_app/settings_dialog.md](espi_app/settings_dialog.md) | Settings dialog with Hardware and UI tabs |
| [espi_app/styles.md](espi_app/styles.md) | Light and dark themes, shared with ESPI Full Algorithm/theme.py |

### ESPI Full Algorithm (Core Measurement System)

The actual ESPI measurement system. Handles camera capture, signal generation, image processing, and analysis. One file per camera type for the modules that need it (Basler, any USB/webcam ["inclusive"], Allied Vision).

| File | Purpose |
|------|---------|
| [espi_full_algorithm/run_experiment_gui.md](espi_full_algorithm/run_experiment_gui.md) | PyQt6 dashboard for frequency sweep experiments (Setup, Preview, Sweep, Results pages) |
| [espi_full_algorithm/run_experiment.md](espi_full_algorithm/run_experiment.md) | The same frequency sweep experiment, as an interactive terminal script |
| [espi_full_algorithm/monitor_gui.md](espi_full_algorithm/monitor_gui.md) | PyQt6 live monitor dashboard using averaged differences |
| [espi_full_algorithm/monitor.md](espi_full_algorithm/monitor.md) | The same live camera monitor, as an interactive terminal script |
| [espi_full_algorithm/settings_dialog.md](espi_full_algorithm/settings_dialog.md) | Settings page UI for run_experiment_gui.py (grayscale, camera, capture defaults, live monitoring toggles) |
| [espi_full_algorithm/settings_manager.md](espi_full_algorithm/settings_manager.md) | JSON load/save/validate for run_experiment_gui.py's and monitor_gui.py's persisted settings |
| [espi_full_algorithm/theme.md](espi_full_algorithm/theme.md) | The shared light/dark stylesheet builder used by espi_app, monitor_gui.py, and run_experiment_gui.py |
| [espi_full_algorithm/camera_control.md](espi_full_algorithm/camera_control.md) | Camera interface for Basler cameras (pypylon) |
| [espi_full_algorithm/camera_control_inclusive.md](espi_full_algorithm/camera_control_inclusive.md) | Camera interface for any USB camera or webcam (OpenCV) |
| [espi_full_algorithm/camera_control_allied_vision.md](espi_full_algorithm/camera_control_allied_vision.md) | Camera interface for Allied Vision cameras (vmbpy) |
| [espi_full_algorithm/capture_and_display.md](espi_full_algorithm/capture_and_display.md) | Live camera preview with frame subtraction, Basler |
| [espi_full_algorithm/capture_and_display_cv2.md](espi_full_algorithm/capture_and_display_cv2.md) | Live camera preview with frame subtraction, any USB camera |
| [espi_full_algorithm/capture_and_display_allied.md](espi_full_algorithm/capture_and_display_allied.md) | Live camera preview with frame subtraction, Allied Vision |
| [espi_full_algorithm/complete_pipeline.md](espi_full_algorithm/complete_pipeline.md) | Full frequency sweep pipeline, Basler |
| [espi_full_algorithm/complete_pipeline_inclusive.md](espi_full_algorithm/complete_pipeline_inclusive.md) | Full frequency sweep pipeline, any USB camera |
| [espi_full_algorithm/complete_pipeline_allied_vision.md](espi_full_algorithm/complete_pipeline_allied_vision.md) | Full frequency sweep pipeline, Allied Vision |
| [espi_full_algorithm/live_graphs.md](espi_full_algorithm/live_graphs.md) | Real-time graph visualization (histogram, log histogram, 3D surface) |
| [espi_full_algorithm/sdg_control.md](espi_full_algorithm/sdg_control.md) | Signal generator control package (`sdg_control/`): connecting, waveform, frequency, safety clamps |
| [espi_full_algorithm/basic_usage.md](espi_full_algorithm/basic_usage.md) | Walkthrough of `examples/basic_usage.py`, a minimal signal generator script |

### Camera Module (Low-Level Camera Demo, Not Currently Used)

| File | Purpose |
|------|---------|
| [camera/connection.md](camera/connection.md) | Low-level camera connection and disconnection, from `Learning/camera/connection.py`. This is a standalone learning exercise, superseded by `ESPI Full Algorithm/camera_control*.py`, and is not imported by anything the two GUIs actually run. |

## Reading Order by Use Case

### Scenario 1: I want to understand the whole project

1. Read [README.md](README.md) (high-level overview)
2. Read [espi_app/main.md](espi_app/main.md) (how the app starts)
3. Read [espi_app/settings.md](espi_app/settings.md) (how configuration works)
4. Read [espi_app/main_window.md](espi_app/main_window.md) (what users see)
5. Read [espi_full_algorithm/camera_control.md](espi_full_algorithm/camera_control.md) (core camera functions)
6. Read [espi_full_algorithm/sdg_control.md](espi_full_algorithm/sdg_control.md) (experiment control)
7. Read [espi_full_algorithm/complete_pipeline.md](espi_full_algorithm/complete_pipeline.md) (full measurement workflow)

### Scenario 2: I want to add a camera feature

1. Read [espi_full_algorithm/camera_control.md](espi_full_algorithm/camera_control.md) (understand the Basler API; the OpenCV and Allied Vision variants follow the same function names)
2. Identify which section to add to
3. Implement the function in all three `camera_control*.py` files if the feature applies to every camera type
4. Test thoroughly

### Scenario 3: I want to fix the GUI

1. Read [espi_app/main.md](espi_app/main.md) (entry point)
2. Read [espi_app/main_window.md](espi_app/main_window.md) (landing page)
3. Read [espi_app/mode_card.md](espi_app/mode_card.md) and [espi_app/logo.md](espi_app/logo.md) if it's a landing-page visual issue
4. Read [espi_app/settings_dialog.md](espi_app/settings_dialog.md) (if settings dialog)
5. Read [espi_app/styles.md](espi_app/styles.md) (if styling issue)
6. Find the corresponding code file
7. Make changes
8. Test in the GUI

### Scenario 4: I want to run an experiment

1. Read [espi_full_algorithm/complete_pipeline.md](espi_full_algorithm/complete_pipeline.md) (workflow overview)
2. Read [espi_full_algorithm/camera_control.md](espi_full_algorithm/camera_control.md) (camera functions)
3. Read [espi_full_algorithm/sdg_control.md](espi_full_algorithm/sdg_control.md) (frequency sweep control)
4. Configure settings via the GUI
5. Run the experiment

### Scenario 5: I want to debug camera issues

1. Read [espi_full_algorithm/camera_control.md](espi_full_algorithm/camera_control.md) (or the variant for your camera type)
2. Read error messages carefully (they usually tell you what to check)
3. Check physical connections (cable, power)
4. Try the relevant `camera_control*.py` directly to isolate issues

## Pseudocode File Format

Each pseudocode file uses this structure:

1. **Purpose** - What the module does in one sentence
2. **Overview/Classes** - Major functions and classes
3. **Detailed Function Descriptions** - What each function does step-by-step
4. **Key Concepts** - Important ideas to understand
5. **Why This Design** - Rationale behind the structure
6. **Related Files** - How this module connects to others

All descriptions use:
- Plain English (no em dashes)
- Simple language anyone can understand
- Step-by-step descriptions of what code does
- Examples of typical usage

## Common Terminology

### Terms You'll See Frequently

| Term | Meaning |
|------|---------|
| ESPI | Electronic Speckle Pattern Interferometry, the measurement technique |
| Frame | One image captured from the camera |
| Grab/Grabbing | Capturing frames from the camera |
| ROI | Region of Interest, a cropped portion of the sensor |
| Gain | Signal amplification in decibels |
| Exposure | How long the sensor captures light |
| Mono8 | 8-bit grayscale pixel format (0-255) |
| Mono12 | 12-bit grayscale pixel format (0-4095) |
| SCPI | Standard Commands for Programmable Instruments (lab equipment language) |
| VISA | Virtual Instrument Software Architecture (communication standard) |
| Node | A region of minimal vibration in a vibrating surface |
| Speckle | Random granular pattern created by laser light interference |

## How Files Relate to Each Other

```
espi_app/
  main.py (entry point)
    -> settings.py (loads config)
    -> main_window.py (landing page)
       -> mode_card.py (the two big buttons)
       -> logo.py (the ESPI logo widget)
       -> settings_dialog.py (change settings)
       -> styles.py (apply theme, shared with ESPI Full Algorithm/theme.py)
       -> monitor_gui.py / run_experiment_gui.py (opened on demand, live in ESPI Full Algorithm/)

ESPI Full Algorithm/
  camera_control.py / camera_control_inclusive.py / camera_control_allied_vision.py
    (one per camera type, same function names in each)

  capture_and_display*.py (live preview only)
    <- matching camera_control*.py

  complete_pipeline*.py (full experiment)
    <- matching camera_control*.py
    <- sdg_control/ (signal generator)
    <- live_graphs.py

  run_experiment.py / run_experiment_gui.py
    <- complete_pipeline*.py (picks the right one for the chosen camera)

  monitor.py / monitor_gui.py
    <- capture_and_display*.py / camera_control*.py
    <- live_graphs.py

  sdg_control/
    connections.py, status.py, output.py, waveform.py, limits.py, constants.py, errors.py
```

## Updating This Index

When a new pseudocode file is added:
1. Add entry to the table above
2. Update the "All Pseudocode Files" section
3. If it's a new category, add a new table
4. Consider if reading order changes
5. Update the dependency graph if applicable

## Questions Not Answered by Pseudocode?

This pseudocode is intentionally high-level. For implementation details:
1. Read the actual Python source files
2. Look for comments in the code
3. Check git history to understand why decisions were made
4. Ask questions in discussions

The pseudocode is meant to help you understand what code does and why. The actual code shows how it's done.
