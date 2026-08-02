# run_experiment.py — Plain-Language Pseudocode

## What this file is for

This is the single starting point for running any ESPI experiment in this
project. Instead of picking which pipeline file to import and which
function to call, running this one file asks a short series of plain-English
questions, then runs the correct sweep automatically and displays the
results at the end. No code needs to be edited and no other file needs to be
known about.

## How to run it

```
python3 run_experiment.py
```

## Small helper functions

```
function clear():
    clear the terminal screen (different command on Windows vs Mac/Linux)

function header():
    print a banner: project name and lab name

function ask(prompt, default, cast, valid):
    loop:
        show the prompt (with the default value, if any) and wait for input
        if nothing was typed and a default exists: return the default
        if nothing was typed and there is no default: ask again
        try converting the typed text to the expected type (e.g. float)
        if that conversion fails: explain the problem and ask again
        if a list of valid answers was given and the answer isn't in it:
            explain the valid choices and ask again
        return the accepted value

function ask_positive_float(prompt, default):
    loop:
        value = ask(prompt, default, cast to float)
        if value > 0: return value
        explain "<prompt> must be greater than 0" and ask again
    # used for exposure — a zero or negative exposure would otherwise
    # reach math.log2() deep inside run_pipeline() and crash with "math
    # domain error" instead of being caught here, the moment it was typed.
    # monitor.py imports this exact function instead of keeping its own copy.

function section(title):
    print a small titled divider in the terminal
```

`ask()` is the building block every question in this file is built from — it
guarantees the rest of the script never receives text where a number was
expected, or an answer outside the allowed choices.

## Error diagnostics

```
_ON_WINDOWS = True only when running on Windows

function _missing_sdk_message(camera_choice, module_name, error):
    print "[ERROR] Could not load {module_name}: {error}"
    if camera_choice is "1" (Basler):
        print "pip install pypylon", plus a note that the Pylon Camera
            Software Suite must also be installed separately (basler.com)
    if camera_choice is "2" (USB/webcam):
        print "pip install opencv-python"
    if camera_choice is "3" (Allied Vision):
        print how to install the Vimba X .whl file, using a Windows-style
            "C:\path\to\..." example if _ON_WINDOWS, otherwise "/path/to/..."
```

Used by both `run_pipeline()` (running the actual sweep) and
`_show_preview_feed()` (showing the live preview before it), so a missing
camera SDK always produces the exact same, specific message no matter which
of those two code paths hits it first.

## Step-by-step questions

```
function choose_camera():
    show "Step 1 of 4" and list: 1 Basler, 2 USB/webcam, 3 Allied Vision
    return the number typed (default "2")

function choose_mode():
    show "Step 2 of 4" and explain pair subtraction vs. reference subtraction
    return "1" (pair, default) or "2" (reference)

function choose_sweep_params():
    show "Step 3 of 4"
    ask for: start frequency, end frequency, step size, frames per frequency
    explain that exposure is entered in SECONDS (e.g. 0.01 = 10 ms)
    ask for: exposure (seconds), gain (dB), output folder
    return all of these as one dictionary

function confirm_settings(camera_choice, mode_choice, params):
    show "Step 4 of 4" — print a readable summary of every choice so far
    ask "Start the experiment? (y/n)"
    return True if the answer was yes
```

## Showing results after the sweep

```
function show_results(results, output_dir):
    if matplotlib is not installed:
        print where the images were saved and stop (no visual viewer)

    if there are no results: print a message and stop

    figure out how many decimal places every frequency label needs so no
        two frequencies look identical on screen

    # build and save a single grid image showing every frequency at once
    arrange all result images into a grid (up to 4 columns)
    label each tile with its frequency
    save this grid as "sweep_results_<timestamp>.png" in output_dir

    # open an interactive one-at-a-time viewer
    show the first result image
    on right-arrow or space: advance to the next image
    on left-arrow: go back to the previous image
    on Escape: close the viewer
```

## Live preview before the sweep starts

