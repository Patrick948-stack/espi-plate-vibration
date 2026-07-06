# capture_and_display_cv2.py — Plain-Language Pseudocode

## What this file is for

This is the OpenCV/webcam equivalent of `capture_and_display.py` — a quick
standalone preview script, not a library. It works with any camera the
operating system can already see (a laptop webcam, a USB camera, an ELP
camera), with no manufacturer SDK required. It opens the same two windows:
a live raw feed and a live frame-to-frame difference view.

## How to run it

```
python3 capture_and_display_cv2.py
```

Press `q` to quit.

## Settings at the top of the file

```
CAMERA_INDEX = 0   # which camera to open (0 = first one found)
EXPOSURE     = -6  # OpenCV log-2 exposure scale, NOT microseconds
                   #   -1  = long exposure / bright
                   #   -6  = medium (a reasonable starting point)
                   #   -11 = short exposure / dark
```

On a MacBook with Continuity Camera turned on, index 0 might actually be an
iPhone's camera rather than the built-in webcam — try 1 if the wrong camera
opens.

## Step-by-step pseudocode

```
function main():
    open the camera at CAMERA_INDEX using the AVFoundation backend (macOS)
    if it failed to open:
        print troubleshooting tips and stop

    switch to manual exposure and set it to EXPOSURE

    print instructions for the two windows and the quit key

    previous_gray_frame = nothing

    loop forever:
        read one frame
        if the read failed: print an error and stop

        convert the frame to greyscale
        show it in the "Live Feed" window

        if there was a previous greyscale frame:
            difference = absolute difference between this frame and the
                          previous one
            show it in the "Frame Subtraction" window

        remember this frame as "previous_gray_frame" for the next loop

        if the 'q' key was pressed: stop looping

    release the camera and close all windows
```

## Why this script exists

Same purpose as `capture_and_display.py`, but for anyone without Basler
hardware. It is often the very first thing to run when checking out this
project on a new laptop, since it needs nothing beyond `opencv-python` and
whatever camera the computer already has.
