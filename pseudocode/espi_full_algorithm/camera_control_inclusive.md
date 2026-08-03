# camera_control_inclusive.py — Plain-Language Pseudocode

## What this file is for

This file is the "works with anything" version of `camera_control.py`. Where
`camera_control.py` only supports Basler cameras through their dedicated
`pypylon` SDK, this file uses plain OpenCV (`cv2.VideoCapture`), which works
with almost any webcam, USB camera, or ELP-style USB camera the operating
system can already see. Every function has the same name and the same
purpose as in `camera_control.py`, so a script can switch cameras by
changing only its import line.

Because OpenCV talks to cameras through generic operating-system drivers
rather than a manufacturer SDK, some things are less precise than the Basler
version — these differences are called out below wherever they matter.

## Beginner glossary

See `camera_control.md` for shared terms (exposure, gain, ROI, numpy array).
One important difference here:

- **OpenCV exposure scale** — this file does NOT use microseconds. It passes
  whatever number is given straight to the camera driver, which usually
  interprets it on a log-2 scale: `-6` is roughly 15 ms, `-1` is roughly
  500 ms (bright), `-11` is roughly 0.5 ms (dark). The exact meaning depends
  on the camera.

## Section 1 — Connecting and disconnecting

```
function connect_camera(camera_index = 0):
    open cv2.VideoCapture at camera_index
        (0 = first camera the OS finds; try 1, 2, ... if the wrong one opens)
    if it failed to open: print troubleshooting tips and return nothing
    read back width/height to confirm frames are really arriving
    return the camera object

function disconnect_camera(camera):
    forget any stored ROI crop for this camera (see Section 3)
    release the camera
    print confirmation
```

## Section 2 — Camera settings

```
function set_exposure_manual(camera, exposure_value):
    switch the driver to manual exposure mode
    write exposure_value (log-2 scale, NOT microseconds)
    read back and return whatever the driver actually applied
    # note: some camera drivers ignore this entirely — if brightness never
    # changes, that camera does not support software exposure control

function set_exposure_auto(camera):
    switch the driver back to automatic exposure

function set_gain_manual(camera, gain):
    write the gain value (scale depends on the camera)
    read back and return the applied value
    # silently ignored on cameras that don't expose a gain control

function set_gain_auto(camera):
    reset gain to 0
    # OpenCV has no universal "auto gain on" command, so this is the closest
    # equivalent available across different camera drivers

function set_pixel_format(camera, format_name):
    NOT SUPPORTED — OpenCV cannot choose pixel format
    print a notice and do nothing
    # exists only so old code calling this function doesn't crash

function get_camera_info(camera):
    read width, height, fps, exposure, gain, brightness from the driver
    return them as one dictionary
    # some values may read as 0 or -1 if the driver doesn't expose them
```

## Section 3 — Region of interest (software crop)

Unlike `camera_control.py`, this file cannot tell the camera hardware to
read a smaller rectangle. Instead, the full frame is always read, and a crop
is applied afterward in software.

```
_roi_store = {}   # maps each camera's id number to (x, y, width, height)

function _apply_roi(frame, camera):
    look up a stored crop rectangle for this camera
    if none stored: return the frame unchanged
    otherwise: return the cropped rectangle from the frame

function set_capture_roi(camera, x, y, width, height):
    read the camera's full frame size
    clamp x, y, width, height so the crop cannot go outside the frame
    remember this rectangle in _roi_store for this camera
    print a note that the sensor still reads the full frame (no speed gain)

function reset_capture_roi(camera):
    remove the stored rectangle for this camera
```

## Section 4 — Capturing frames

```
function grab_single_frame(camera):
    read one frame from the camera
    if it failed: print an error and return nothing
    convert to greyscale if the frame has color channels
    apply the stored ROI crop, if any
    return the frame

function grab_single_frame_with_retry(camera, max_retries = 3):
    try grab_single_frame() up to max_retries times
    return the first successful frame, or nothing if every attempt failed
    # exists because USB cameras occasionally drop a frame under load

function grab_n_frames(camera, n, max_retries = 3):
    repeat n times:
        grab one frame using grab_single_frame_with_retry()
        add it to a list if it succeeded
    return the list (may be shorter than n if some grabs failed)

function grab_reference_frame(camera):
    calls grab_single_frame() and labels the result as the ESPI baseline

function discard_warmup_frames(camera, n = 5):
    read and throw away n frames in a row
    # after opening the camera or changing exposure, the first few frames
    # may still reflect the OLD setting; discarding them lets the sensor
    # fully settle before real measurement frames are captured
```

## Section 5 — ESPI image processing

Identical logic to `camera_control.py` — these functions only operate on
numpy arrays and do not depend on which camera produced them:
`substract_frames`, `binarize_diff`, `show_diff`,
`run_espi_pipeline`, `save_diff`, `average_img`. See `camera_control.md`
Section 5 for the pseudocode; the only difference here is that
`substract_frames` returns nothing (instead of raising an error) if the two
frame shapes do not match.

## Section 6 — Node detection (not yet implemented)

Same two stub functions as `camera_control.py`: `detect_nodes` and
`has_nodes`. Neither has its logic written yet.

## Section 7 — File logging

Identical logic to `camera_control.py`: `build_filename`, `save_image`,
`save_session_log`, `log_frame_metadata`. See `camera_control.md` Section 7.

## Section 8 — Quick view

Same as `camera_control.py`'s `save_and_display_img`: convert to greyscale,
save with a timestamped filename if none given, display until a key press.

## Section 9 — Live feed and multi-photo capture

```
function show_live_camera(camera_index = 0):
    open a brand-new camera connection just for this preview
    loop:
        read and display a frame
        if 'e' is pressed: stop
    release this camera connection
    # opens its OWN connection — do not use this while another connection
    # to the same camera is already open, or the two may conflict

function show_live_feed_from_camera(camera):
    # safer version — reuses a camera connection that is already open
    loop:
        read a frame
        if the read failed: print an error and stop
        draw "Press 'e' when ready to start" on a copy of the frame
        show it in a window
        if 'e' is pressed: stop
    close the preview window

function capture_and_display(camera_index = 0, n_images = 5, exposure = -6):
    open its own camera connection
    switch to manual exposure at the given value
    repeat n_images times:
        read one frame, convert to greyscale
        save it with a timestamped filename in the current folder
        display it with matplotlib (close the window to continue)
    release the camera
    return the list of saved file paths
```

`capture_and_display` uses matplotlib instead of `cv2.imshow` because
matplotlib gives an interactive zoom/pan toolbar, useful for inspecting a
still photo closely — but it is too slow to use for a smooth live video feed,
which is why the live-preview functions above use `cv2.imshow` instead.

## How the pieces connect in a typical experiment

```
camera = connect_camera(camera_index=0)
show_live_feed_from_camera(camera)         # aim, press 'e'
discard_warmup_frames(camera, n=10)        # flush stale frames

set_exposure_manual(camera, -6)            # OpenCV log2 scale, not microseconds
set_gain_manual(camera, 0.0)

frames = grab_n_frames(camera, 2, max_retries=3)
diff   = substract_frames(frames[0], frames[1])
save_image(diff, output_dir="output", frequency_hz=440.0, exposure_us=-6, step="test")

disconnect_camera(camera)
```
