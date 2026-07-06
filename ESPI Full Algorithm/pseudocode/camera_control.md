# camera_control.py — Plain-Language Pseudocode

## What this file is for

This file talks to a Basler camera (using the manufacturer's `pypylon`
library) and turns raw camera frames into ESPI fringe images. ESPI
(Electronic Speckle Pattern Interferometry) works by shining a laser on a
vibrating object and photographing it twice — once before and once during
motion. Subtracting the two photos reveals bright and dark bands (fringes)
that map out how the object moved.

Two sibling files, `camera_control_inclusive.py` (any USB camera) and
`camera_control_allied_vision.py` (Allied Vision cameras), provide the exact
same function names so a script can switch camera hardware by changing only
one import line. This document covers the Basler version; the other two are
documented separately, with notes on what differs.

## Beginner glossary

- **Exposure** — how long the camera sensor collects light for one frame.
  Longer exposure means a brighter image but more blur if something moves.
  This file measures exposure in **microseconds** (10000 = 10 ms).
- **Gain** — electronic amplification applied after exposure. Higher gain
  brightens a dark image but adds visible noise (grain).
- **ROI (Region of Interest)** — a rectangle telling the camera to read only
  part of the sensor, which speeds up capture.
- **numpy array** — an image is stored as a grid of numbers, one per pixel,
  from 0 (black) to 255 (white) for an 8-bit greyscale image.

## Section 1 — Connecting and disconnecting

```
function connect_camera():
    ask pypylon's TlFactory to find the first camera plugged in
    wrap it in an InstantCamera object and open a session
    print the camera's model name
    return the camera object
    if anything goes wrong (no camera, bad connection):
        print the error and return nothing

function disconnect_camera(camera):
    if the camera is mid-capture, stop it first
    close the session
    print confirmation
```

Every script that uses this file follows the same pattern: call
`connect_camera()`, check for nothing, then always call
`disconnect_camera()` before exiting — including on errors — so the camera
never gets stuck in a locked state.

## Section 2 — Camera settings

```
function set_exposure_manual(camera, exposure_us):
    turn off auto-exposure
    clamp exposure_us to the camera's hardware min/max
    write the value to the camera
    read back and return what the camera actually accepted

function set_exposure_auto(camera):
    open the auto-exposure range to the full hardware limits
    target mid-grey brightness
    turn on continuous auto-exposure
    # note: never used during an actual ESPI measurement — only for aiming

function set_gain_manual(camera, gain):
    turn off auto-gain, clamp to hardware limits, write, read back, return

function set_gain_auto(camera):
    turn on continuous auto-gain

function set_pixel_format(camera, format_name):
    set the camera's output format (e.g. "Mono8" for 8-bit greyscale)

function get_camera_info(camera):
    read model, serial number, width, height, exposure, gain, pixel format
    return them all as one dictionary
```

For ESPI, exposure and gain must always stay on manual — if either drifts
between the reference and live frame, the brightness mismatch corrupts the
subtraction.

## Section 3 — Region of interest (ROI)

```
function set_capture_roi(camera, x, y, width, height):
    reset offsets to 0 first (required before resizing)
    clamp width/height/x/y to the sensor's limits and increment grid
    apply the new width, height, and offsets to the camera
    print the applied ROI

function reset_capture_roi(camera):
    reset offsets to 0, then restore width/height to the sensor's maximum
```

Because this is a real hardware ROI, the sensor itself only reads out the
smaller rectangle — so frame rate improves, unlike the software-crop version
in `camera_control_inclusive.py`.

## Section 4 — Capturing frames

```
function grab_single_frame(camera):
    tell the camera to grab exactly 1 frame
    wait up to 5 seconds for it to arrive
    if it succeeded: copy the pixel data into a numpy array and return it
    if it failed or timed out: print an error and return nothing

function grab_n_frames(camera, n):
    tell the camera to grab n frames
    loop while frames are still arriving:
        collect each successful frame into a list
        (frames that fail are skipped, so the list may be shorter than n)
    return the list

function grab_reference_frame(camera):
    just calls grab_single_frame() and labels the result as a baseline frame
```

