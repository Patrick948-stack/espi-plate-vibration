# complete_pipeline.py — Plain-Language Pseudocode

## What this file is for

This file ties `signal_generator_control.py` and `camera_control.py`
together into a full automated ESPI frequency sweep for a Basler camera. It
steps the signal generator through a range of frequencies, captures and
processes images at each one, and saves the results — all without a human
needing to press a button at every step.

Two sibling files provide the same behavior for other camera hardware:
`complete_pipeline_inclusive.py` (any USB camera) and
`complete_pipeline_allied_vision.py` (Allied Vision cameras). This document
covers the Basler version; the other two are documented separately with
notes on what they add or change.

## The two measurement modes this file provides

- **`frequency_sweep()`** — pair subtraction. At each frequency, two frames
  are grabbed back-to-back and subtracted from each other. Good for
  higher-frequency vibration, where the plate visibly moves between two
  quick frames.
- **`reference_frequency_sweep()`** — reference subtraction. One frame is
  captured before the signal generator ever turns on (the plate at rest),
  and every later frame is subtracted from that same fixed baseline. Good
  for slow or low-amplitude vibration, where two consecutive frames would
  look almost identical.

## Beginner glossary

- **Settle time** — after changing frequency, a vibrating plate does not
  instantly reach a stable pattern; it rings through a brief transition
  first. `SETTLE_TIME_S` (2.0 seconds) is how long the sweep waits before
  trusting the images it captures.
- **Averaging** — capturing several difference images at the same frequency
  and blending them together cancels out random noise while keeping the real
  vibration pattern.

## Helper: watching the plate while it settles

```
function _settle_with_live_feed(camera, seconds, freq):
    end_time = now + seconds
    while now < end_time:
        grab one frame
        if it arrived: show it in a window with a
            "{freq} Hz | Settling: {remaining}s" countdown overlay
    # this replaces a plain pause so the screen stays live and responsive
    # instead of frozen for two full seconds at every frequency
```

## `frequency_sweep()` — pair subtraction mode

```
function frequency_sweep(start_freq, end_freq, step, n_averages,
                          exposure_us, gain, output_dir):

    # STEP 0 — sanity-check every input
    if start_freq <= 0, or end_freq < start_freq, or step <= 0,
       or n_averages <= 0, or exposure_us <= 0, or gain < 0:
        print which value is invalid and return nothing

    # STEP 1 — connect both devices
    instr = open_connection()
    if instr is nothing: print error, return nothing

    camera = connect_camera()
    if camera is nothing:
        print error
        close_connection(instr)   # don't leave the signal generator open
        return nothing

    # STEP 2 — lock camera brightness settings
    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain)

    # STEP 3 — configure and enable the signal generator
    sg_settings = configure_channel(instr, waveform="sine",
                                     frequency=start_freq, amplitude=1.0,
                                     offset=0.0, channel=1)

    # STEP 4 — prepare the output folder and results container
    create output_dir if it doesn't exist
    results = {}   # will map frequency -> averaged image

    # STEP 5 — build the exact list of frequencies to test
    # (computed as start + i*step each time, rather than adding step
    #  repeatedly, so floating-point rounding never skips the last value)
    frequencies = [start_freq, start_freq+step, ..., up to end_freq]

    for freq in frequencies:
        set_frequency(instr, freq, waveform=sg_settings["waveform"])

        _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

        difference_images = []
        repeat n_averages times:
            pair = grab_n_frames(camera, 2)
            if fewer than 2 frames arrived: warn and skip this pair
            diff = 20 x substract_frames(pair[0], pair[1])
            add diff to difference_images

        if difference_images is empty:
            warn and skip to the next frequency

        averaged = average_img(difference_images)
        if averaged is nothing: warn and skip

        save_image(averaged, output_dir, freq, exposure_us, step="espi_sweep")
        results[freq] = averaged

        show the amplified averaged image in a "Last Result" window

    # STEP 6 — clean up, always
    turn_off_output(instr)
    disconnect_camera(camera)
    close_connection(instr)

    # STEP 7 — report and return
    print how many frequencies got a result
    return results
```

## `reference_frequency_sweep()` — reference subtraction mode

Same overall shape as `frequency_sweep()`, with these differences:

```
function reference_frequency_sweep(start_freq, end_freq, step, n_averages,
                                    exposure_us, gain, output_dir):

    # steps 0-2 are identical: validate inputs, connect devices,
    # lock exposure and gain

    # STEP 3 — capture ONE reference frame BEFORE the signal generator
    #           turns on, so the plate is genuinely at rest
    reference = grab_n_frames(camera, 1)[0]
    if it failed: print error, disconnect everything, return nothing

    # STEP 4 — NOW configure and enable the signal generator
    sg_settings = configure_channel(instr, waveform="sine",
                                     frequency=start_freq, ...)

    for freq in frequencies:
        set_frequency(instr, freq, ...)
        _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

        # grab n_averages INDIVIDUAL frames (not pairs), and compare
        # every single one against the same fixed reference frame
        frames = grab_n_frames(camera, n_averages)
        difference_images = [substract_frames(reference, f) for f in frames]

        averaged = average_img(difference_images)
        save_image(averaged, output_dir, freq, exposure_us, step="espi_ref")
        results[freq] = averaged

    # clean up and return, same as frequency_sweep()
```

## Running the file directly

```
if this file is run directly (not imported):
    ask the user to choose mode 1 (pair) or mode 2 (reference)
    use a fixed set of example sweep settings
        (100-1000 Hz, step 100, 5 averages, 10ms exposure, 0dB gain)
    call the matching sweep function
    print which frequencies were measured
```

This block only executes when the file is run as `python complete_pipeline.py`
directly — importing `frequency_sweep` from another script skips it
entirely, which is why `run_experiment.py` can safely import the sweep
functions without triggering this example prompt.
