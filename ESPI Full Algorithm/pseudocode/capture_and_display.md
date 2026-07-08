# capture_and_display.py — Plain-Language Pseudocode

## What this file is for

This is a quick preview script for a Basler camera, not a full sweep — it
opens two live windows side by side: the raw camera feed, and the live
subtraction between each new frame and the one before it. It is both
runnable directly and importable: `monitor.py` imports it and calls its
`main()` function with settings the user typed in, instead of editing the
constants at the top of this file.

## How to run it

```
python3 capture_and_display.py
```

Press `q` to quit.

## Settings at the top of the file (used only when run directly)

```
EXPOSURE_US = 60000   # shutter time in microseconds (60 ms)
GAIN_DB     = 1.0     # amplification in dB
Gain_factor = 20      # multiplier applied to the subtraction display only
```

Editing these constants changes the brightness of the preview when the file
is run on its own. When called through `monitor.py`, or by importing this
file and calling `main(...)` yourself, the caller's values are used instead.

## Step-by-step pseudocode

```
function main(exposure_us = EXPOSURE_US, gain_db = GAIN_DB,
              gain_factor = Gain_factor, graph_type = nothing):
    camera = connect_camera()
    if camera is nothing:
        print "No camera found" and stop

    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain_db)

    live_graph = live_graphs.create_live_graph(graph_type)
        # nothing unless graph_type is "histogram" or "3d" — see
        # live_graphs.md for how each type works

    print instructions for the two (or three, if a graph was requested) windows
        and the quit key

    previous_frame = nothing

    start continuously grabbing the newest available frame

    loop while grabbing:
        try to retrieve the next frame (wait up to 5 seconds)

        if a frame arrived successfully:
            show it in the "Live Feed" window

            if live_graph is not nothing:
                live_graph.update(frame)   # the RAW frame, not the diff

            if there was a previous frame:
                difference = absolute difference between this frame and
                              the previous frame
                amplified  = difference scaled by gain_factor, CLIPPED at
                             255 instead of wrapping around
                # this uses cv2.convertScaleAbs, not "gain_factor * diff".
                # plain multiplication on an 8-bit image wraps around past
                # 255 (e.g. a true value of 300 becomes 44, a dark speckle
                # in what should be a bright fringe) — convertScaleAbs
                # saturates at white instead, which is what a human
                # actually expects to see
                show "amplified" in the "Frame Subtraction" window

            remember this frame as "previous_frame" for the next loop

        if the 'q' key was pressed: stop looping

    stop grabbing, close all windows, close live_graph if it exists,
        disconnect the camera
```

## Why this script exists

Running a full frequency sweep takes time and commits to specific settings.
This script is a fast sanity check — confirm the camera connects, confirm
exposure and gain look reasonable, and see roughly how much frame-to-frame
motion the subtraction picks up — before running `complete_pipeline.py` or
`run_experiment.py` for a real measurement. `monitor.py` is the recommended
way to run this check now, since it asks for the settings interactively and
picks the right one of the three preview scripts automatically.