All capture functions return nothing (or an empty list) on failure, so
calling code must always check the result before using it.

## Section 5 — ESPI image processing

```
function substract_frames(frame_a, frame_b):
    # uses cv2.absdiff instead of plain subtraction, because plain numpy
    # subtraction on 8-bit images wraps around (10 - 20 becomes 246, not -10)
    return the pixel-by-pixel absolute difference of the two frames

function amplify_difference(diff):
    stretch contrast so the darkest pixel becomes 0 and brightest becomes 255
    return the stretched image
    # necessary because raw differences are usually very dark and faint

function binarize_diff(diff, method):
    if method is "otsu": automatically pick the best black/white threshold
    else: use a fixed threshold of 127
    return (black_and_white_image, threshold_value_used)

function average_img(list_of_images):
    if the list is empty: warn and return nothing
    stack all images and compute the average value at every pixel
    round back to whole numbers (0-255) and return
    # averaging many noisy difference images cancels out random speckle noise

function run_espi_pipeline(reference, live):
    diff      = substract_frames(reference, live)
    amplified = amplify_difference(diff)
    binary, threshold = binarize_diff(amplified)
    colored   = apply a false-color map to amplified (blue = low, red = high)
    return a dictionary with diff, amplified, binary, colored, threshold

function show_diff(diff, amplified, binary):
    open on-screen windows for each image provided
    wait for any key press, then close all windows

function save_diff(diff, path):
    write the image to disk at the given path
    return whether it succeeded
```

## Section 6 — Node detection (not yet implemented)

```
function detect_nodes(diff, threshold_method):
    # TODO — not implemented. Meant to isolate regions that did not move.
    return nothing (stub)

function has_nodes(binary, min_area):
    # TODO — not implemented. Meant to answer yes/no if any node region exists.
    return nothing (stub)
```

These two functions exist as placeholders with full docstrings describing the
intended behavior, but the actual logic has not been written yet.

## Section 7 — File logging

```
function build_filename(frequency_hz, exposure_us, step, extension):
    get today's date as text
    figure out how many decimal places the frequency needs
        (so files always sort correctly by frequency, e.g. 170.2 vs 170.225)
    return a filename like "step_2026-06-10_00170.2Hz_010000us.png"

function save_image(image, output_dir, frequency_hz, exposure_us, step, bit_depth):
    if output_dir was not given: default to the Desktop
    pick .tiff for 16-bit images or .png for 8-bit images
    build the filename, create the output folder if missing
    write the image to disk
    return the full path saved, or nothing on failure

function save_session_log(session_info, output_dir):
    write a text file listing every key/value in session_info
    (typically the dictionary returned by get_camera_info())

function log_frame_metadata(frame_index, exposure_us, mean_brightness, output_dir):
    if frame_metadata.csv doesn't exist yet: write a header row first
    append one row: frame_index, timestamp, exposure, brightness
```

## Section 8 — Live preview and quick view

```
function show_live_feed_from_camera(camera):
    start continuously grabbing the newest available frame
    loop:
        show each frame in a window with "Press 'e' to continue" overlaid
        if the 'e' key is pressed: stop
    stop grabbing and close the window

function save_and_display_img(image, filename):
    convert to greyscale if the image has color channels
    if no filename given: build one from the current timestamp
    save to the current folder
    show it in a window until any key is pressed
```

## How the pieces connect in a typical experiment

```
camera = connect_camera()
show_live_feed_from_camera(camera)      # aim, press 'e'
set_exposure_manual(camera, 10000)      # lock settings before measuring
set_gain_manual(camera, 0.0)

reference = grab_reference_frame(camera)
live      = grab_single_frame(camera)
result    = run_espi_pipeline(reference, live)

save_image(result["colored"], output_dir="output", frequency_hz=440.0,
           exposure_us=10000, step="test")

disconnect_camera(camera)
```
