# camera_control_allied_vision.py — Plain-Language Pseudocode

## What this file is for

This file is the Allied Vision equivalent of `camera_control.py`, using
Allied Vision's own SDK wrapper, `vmbpy` (Vimba X), instead of `pypylon` or
plain OpenCV. It supports Allied Vision's USB3 Vision and GigE Vision
cameras (models like Mako, Manta, Alvium, and Prosilica). Every function
shares the same name and purpose as the other two camera-control files, so a
script only needs to change its import line to switch camera hardware.

Exposure here is measured in **microseconds**, the same as `camera_control.py`
— unlike `camera_control_inclusive.py`, which uses OpenCV's log-2 scale.

## Beginner glossary

See `camera_control.md` for shared terms. One addition specific to this file:

- **vmbpy / Vimba X** — Allied Vision's official Python SDK. If it is not
  installed, this file still loads (so image-processing functions keep
  working), but every function that needs the camera prints a clear message
  explaining that `vmbpy` must be installed first.

## The camera handle wrapper

VimbaPy normally expects code to use Python's `with` keyword to open the SDK
and a camera together, and close them together automatically. This project
needs to keep the camera open across many separate function calls (grab a
frame here, change exposure there), so a small helper class does that job:

```
class _AVHandle:
    holds the open Vimba SDK instance and the open camera object together
    connect_camera() creates one of these
    disconnect_camera() closes both parts stored inside it
    every other function in this file takes one of these handles as its
        first argument, instead of a raw camera object
```

## Section 1 — Connecting and disconnecting

```
function connect_camera(camera_index = 0):
    if vmbpy is not installed: print a message and return nothing
    start the Vimba SDK
    list all detected Allied Vision cameras
    if none found, or camera_index is out of range:
        print an error, shut the SDK back down, return nothing
    open the camera at camera_index
    print its model name and resolution
    return an _AVHandle wrapping both the SDK and the camera

function disconnect_camera(camera):
    forget any stored ROI crop for this handle
    close the camera, then close the SDK
    print confirmation
```

## Section 2 — Camera settings

```
function set_exposure_manual(camera, exposure_us):
    turn off auto-exposure (ignored if this camera model lacks the feature)
    read the camera's hardware exposure range and clamp the request to it
    warn if clamping changed the value
    write the clamped exposure and return what was actually applied

function set_exposure_auto(camera):
    turn on continuous auto-exposure
    (prints a message instead of crashing if unsupported on this model)

function set_gain_manual(camera, gain):
    turn off auto-gain, clamp to the hardware range, write, read back, return

function set_gain_auto(camera):
    turn on continuous auto-gain

function set_pixel_format(camera, format_name = "Mono8"):
    set the camera's output pixel format
    "Mono8" is recommended: 8-bit greyscale, small files, no conversion needed

function get_camera_info(camera):
    read model, width, height, fps (if supported), exposure, gain, pixel format
    return them as one dictionary; unreadable values become nothing
```

## Section 3 — Region of interest (hardware ROI)

Like `camera_control.py` (and unlike the OpenCV version), this file can ask
the sensor itself to read out only part of the image, which genuinely
increases frame rate:

```
function set_capture_roi(camera, x, y, width, height):
    read the sensor's maximum width and height
    clamp x, y, width, height to fit inside the sensor
    set width and height BEFORE offsets (a Vimba SDK requirement)
    set OffsetX and OffsetY
    remember the rectangle in case a software crop fallback is ever needed
    if the hardware ROI call fails for any reason:
        fall back to storing the rectangle for a software crop instead

function reset_capture_roi(camera):
    forget any stored rectangle
    reset offsets to 0, then restore width/height to the sensor's maximum

function _apply_roi(frame, camera):
    (internal helper) crop the frame if a software-fallback rectangle was
    stored for this camera; otherwise return the frame unchanged
```

## Section 4 — Capturing frames

```
function _to_gray(image):
    (internal helper)
    if the image has 3 dimensions:
        if the third dimension has only 1 channel: drop it, already greyscale
        otherwise: convert color (BGR) to greyscale
    return a plain 2D greyscale array

function grab_single_frame(camera, timeout_ms = 2000):
    ask the SDK for one frame, waiting up to timeout_ms
    if the frame did not arrive complete: print an error, return nothing
    convert to a 2D numpy array and to greyscale using _to_gray()
    if the camera delivered 12-bit or 16-bit data: rescale it to 8-bit
    apply any stored ROI crop
    return the frame

function grab_single_frame_with_retry(camera, max_retries = 3):
    try grab_single_frame() up to max_retries times
    return the first success, or nothing if every attempt failed
    # handles occasional dropped packets on GigE network cameras

function grab_n_frames(camera, n, max_retries = 3):
    repeat n times, using grab_single_frame_with_retry()
    collect every success into a list and return it
    # list may be shorter than n if some grabs failed even after retrying

function grab_reference_frame(camera):
    calls grab_single_frame() and labels the result as the ESPI baseline
    # call this BEFORE turning on the signal generator, plate at rest

function discard_warmup_frames(camera, n = 5):
    grab and throw away n frames
    # lets the sensor fully apply a just-changed exposure or gain setting
    # before any measurement frame is captured
```

## Section 5 — ESPI image processing

Identical logic to `camera_control.py`: `substract_frames`,
`amplify_difference`, `binarize_diff`, `show_diff`, `run_espi_pipeline`,
`save_diff`, `average_img`. These functions only operate on numpy arrays and
have no camera-specific code — see `camera_control.md` Section 5 for the
pseudocode.

## Section 6 — Node detection (not yet implemented)

Same two stub functions as the other camera-control files: `detect_nodes`
and `has_nodes`, with no logic written yet.

## Section 7 — File logging

Identical logic to `camera_control.py`: `build_filename`, `save_image`,
`save_session_log`, `log_frame_metadata`. See `camera_control.md` Section 7.

## Section 8 — Quick view

Same as the other files' `save_and_display_img`: convert to greyscale using
`_to_gray()`, save with a timestamped name if none given, show until any key
is pressed.

## Section 9 — Live feed and multi-photo capture

```
function show_live_feed_from_camera(camera):
    keep a one-item list as a shared "latest frame" holder
        (needed because a nested function can read an outer variable but
        cannot reassign it directly without extra Python syntax; storing
        the value inside a list sidesteps that restriction)

    function _handler(cam, stream, frame):
        # called automatically by the SDK on a background thread whenever
        # a new frame arrives
        if the frame is complete: convert it to greyscale and store it
        always hand the frame buffer back to the SDK when done (cam.queue_frame)

    start streaming with _handler, using a small buffer pool
    loop:
        if a frame has arrived: show it with a "press e" overlay
        if 'e' is pressed: stop
    stop streaming and close the preview window

function capture_and_display(camera, n_images = 5):
    repeat n_images times:
        grab one frame (with retry)
        save it with a timestamped filename in the current folder
        display it with matplotlib (close the window to continue)
    return the list of saved file paths
```

The live feed here runs on a background thread supplied by the SDK (rather
than reading frames in the same loop that draws the window), which is a
difference from the simpler polling loops in the other two camera files.

## How the pieces connect in a typical experiment

```
camera = connect_camera()
show_live_feed_from_camera(camera)      # aim, press 'e'
set_exposure_manual(camera, 10000)      # 10 ms, in microseconds
set_gain_manual(camera, 0.0)

frames = grab_n_frames(camera, 2)
diff   = substract_frames(frames[0], frames[1])
save_image(diff, output_dir="output", frequency_hz=440.0, exposure_us=10000, step="test")

disconnect_camera(camera)
```
