# capture_and_display_allied.py — Plain-Language Pseudocode

## What this file is for

This is the Allied Vision equivalent of `capture_and_display_cv2.py` — a
quick standalone preview script using the `vmbpy` (Vimba X) SDK instead of
generic OpenCV video capture. It opens the same two windows: a live raw feed
and a live frame-to-frame difference view. Unlike the other two files in
this group, this script is not wrapped in a `main()` function — its logic
runs directly from top to bottom as soon as the file is executed.

## How to run it

```
python3 capture_and_display_allied.py
```

Press `q` to quit.

## Settings at the top of the file

```
CAMERA_INDEX  = 0       # which Allied Vision camera to use (0 = first found)
EXPOSURE_US   = 10000   # exposure time in microseconds (10 ms)
LIST_CAMERAS  = False   # set True to print all detected cameras and exit
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

function frame_to_gray(frame):
    convert an SDK frame object into an OpenCV-style image
    if it has 3 dimensions:
        if only 1 channel: drop the extra dimension, already greyscale
        otherwise: convert color to greyscale
    return the plain 2D greyscale array
```

## Step-by-step pseudocode of the main script body

```
start the Vimba SDK

if LIST_CAMERAS is True:
    print every detected camera's ID, name, and model
    stop the program here

camera = get_camera(vmb, CAMERA_INDEX)
print which camera is being used

open the camera:
    set_exposure(camera, EXPOSURE_US)
    try to set pixel format to Mono8 (ignore if it fails)

    previous_gray_frame = nothing

    loop forever:
        try to grab one frame, waiting up to 2 seconds
        if it timed out: print a warning and try again
        if it failed for another reason: print an error and stop

        convert the frame to greyscale using frame_to_gray()
        show it in the "Live Feed" window

        if there was a previous greyscale frame:
            difference = absolute difference between this frame and the
                          previous one
            show it in the "Frame Subtraction" window

        remember this frame as "previous_gray_frame"

        if the 'q' key was pressed: stop looping

    close all windows

# closing the "with cam" and "with vmb" blocks automatically releases the
# camera and shuts down the SDK cleanly, even if an error occurred above
```

## Why this script exists

Same purpose as the other two preview scripts, but for Allied Vision
hardware — a fast way to confirm the camera connects, check that exposure in
microseconds looks reasonable, and see roughly how much frame-to-frame
difference the camera picks up, before committing to a full sweep with
`complete_pipeline_allied_vision.py` or `run_experiment.py`.
