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

function section(title):
    print a small titled divider in the terminal
```

`ask()` is the building block every question in this file is built from — it
guarantees the rest of the script never receives text where a number was
expected, or an answer outside the allowed choices.

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
    if the import fails: warn and skip the preview

    connect to the camera
    if it fails: warn and skip the preview

    show_live_feed_from_camera(camera)   # aim, press 'e'
    disconnect the camera afterward, always (even on error)

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
        if the import fails (pypylon missing): print a clear error, stop
        convert exposure from seconds to microseconds
        call reference_frequency_sweep() if mode is "2", else frequency_sweep()

    if camera_choice is "2" (USB/webcam):
        import frequency_sweep_inclusive / reference_frequency_sweep_inclusive
            from complete_pipeline_inclusive
        if the import fails (opencv missing): print a clear error, stop
        convert exposure from seconds to OpenCV's log-2 scale
        always skip that pipeline's own live-feed step, because
            run_experiment.py already showed a preview itself
        call the matching sweep function

    if camera_choice is "3" (Allied Vision):
        import frequency_sweep_allied_vision /
               reference_frequency_sweep_allied_vision
            from complete_pipeline_allied_vision
        if the import fails (vmbpy missing): print a clear error, stop
        convert exposure from seconds to microseconds
        skip that pipeline's own live-feed step, same reason as above
        call the matching sweep function

    return whatever the chosen sweep function returned
```

## Overall program flow

```
function main():
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

## Why this file exists

Every other pipeline file requires knowing which function to import and
which units (microseconds vs. OpenCV log-2 scale) that specific camera
expects. `run_experiment.py` hides all of that behind four short questions,
always accepts exposure in plain seconds, and converts to whatever unit the
chosen camera needs internally — so a new lab member can run a full
experiment without reading any other file in this project first.
