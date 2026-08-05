# Pseudocode Maintenance Checklist

Use this checklist whenever you write or modify code.

## Adding a New Feature

- [ ] Write the Python code
- [ ] Find the corresponding pseudocode file (.md)
- [ ] If file doesn't exist, create it following the template below
- [ ] Add description of new function/class
- [ ] Update related files section if needed
- [ ] Update INDEX.md if adding a whole new module

## Modifying Existing Code

- [ ] Make your code changes
- [ ] Ask: Did the external behavior change?
  - [ ] If YES: Update the pseudocode
  - [ ] If NO: Don't update pseudocode
- [ ] Update the corresponding .md file
- [ ] Verify related files section is still accurate
- [ ] Check INDEX.md still has correct reading order

## Bug Fixes

- [ ] Fix the bug in Python code
- [ ] Check if pseudocode describes buggy behavior
  - [ ] If YES (pseudocode is now wrong): Fix pseudocode
  - [ ] If NO (pseudocode was correct): Leave it alone
- [ ] Don't update pseudocode just because code was fixed

## Code Optimization

- [ ] Optimize the Python code
- [ ] Check if external behavior changed
  - [ ] If YES (e.g., function signature): Update pseudocode
  - [ ] If NO (same inputs/outputs): Leave pseudocode alone
- [ ] Remember: pseudocode documents behavior, not performance

## Major Refactoring

- [ ] Reorganize the Python code
- [ ] Update pseudocode to match new organization
- [ ] Create new .md files if splitting into modules
- [ ] Update INDEX.md with new file structure
- [ ] Update dependency graph in INDEX.md
- [ ] Update links in README.md if needed

## Adding a New Module

- [ ] Create new Python file(s)
- [ ] Create corresponding .md file in pseudocode folder
- [ ] Follow the template (see below)
- [ ] Add entry to INDEX.md "All Pseudocode Files" table
- [ ] Consider where it fits in reading recommendations
- [ ] Update dependency graph if it connects to existing modules

## Template for New Pseudocode File

Copy this when creating a new .md file:

```markdown
# module_name.py - Short Description

## Purpose

One sentence: what this code does.

## Main Functions/Classes

Brief list of key functions or classes.

## How It Works

High-level overview of the main workflow.

## Key Functions

### function_name()

What it does:
1. First step
2. Second step
3. Final step

Example:
```python
result = function_name()
```

(Repeat for each major function)

## Key Concepts

Explain important ideas in simple terms.

## Why This Design

Explain reasoning behind the structure.

## Related Files

- file1.py - How it connects
- file2.py - How it connects
```

## Quick Decision Tree

```
Did you write/modify Python code?
│
├─ YES → Does external behavior change?
│        │
│        ├─ YES → Update pseudocode .md file
│        │        └─ Also update INDEX.md if structure changed
│        │
│        └─ NO → Leave pseudocode alone
│
└─ NO → Nothing to do
```

## File Mapping Quick Reference

When you modify a Python file, find its pseudocode here:

| Python File | Pseudocode File |
|-------------|-----------------|
| espi_app/main.py | pseudocode/espi_app/main.md |
| espi_app/settings.py | pseudocode/espi_app/settings.md |
| espi_app/main_window.py | pseudocode/espi_app/main_window.md |
| espi_app/mode_card.py | pseudocode/espi_app/mode_card.md |
| espi_app/logo.py | pseudocode/espi_app/logo.md |
| espi_app/settings_dialog.py | pseudocode/espi_app/settings_dialog.md |
| espi_app/styles.py | pseudocode/espi_app/styles.md |
| ESPI Full Algorithm/camera_control.py | pseudocode/espi_full_algorithm/camera_control.md |
| ESPI Full Algorithm/camera_control_inclusive.py | pseudocode/espi_full_algorithm/camera_control_inclusive.md |
| ESPI Full Algorithm/camera_control_allied_vision.py | pseudocode/espi_full_algorithm/camera_control_allied_vision.md |
| ESPI Full Algorithm/live_graphs.py | pseudocode/espi_full_algorithm/live_graphs.md |
| ESPI Full Algorithm/capture_and_display.py | pseudocode/espi_full_algorithm/capture_and_display.md |
| ESPI Full Algorithm/capture_and_display_cv2.py | pseudocode/espi_full_algorithm/capture_and_display_cv2.md |
| ESPI Full Algorithm/capture_and_display_allied.py | pseudocode/espi_full_algorithm/capture_and_display_allied.md |
| ESPI Full Algorithm/complete_pipeline.py | pseudocode/espi_full_algorithm/complete_pipeline.md |
| ESPI Full Algorithm/complete_pipeline_inclusive.py | pseudocode/espi_full_algorithm/complete_pipeline_inclusive.md |
| ESPI Full Algorithm/complete_pipeline_allied_vision.py | pseudocode/espi_full_algorithm/complete_pipeline_allied_vision.md |
| ESPI Full Algorithm/monitor.py | pseudocode/espi_full_algorithm/monitor.md |
| ESPI Full Algorithm/monitor_gui.py | pseudocode/espi_full_algorithm/monitor_gui.md |
| ESPI Full Algorithm/run_experiment.py | pseudocode/espi_full_algorithm/run_experiment.md |
| ESPI Full Algorithm/run_experiment_gui.py | pseudocode/espi_full_algorithm/run_experiment_gui.md |
| ESPI Full Algorithm/settings_dialog.py | pseudocode/espi_full_algorithm/settings_dialog.md |
| ESPI Full Algorithm/settings_manager.py | pseudocode/espi_full_algorithm/settings_manager.md |
| ESPI Full Algorithm/theme.py | pseudocode/espi_full_algorithm/theme.md |
| ESPI Full Algorithm/sdg_control/*.py | pseudocode/espi_full_algorithm/sdg_control.md |

## Common Update Scenarios

### Scenario 1: Add a new function to camera_control.py

1. Write function in camera_control.py
2. Open espi_full_algorithm/camera_control.md
3. Find the right section (e.g., "Section 4: Image Capture")
4. Add a new subsection describing the function
5. Done

### Scenario 2: Change SettingsDialog layout

1. Modify settings_dialog.py
2. Open espi_app/settings_dialog.md
3. Update the "UI Tab" section (or whichever changed)
4. Update example if provided
5. Done

### Scenario 3: Split camera_control.py into multiple files

1. Split the Python code
2. Create new .md file(s) for new modules
3. Update espi_full_algorithm/camera_control.md to reference the split
4. Update INDEX.md to list new files
5. Update README.md dependency diagram
6. Done

### Scenario 4: Fix a bug in live_graphs.py

1. Fix the bug in live_graphs.py
2. Ask: Does the pseudocode describe the buggy behavior?
   - If YES: Update espi_full_algorithm/live_graphs.md
   - If NO: Leave pseudocode alone
3. Done

## Red Flags (When to Update Pseudocode)

- Function signature changed (parameters or return type)
- Function behavior changed (what it does)
- File organization changed (new sections or classes)
- Major design decision changed
- New file or module added

## Green Flags (When NOT to Update)

- Internal implementation changed but behavior is same
- Performance optimized
- Bug fixed but pseudocode was already correct
- Internal comments added
- Variable names refactored

## Questions?

If you're unsure whether to update pseudocode:

1. Ask: "Would someone reading this pseudocode expect this behavior?"
2. If YES and code no longer does that: Update pseudocode
3. If NO (they'd expect the new behavior): Update pseudocode
4. If UNSURE: Update it anyway (over-documenting is better than under-documenting)

Keep the pseudocode folder fresh and useful!
