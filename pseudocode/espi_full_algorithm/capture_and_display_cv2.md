# capture_and_display_cv2.py — Plain-Language Pseudocode

## What this file is for

This is the OpenCV/webcam equivalent of `capture_and_display.py` — a quick
preview script. It works with any camera the operating system can already
see (a laptop webcam, a USB camera, an ELP camera), with no manufacturer SDK
required. It opens the same two windows: a live raw feed and a live
frame-to-frame difference view. It is both runnable directly and importable:
`monitor.py` imports it and calls its `main()` function with settings the
user typed in.

## How to run it

```
python3 capture_and_display_cv2.py
```

Press `q` to quit.

## Settings at the top of the file (used only when run directly)

```
CAMERA_INDEX = 0    # which camera to open (0 = first one found)
EXPOSURE     = -6   # OpenCV log-2 exposure scale, NOT seconds or microseconds
                    #   -1  = long exposure / bright
                    #   -6  = medium (a reasonable starting point)
                    #   -11 = short exposure / dark
GAIN         = 0.0  # camera gain, camera-dependent scale — not every camera
                    #   lets OpenCV control this, it may be silently ignored
Gain_factor  = 20   # multiplier applied to the subtraction display only
```

On a MacBook with Continuity Camera turned on, index 0 might actually be an
iPhone's camera rather than the built-in webcam — try 1 if the wrong camera
opens.

## Step-by-step pseudocode

```
function _capture_backend():
    # cv2.CAP_AVFOUNDATION only exists on macOS. This file used to
    # hardcode it unconditionally, which meant the camera would fail to
    # open (or silently fall back to something slower) on Windows.
    if running on macOS:   return cv2.CAP_AVFOUNDATION
    if running on Windows: return cv2.CAP_DSHOW
    otherwise:              return cv2.CAP_ANY  # let OpenCV pick

function main(camera_index = CAMERA_INDEX, exposure = EXPOSURE,
              gain = GAIN, gain_factor = Gain_factor, graph_type = nothing):
    open camera_index using _capture_backend()
    if it failed to open:
        print troubleshooting tips (mention camera_index) and stop

    switch to manual exposure, set it to "exposure" (still the log-2 scale,
        callers that have seconds must convert with log2(seconds) first —
        this is exactly what monitor.py does before calling main())
    set gain to "gain"

    live_graph = live_graphs.create_live_graph(graph_type)
        # nothing unless graph_type is "histogram" or "3d"

    print instructions for the two (or three) windows and the quit key

    previous_gray_frame = nothing

    loop forever:
        read one frame
        if the read failed: print an error and stop

        convert the frame to greyscale
        show it in the "Live Feed" window

        if live_graph is not nothing:
            live_graph.update(gray_frame)   # the RAW frame, not the diff

        if there was a previous greyscale frame:
            difference = absolute difference between this frame and the
                          previous one
            amplified  = difference scaled by gain_factor, CLIPPED at 255
                         instead of wrapping around (see the note on this
                         in capture_and_display.md — same fix, same reason)
            show "amplified" in the "Frame Subtraction" window

        remember this frame as "previous_gray_frame" for the next loop

        if the 'q' key was pressed: stop looping

    always release the camera, close all windows, and close live_graph if
        it exists — even if the loop above raised an unexpected error
```

## Why this script exists

Same purpose as `capture_and_display.py`, but for anyone without Basler
hardware. It is often the very first thing to run when checking out this
project on a new laptop, since it needs nothing beyond `opencv-python` and
whatever camera the computer already has. `monitor.py` is the recommended
way to run this check now, since it asks for the settings interactively.
