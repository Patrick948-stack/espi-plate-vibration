# capture_and_display.py — Plain-Language Pseudocode

## What this file is for

This is a small standalone script (not a library to import) for quickly
checking that a Basler camera is working and roughly what an ESPI difference
image looks like, without running a full frequency sweep. Running it opens
two live windows side by side: the raw camera feed, and the live subtraction
between each new frame and the one before it.

## How to run it

```
python3 capture_and_display.py
```

Press `q` to quit.

## Settings at the top of the file

```
EXPOSURE_US = 60000   # shutter time in microseconds (60 ms)
GAIN_DB     = 1.0     # amplification in dB
```

Editing these two constants changes the brightness of the preview.

## Step-by-step pseudocode

```
function main():
    camera = connect_camera()
    if camera is nothing:
        print "No camera found" and stop

    set_exposure_manual(camera, EXPOSURE_US)
    set_gain_manual(camera, GAIN_DB)

    print instructions for the two windows and the quit key

    previous_frame = nothing

    start continuously grabbing the newest available frame

    loop while grabbing:
        try to retrieve the next frame (wait up to 5 seconds)

        if a frame arrived successfully:
            show it in the "Live Feed" window

            if there was a previous frame:
                difference = 20 x (absolute difference between this frame
                                    and the previous frame)
                # multiplying by 20 exaggerates small changes so they are
                # visible on screen, even though this would overexpose a
                # real measurement — this script is only for a quick look
                show the difference in the "Frame Subtraction" window

            remember this frame as "previous_frame" for the next loop

        if the 'q' key was pressed: stop looping

    stop grabbing, close all windows, disconnect the camera
```

## Why this script exists

Running a full frequency sweep takes time and commits to specific settings.
This script is a fast sanity check — confirm the camera connects, confirm
exposure and gain look reasonable, and see roughly how much frame-to-frame
motion the subtraction picks up — before running `complete_pipeline.py` or
`run_experiment.py` for a real measurement.
