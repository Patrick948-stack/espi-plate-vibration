# monitor.py — Plain-Language Pseudocode

## What this file is for

This is the interactive starting point for just watching a camera before
committing to a full frequency sweep. It asks which camera to use, its
index (if that camera type can have more than one), exposure, gain, and
`gain_factor`, then hands off to whichever `capture_and_display*.py` script
matches that camera. It is the `run_experiment.py` of "just let me look
through the camera", not of running the actual experiment.

## How to run it

```
python3 monitor.py
```

Press `q` inside either preview window to close the monitor and return to
the terminal.

## Lookup tables

```
_CAMERA_NAMES maps "1"->"Basler", "2"->"USB / webcam", "3"->"Allied Vision"

_CAPTURE_MODULES maps "1"->capture_and_display,
                       "2"->capture_and_display_cv2,
                       "3"->capture_and_display_allied
```

Both tables are keyed by the same "1" / "2" / "3" choice, so the rest of the
file only ever branches on that one string, never on a camera name.

## Input helper

```
function ask_positive_float(prompt, default):
    loop:
        value = ask(prompt, default, cast to float)
        # ask() already retries until the text converts to a float
        # this only adds the "> 0" rule on top of that
        if value > 0: return value
        print "<prompt> must be greater than 0" and ask again
```

Used for exposure (seconds) and `gain_factor`, neither of which makes sense
as zero or negative. Gain in dB is allowed to be zero or negative, so it
uses the plain `ask()` instead.

## Step-by-step questions

```
function choose_camera():
    show "Step 1 of 3" and list: 1 Basler, 2 USB/webcam, 3 Allied Vision
    return the number typed (default "2")

function choose_camera_index(camera_choice):
    if camera_choice is "1" (Basler):
        return 0 without asking anything
        # camera_control.py always connects to the first Basler device
        # pypylon finds, it has no index parameter to choose a different one
    otherwise:
        explain that 0 = first device found, try 1/2/etc if wrong camera opens
        loop: ask for a whole number >= 0, re-ask if negative

function choose_camera_settings():
    show "Step 2 of 3"
    explain that exposure is in SECONDS (0.01 = 10 ms)
    ask_positive_float for exposure (seconds)
    ask for gain (dB), zero or negative allowed
    explain that gain_factor only brightens the on-screen display, not the
        raw camera data
    ask_positive_float for gain_factor
    explain the two live graph options and that a 3D redraw is much slower
        than a histogram redraw
    ask for graph type: "none" (default), "histogram", or "3d"
    graph_type = nothing if the answer was "none", otherwise the answer
    return all four (exposure_s, gain_db, gain_factor, graph_type) as one
        dictionary

function confirm_settings(camera_choice, camera_index, settings):
    show "Step 3 of 3" — print a summary: camera name (+ index, unless
        Basler), exposure, gain, gain_factor, graph type ("none" if nothing)
    ask "Open the live monitor? (y/n)"
    return True if the answer was yes
```

## Launching the right preview script

```
function launch_monitor(camera_choice, camera_index, settings):
    module_name = _CAPTURE_MODULES[camera_choice]

    try to import that module
    if the import fails (SDK not installed):
        print which package to pip install, specific to this camera type
        return False

    convert exposure from seconds to microseconds (Basler and Allied need
        microseconds; this conversion just always happens up front)

    graph_type = settings.get("graph_type")  # nothing if the key is absent,
        so an older-style settings dict (built before this feature existed)
        still works instead of raising a KeyError

    try:
        if camera_choice is "1" (Basler):
            call module.main(exposure_us, gain_db, gain_factor, graph_type)
            # no camera_index argument — Basler doesn't support one

        if camera_choice is "2" (USB/webcam):
            call module.main(camera_index,
                              exposure = log2(exposure in seconds),
                              gain, gain_factor, graph_type)
            # OpenCV wants its own log-2 scale, not seconds or microseconds

        if camera_choice is "3" (Allied Vision):
            call module.main(camera_index, exposure_us, gain, gain_factor,
                              graph_type)

    if a ValueError happened (e.g. log2 of a non-positive number):
        print "Invalid exposure value" with the underlying reason
        return False
    if any other exception happened:
        print "The monitor stopped unexpectedly" with the reason
        return False

    return True
```

Every failure path prints something specific instead of letting a raw
traceback reach the terminal — missing SDK, bad exposure, or anything else
that goes wrong inside the chosen preview script's `main()`.

## Overall program flow

```
function main():
    clear the screen, print the header

    camera_choice = choose_camera()
    camera_index  = choose_camera_index(camera_choice)
    settings      = choose_camera_settings()

    if confirm_settings(...) says no: exit the program

    launch_monitor(camera_choice, camera_index, settings)
```

## Why this file exists

Before this file, checking a camera meant knowing which of three
`capture_and_display*.py` scripts matched your hardware, then opening it and
manually editing constants at the top for exposure, gain, and gain_factor.
`monitor.py` collapses that into the same short question-and-answer flow
`run_experiment.py` already uses for full sweeps, always in the same units
(seconds, dB), and picks the correct underlying script automatically.
