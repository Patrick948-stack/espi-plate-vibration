# Pseudocode Documentation Summary

## What Was Created

A complete pseudocode folder documenting every major file in the ESPI Camera Control project. This folder mirrors the actual project structure, making it easy to find documentation for any code file.

### Files Created

**27 pseudocode files in plain English:**

#### Application Framework (espi_app/)
- main.md - Application entry point
- settings.md - Persistent configuration system
- main_window.md - Landing page GUI
- mode_card.md - The clickable mode selection card widget
- logo.md - The ESPI logo widget
- settings_dialog.md - Settings interface (Hardware, UI tabs)
- styles.md - Theme and styling system

#### Core ESPI System (espi_full_algorithm/)
- run_experiment_gui.md / run_experiment.md - Frequency sweep experiment, GUI and command-line
- monitor_gui.md / monitor.md - Live camera monitor, GUI and command-line
- camera_control.md / camera_control_inclusive.md / camera_control_allied_vision.md - Camera interface, one per camera type
- capture_and_display.md / capture_and_display_cv2.md / capture_and_display_allied.md - Live preview, one per camera type
- complete_pipeline.md / complete_pipeline_inclusive.md / complete_pipeline_allied_vision.md - Full sweep pipeline, one per camera type
- live_graphs.md - Real-time visualization
- settings_dialog.md - run_experiment_gui.py's own Settings page
- settings_manager.md - Persisted settings shared by both dashboards
- theme.md - The shared light/dark stylesheet builder
- sdg_control.md - Signal generator control package
- basic_usage.md - Walkthrough of examples/basic_usage.py

#### Supporting Systems
- camera/connection.md - Low-level camera connection (Learning/camera/, not used by the two GUIs)

#### Documentation & Navigation
- README.md - High-level overview and how to use this folder
- INDEX.md - Complete index with reading recommendations
- SUMMARY.md - This file
- MAINTENANCE_CHECKLIST.md - How to keep this folder in sync with the code

## Total Coverage

All major modules in the project are now documented:

- 7 espi_app files (PyQt6 GUI framework)
- 19 espi_full_algorithm files (core ESPI measurement, all three camera types plus the signal generator package)
- 1 camera file (a low-level learning exercise, not part of either GUI)

## Key Features of This Documentation

### Plain English

- No em dashes (use regular hyphens or restructure)
- Simple language anyone can understand
- Explains the WHY, not just the WHAT
- Beginner-friendly jargon explanations

### Mirrors Project Structure

```
pseudocode/
├── README.md (overview)
├── INDEX.md (navigation)
├── SUMMARY.md (this file)
├── MAINTENANCE_CHECKLIST.md
├── espi_app/
│   ├── main.md
│   ├── settings.md
│   ├── main_window.md
│   ├── mode_card.md
│   ├── logo.md
│   ├── settings_dialog.md
│   └── styles.md
├── espi_full_algorithm/
│   ├── camera_control.md, camera_control_inclusive.md, camera_control_allied_vision.md
│   ├── capture_and_display.md, capture_and_display_cv2.md, capture_and_display_allied.md
│   ├── complete_pipeline.md, complete_pipeline_inclusive.md, complete_pipeline_allied_vision.md
│   ├── monitor_gui.md, monitor.md
│   ├── run_experiment_gui.md, run_experiment.md
│   ├── live_graphs.md, settings_dialog.md, settings_manager.md, theme.md
│   └── sdg_control.md, basic_usage.md
└── camera/
    └── connection.md
```

Matches your actual codebase layout, so documentation is always where you expect it.

### Structured Format

Each file includes:
1. **Purpose** - What this code does
2. **Step-by-step Explanations** - How functions work
3. **Key Concepts** - Important ideas
4. **Design Rationale** - Why this approach was chosen
5. **Examples** - Typical usage patterns
6. **Related Files** - How modules connect

## How to Use This Documentation

### For Learning

1. Start with `README.md` for high-level overview
2. Pick a topic that interests you
3. Read the corresponding pseudocode file
4. Then read the actual Python source to see implementation

Example journey:
```
README.md 
  -> espi_app/main.md 
  -> espi_app/settings.md 
  -> espi_full_algorithm/camera_control.md
```

### For Development

1. Find the file you need to modify
2. Read its pseudocode file first
3. Understand the current design
4. Make informed changes
5. Check if related files need updates

### For Debugging

1. Identify which module is causing issues
2. Read its pseudocode to understand expected behavior
3. Compare actual behavior to documentation
4. Spot the discrepancy

### For Onboarding New Team Members

Assign reading in this order:
1. README.md (5 min overview)
2. espi_app/main.md (10 min, understand entry point)
3. espi_full_algorithm/camera_control.md (15 min, understand core)
4. espi_full_algorithm/complete_pipeline.md (20 min, understand workflow)

Total: ~50 minutes to understand the whole system.

## What This Is NOT

This pseudocode is intentionally high-level. It is not:

- Line-by-line code translation
- A substitute for reading actual code
- Complete implementation details
- API documentation (though it covers that too)
- Performance-optimized pseudocode

For those, read the actual Python source files.

## Next Steps

### For Understanding

1. Open [README.md](README.md)
2. Choose a module to explore
3. Read the corresponding .md file
4. Read the actual Python code
5. Experiment with the code

### For Contributing

1. Read the pseudocode for the file you're modifying
2. Understand the current design
3. Make your changes to the Python file
4. Update the pseudocode documentation if design changes
5. Run tests
6. Commit with clear messages

### For Maintaining

Keep this documentation updated whenever:
- A major function is added or removed
- File organization changes
- A new module is created
- Design decisions change

## Convention Notes

When you read these files, remember:

- No em dashes (all prose is written plainly)
- Numbered lists are step-by-step processes
- Indented bullet lists are hierarchical information
- Code blocks show examples, not actual implementation
- "What it does" sections describe behavior, not syntax

## File Maintenance

Each pseudocode file should be updated when:

1. **New functions added** - Add a new section describing them
2. **Major refactoring** - Update affected sections
3. **Design changes** - Update the "Why This Design" section
4. **Documentation needed** - Add explanations of complex algorithms

Don't update if:
- Only fixing a bug (behavior is same)
- Only optimizing (behavior is same)
- Only adding comments (not changing external interface)

## Questions?

If something in the pseudocode is unclear:
1. Read the actual Python source for that file
2. Check git history to understand why it was designed that way
3. Ask clarifying questions in project discussions

These pseudocode files should help you understand and contribute to the project. They're part of the documentation that keeps the project maintainable and welcoming to new team members.

Enjoy exploring the ESPI Camera Control Project!