```
_CAMERA_LIBRARY maps "1"->camera_control, "2"->camera_control_inclusive,
                      "3"->camera_control_allied_vision

function _show_preview_feed(camera_choice):
    dynamically import the matching camera library
        (done at call-time, not at the top of the file, so a machine
        missing e.g. pypylon does not crash just from opening this script)
    if the import fails (SDK not installed):
        _missing_sdk_message(camera_choice, module_name, error)
        skip the preview, but let the rest of the program continue
    if the import succeeds but is missing an expected function:
        warn that the file may be outdated or partially edited, skip preview
        # a different problem from "not installed" — the module loaded fine

    connect to the camera
    if it fails: warn and skip the preview

    try:
        show_live_feed_from_camera(camera)   # aim, press 'e'
    if that crashes (e.g. USB cable came loose while aiming):
        warn and continue anyway — the preview is a convenience, not a
        requirement, so it must not take down the whole program
    finally:
        disconnect the camera, always (even on error)

function reconfigure_if_needed(camera_choice, params):
    loop:
        ask "Adjust settings before starting? (camera / signal / both / no)"
        if "no": return params unchanged

        if adjusting camera: ask new exposure (seconds) and gain
        if adjusting signal: ask new frequency range, step, averages

        _show_preview_feed(camera_choice)   # see the effect of the change

        print the updated settings
        ask "Change anything else? (y/n)"
        if "n": return params
```

## Running the chosen pipeline

```
function run_pipeline(camera_choice, mode_choice, params):
    build a dictionary of the shared settings every pipeline needs
        (start_freq, end_freq, step, n_averages, gain, output_dir)

    if camera_choice is "1" (Basler):
        import frequency_sweep / reference_frequency_sweep
            from complete_pipeline
        if the import fails: _missing_sdk_message(...), stop
        convert exposure from seconds to microseconds
        sweep_fn = reference_frequency_sweep if mode is "2" else frequency_sweep

    elif camera_choice is "2" (USB/webcam):
        import frequency_sweep_inclusive / reference_frequency_sweep_inclusive
            from complete_pipeline_inclusive
        if the import fails: _missing_sdk_message(...), stop
        try to convert exposure from seconds to OpenCV's log-2 scale
        if exposure was 0 or negative (log2 has no answer for that):
            print "[ERROR] Invalid exposure" with the value and a hint, stop
        always skip that pipeline's own live-feed step, because
            run_experiment.py already showed a preview itself
        sweep_fn = the matching reference/pair function

    elif camera_choice is "3" (Allied Vision):
        import frequency_sweep_allied_vision /
               reference_frequency_sweep_allied_vision
            from complete_pipeline_allied_vision
        if the import fails: _missing_sdk_message(...), stop
        convert exposure from seconds to microseconds
        skip that pipeline's own live-feed step, same reason as above
        sweep_fn = the matching reference/pair function

    else:
        print "[ERROR] Unknown camera choice", stop
        # defensive — choose_camera() only ever returns "1"/"2"/"3", this
        # only fires if run_pipeline() is called directly with a bad value

    try:
        return sweep_fn(**p)
    if that crashes (e.g. signal generator or camera disconnects mid-sweep):
        print "[ERROR] The experiment stopped unexpectedly: {error}"
        suggest checking that everything is still connected and powered on
        return nothing instead of letting a raw traceback end the program
```

## Overall program flow

```
function main():
    try:
        _run()   # everything below used to live directly in main()
    if Ctrl+C was pressed anywhere inside _run():
        print "Cancelled (Ctrl+C). No experiment was started." and exit quietly
        # Ctrl+C is a normal, intentional way to back out — it is not a bug,
        # so it must not show a raw traceback that looks like a crash

function _run():
    clear the screen, print the header

    camera_choice = choose_camera()
    mode_choice   = choose_mode()
    params        = choose_sweep_params()

    if confirm_settings(...) says no: exit the program

    _show_preview_feed(camera_choice)   # first look at the live camera

    loop:
        params = reconfigure_if_needed(camera_choice, params)
        if confirm_settings(...) says yes: stop looping

    print "Starting experiment"

    results = run_pipeline(camera_choice, mode_choice, params)

    if results were returned:
        print how many frequencies were measured and where images were saved
        show_results(results, params["output_dir"])
    else:
        print that no results were collected and to check earlier error messages
```

`show_results()` also wraps its interactive one-at-a-time viewer in its own
try/except: by the time that viewer opens, the results grid image has
already been saved to disk, so a display problem there (no X server on a
headless machine, an SSH session without X forwarding) prints a warning and
the saved file's location instead of making it look like the whole sweep
failed.

## Why this file exists

Every other pipeline file requires knowing which function to import and
which units (microseconds vs. OpenCV log-2 scale) that specific camera
expects. `run_experiment.py` hides all of that behind four short questions,
always accepts exposure in plain seconds, and converts to whatever unit the
chosen camera needs internally — so a new lab member can run a full
experiment without reading any other file in this project first.
