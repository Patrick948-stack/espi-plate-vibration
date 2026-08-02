# ESPI Camera Control Project: Complete Pseudocode Documentation

This folder contains plain-English pseudocode for every major file in the ESPI Camera Control project. The structure mirrors the actual codebase so you can easily find what you need.

## Project Overview

This is a Python application to control an ESPI (Electronic Speckle Pattern Interferometry) camera system for measuring vibrations in musical instrument plates. The system consists of:

1. A modern PyQt6 GUI application (espi_app) that serves as the entry point
2. Core ESPI algorithm modules (ESPI Full Algorithm folder) that handle camera capture, signal generation, and data analysis
3. Lower-level camera control modules
4. Signal generator control for frequency sweeps
5. Image processing utilities

## Folder Structure

This mirrors the actual project layout: `pseudocode/espi_app/` documents
`espi_app/`, `pseudocode/espi_full_algorithm/` documents
`ESPI Full Algorithm/` (including its `sdg_control/` package, in one
combined file since the package is small), and `pseudocode/camera/`
documents the one file still worth documenting under `Learning/camera/`.

```
pseudocode/
├── README.md (this file)
├── INDEX.md (navigation)
├── SUMMARY.md (file count and coverage)
├── MAINTENANCE_CHECKLIST.md (how to keep this folder in sync)
├── espi_app/
│   ├── main.md - Application entry point
│   ├── settings.md - Settings manager for persistent configuration
│   ├── main_window.md - Landing page and mode selection
│   ├── mode_card.md - The clickable mode selection card widget
│   ├── logo.md - The ESPI logo widget
│   ├── settings_dialog.md - Settings UI dialog (Hardware, UI tabs)
│   └── styles.md - Theme and styling system
├── espi_full_algorithm/
│   ├── camera_control.md - Basler camera interface
│   ├── camera_control_inclusive.md - Any USB camera or webcam interface
│   ├── camera_control_allied_vision.md - Allied Vision camera interface
│   ├── capture_and_display.md - Live preview, Basler
│   ├── capture_and_display_cv2.md - Live preview, any USB camera
│   ├── capture_and_display_allied.md - Live preview, Allied Vision
│   ├── complete_pipeline.md - Full frequency sweep pipeline, Basler
│   ├── complete_pipeline_inclusive.md - Full pipeline, any USB camera
│   ├── complete_pipeline_allied_vision.md - Full pipeline, Allied Vision
│   ├── live_graphs.md - Graph generation for pixel intensity analysis
│   ├── monitor_gui.md - Monitor mode GUI
│   ├── monitor.md - Monitor mode logic (command-line)
│   ├── run_experiment.md - Frequency sweep experiment (command-line)
│   ├── run_experiment_gui.md - Experiment mode GUI
│   ├── settings_dialog.md - run_experiment_gui.py's Settings page
│   ├── settings_manager.md - Persisted settings shared by both dashboards
│   ├── theme.md - Shared light/dark stylesheet builder
│   ├── sdg_control.md - Signal generator control package
│   └── basic_usage.md - Walkthrough of examples/basic_usage.py
└── camera/
    └── connection.md - Low-level camera connection (Learning/camera/, not used by the two GUIs)
```

## How to Use This Documentation

Each file in this folder describes a real Python file in the codebase in plain English. It uses:
- Simple language anyone can understand
- No em dashes (use hyphens or restructure sentences)
- Clear step-by-step descriptions of what each function does
- Explanations of why certain design choices were made

When you need to understand what a piece of code does, find the corresponding .md file and read the description.

## Key Concepts

### Settings System
Settings are stored in a JSON file at ~/.espi_app/settings.json. They include hardware configuration (camera, exposure), visualization preferences (which graphs to show), and UI preferences (theme). The SettingsManager class provides a simple interface to load, save, and modify settings.

### Two Modes of Operation
The application has two main modes:
1. Monitor Mode - Continuous live feed from the camera with optional intensity analysis
2. Scan Mode - Automated frequency sweep to measure how the sample responds at different frequencies

### Three Camera Types Supported
The system can work with three different camera types:
1. Basler cameras (USB3 or GigE)
2. USB/Webcam cameras (like the ELP camera)
3. Allied Vision cameras

Each has its own camera control module and capture implementation.

### Graphing System
The system can display real-time graphs showing pixel intensity across the image. This helps users understand what the camera is capturing and verify that settings are correct.

### Signal Generator Integration
For experiments, the system controls a signal generator to sweep through frequencies. As the frequency changes, the camera captures images to measure how the sample vibrates at each frequency.

## Module Dependencies

The application starts from espi_app/main.py, which loads settings and shows the landing page. Users can then choose between Monitor or Scan mode. Both modes use the core camera control and signal generation modules.

```
main.py
  -> SettingsManager (settings.py)
  -> LandingPage (main_window.py)
     -> SettingsDialog (settings_dialog.py)
     -> MonitorMode (calls monitor_gui.py or monitor.py)
     -> ScanMode (calls run_experiment_gui.py or run_experiment.py)
        -> CameraControl (camera_control.py or variants)
        -> SignalGeneratorControl (sdg_control/ package)
        -> ImageProcessing (live_graphs.py)
```

## Building Your Understanding

Start by reading:
1. This README
2. espi_app/main.md - to understand the application flow
3. espi_app/settings.md - to understand how configuration works
4. espi_full_algorithm/camera_control.md - to understand camera basics
5. espi_full_algorithm/sdg_control.md - to understand experiments

Then explore other modules based on what interests you.

## Keeping This Documentation Fresh

This pseudocode folder is kept in sync with the actual code. When you add or modify code:

1. Find the corresponding .md file (use the file mapping in MAINTENANCE_CHECKLIST.md)
2. Update it with your changes
3. If you're adding a whole new module, create a new .md file

See **MAINTENANCE_CHECKLIST.md** for quick reference on when and how to update.

The goal: This documentation should always match what the code actually does.
