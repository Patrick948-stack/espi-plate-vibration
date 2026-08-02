# capture_and_display_allied.py — Plain-Language Pseudocode

## What this file is for

This is the Allied Vision equivalent of `capture_and_display_cv2.py` — a
quick preview script using the `vmbpy` (Vimba X) SDK instead of generic
OpenCV video capture. It opens the same two windows: a live raw feed and a
live frame-to-frame difference view.

This used to be the odd one out in the group: its logic ran directly from
top to bottom the moment the file was imported, not just when run directly.
That meant simply writing `import capture_and_display_allied` anywhere would
immediately try to open a physical camera. It is now wrapped in a `main()`
function, exactly like the other two scripts, so it can be imported safely.
`monitor.py` relies on this: it imports this file and calls `main()` only
after the user has confirmed their settings.

## How to run it

```
python3 capture_and_display_allied.py
```

Press `q` to quit.

## Settings at the top of the file (used only when run directly)

```
CAMERA_INDEX  = 0       # which Allied Vision camera to use (0 = first found)
EXPOSURE_US   = 10000   # exposure time in microseconds (10 ms)
GAIN          = None    # camera gain in dB, or None to leave it unchanged
LIST_CAMERAS  = False   # set True to print all detected cameras and exit
Gain_factor   = 20      # multiplier applied to the subtraction display only
```

## Helper functions

```
function get_camera(vmb, index):
    ask the SDK for every connected Allied Vision camera
    if none found: raise an error
    if index is out of range: raise an error
    return the camera at that index

function set_exposure(cam, exposure_us):
    turn off auto-exposure (ignore if unsupported on this model)
    write the exposure value in microseconds
    print a warning if it could not be applied

function set_gain(cam, gain):
    if gain is nothing: do nothing and return (caller wants gain untouched)
    turn off auto-gain (ignore if unsupported on this model)
    write the gain value in dB
    print a warning if it could not be applied

function frame_to_gray(frame):
    convert an SDK frame object into an OpenCV-style image
    if it has 3 dimensions:
        if only 1 channel: drop the extra dimension, already greyscale
        otherwise: convert color to greyscale
    return the plain 2D greyscale array
```

## Step-by-step pseudocode

```
function main(camera_index = CAMERA_INDEX, exposure_us = EXPOSURE_US,
              gain = GAIN, gain_factor = Gain_factor,
              list_cameras = LIST_CAMERAS, graph_type = nothing):
    start the Vimba SDK

    if list_cameras is True:
        print every detected camera's ID, name, and model
        return (no live feed opened)

    try to get_camera(vmb, camera_index)
    if that raised an error (no cameras / bad index):
        print the error message and return, instead of crashing

    print which camera is being used

    live_graph = live_graphs.create_live_graph(graph_type)
        # nothing unless graph_type is "histogram" or "3d"

    open the camera:
        set_exposure(camera, exposure_us)
        set_gain(camera, gain)
        try to set pixel format to Mono8 (ignore if it fails)

        previous_gray_frame = nothing

        loop forever:
            try to grab one frame, waiting up to 2 seconds
            if it timed out: print a warning and try again
            if it failed for another reason: print an error and stop

            convert the frame to greyscale using frame_to_gray()
            show it in the "Live Feed" window

            if live_graph is not nothing:
                live_graph.update(gray_frame)   # the RAW frame, not the diff

            if there was a previous greyscale frame:
                difference = absolute difference between this frame and
                              the previous one
                amplified  = difference scaled by gain_factor, CLIPPED at
                             255 instead of wrapping around (same fix as
                             the other two preview scripts)
                show "amplified" in the "Frame Subtraction" window

            remember this frame as "previous_gray_frame"

            if the 'q' key was pressed: stop looping

        close all windows
        close live_graph if it exists

    # closing the "with cam" and "with vmb" blocks automatically releases
    # the camera and shuts down the SDK cleanly, even if an error occurred
```

## Why this script exists

Same purpose as the other two preview scripts, but for Allied Vision
hardware — a fast way to confirm the camera connects, check that exposure in
microseconds looks reasonable, and see roughly how much frame-to-frame
difference the camera picks up, before committing to a full sweep with
`complete_pipeline_allied_vision.py` or `run_experiment.py`. `monitor.py` is
the recommended way to run this check now, since it asks for the settings
interactively and never touches the camera just from being imported.
