# complete_pipeline_inclusive.py — Plain-Language Pseudocode

## What this file is for

This is the "works with any camera" version of `complete_pipeline.py`. It
runs the exact same kind of automated ESPI frequency sweep, but through
`camera_control_inclusive.py` (plain OpenCV) instead of a Basler-specific
SDK, so it works with USB webcams, ELP cameras, or almost anything else the
computer can already see.

Compared to `complete_pipeline.py`, this file adds several extra safety
steps that matter more for generic USB cameras: a live-feed aiming phase,
warmup-frame discarding, automatic retry on failed grabs, and a JSON
metadata file recording every setting used. See the table in
`README.md` for a full side-by-side comparison of all three pipelines.

## Beginner glossary

New terms not already covered in `complete_pipeline.md`:

- **Warmup frames** — the first few frames a camera delivers right after
  opening it, or right after changing exposure, may still reflect the OLD
  setting. Reading and discarding a handful of them ensures every frame used
  for a real measurement reflects the CURRENT setting.
- **Session metadata (JSON)** — a structured settings file saved next to the
  images, so anyone looking at the results later (including a future self)
  knows exactly what frequency range, exposure, gain, and camera were used.

## Module-level settings

```
SETTLE_TIME_S    = 2.0   # seconds to wait after each frequency change
MAX_GRAB_RETRIES = 3     # retry attempts per frame if a grab fails
```

## Helper: watching the plate while it settles

Identical idea to `complete_pipeline.py`'s `_settle_with_live_feed()` —
shows live frames with a countdown overlay instead of freezing the screen
during the settle pause.

## `frequency_sweep_inclusive()` — pair subtraction mode

```
function frequency_sweep_inclusive(start_freq, end_freq, step, n_averages,
                                    exposure, gain, output_dir,
                                    waveform="sine", amplitude=1.0,
                                    warmup_frames=10, channel=1,
                                    skip_live_feed=False):

    # STEP 1 — validate every input; stop early with a clear message
    #          rather than failing halfway through a sweep
    check start_freq, end_freq, step, n_averages, amplitude, channel

    build the frequency list once, up front, so it is available even if
        the sweep is interrupted before finishing

    instr, camera, results, failed_frequencies = nothing, nothing, {}, []

    try:
        # STEP 2 — connect both devices
        instr = open_connection()
        if nothing: print error, stop

        print the signal generator's identity string

        camera = connect_camera()
        if nothing: print error, stop

        # STEP 3 — aim the camera (skipped if skip_live_feed is True)
        if not skip_live_feed:
            show_live_feed_from_camera(camera)   # press 'e' to continue

        # STEP 4 — flush stale frames left over from the live feed
        discard_warmup_frames(camera, n=warmup_frames)

        # STEP 5 — lock exposure and gain, then flush a few more frames
        #          so the NEW settings are fully in effect
        actual_exposure = set_exposure_manual(camera, exposure)
        actual_gain     = set_gain_manual(camera, gain)
        if actual_exposure is far from the requested value: warn
        discard_warmup_frames(camera, n=5)

        # STEP 6 — configure and enable the signal generator
        sg_settings = configure_channel(instr, waveform, start_freq,
                                         amplitude, offset=0.0, channel)
        if the output did not turn on: print error, stop

        # STEP 7 — write session_metadata.json recording every setting:
        #          date, time, frequency range, averages, waveform,
        #          amplitude, exposure/gain requested vs. actual, camera
        #          resolution and fps, signal generator identity, and the
        #          full list of frequencies to be tested
        save the metadata file
        save_session_log(camera info, output_dir)

        # STEP 8 — the sweep loop
        for each freq in frequencies:
            print progress: which step number, elapsed time so far

            result = set_frequency(instr, freq, waveform=active_waveform)
            if it failed: record freq as failed, skip to next

            _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

            difference_images = []
            repeat n_averages times:
                pair = grab_n_frames(camera, 2, max_retries=MAX_GRAB_RETRIES)
                if fewer than 2 arrived: warn, skip this pair
                diff = substract_frames(pair[0], pair[1])
                if diff is valid: add it to difference_images

            if difference_images is empty:
                record freq as failed, skip to next

            averaged = average_img(difference_images)
            if averaged is nothing: record freq as failed, skip to next

            # averaged is already gain_factor-scaled (see the frame-pair
            # loop above), so the same array is both saved and shown live,
            # a copy() of it (cv2.putText draws in place)
            save_image(averaged, output_dir, freq, exposure, step="espi_raw")

            results[freq] = averaged
            show averaged.copy() in a "Last Result" window

    except the user pressing Ctrl+C:
        print that the sweep was interrupted, fall through to clean-up

    except any other unexpected error:
        print it, then re-raise after clean-up so the full error is visible

    finally:
        # STEP 9 — guaranteed clean-up, no matter how the try block ended
        if instr exists: turn off its output, close the connection
        if camera exists: disconnect it
        close all preview windows

    # STEP 10 — print a summary: how many frequencies succeeded vs failed
    return results, or nothing if nothing succeeded
```

## `reference_frequency_sweep_inclusive()` — reference subtraction mode

Same overall shape and safety structure as `frequency_sweep_inclusive()`,
with the same difference described in `complete_pipeline.md`: a single
reference frame is captured once, before the signal generator turns on
(step 6, inserted before configuring the signal generator), and every later
frequency subtracts each individually grabbed frame from that same fixed
reference instead of subtracting frame pairs from each other. The saved
files are labeled `espi_ref_raw` instead of `espi_raw`, and the metadata
file records `"diff_mode": "reference"`.

## Recent Changes

**The real Sweep now honors the Settings page's grayscale choice, not just Preview.**
Both sweep functions gained two new keyword parameters,
`grayscale_method="standard"`, `grayscale_color="R"` (matching
`DEFAULT_SETTINGS`, so any existing caller that omits them is unaffected).
`grayscale_method` is now forwarded into
`connect_camera(camera_index=0, grayscale_method=...)` in step 2, and every
captured frame (both members of each pair in step 8, and the reference
frame in the reference-subtraction variant) is run through
`_apply_grayscale_conversion()` (imported from `monitor_gui.py`, reused
rather than duplicated) before it is subtracted, applying the R/B channel
swap first whenever `format_info["needs_channel_swap"]` is set. A third
parameter, `grayscale_backend`, used to select between NumPy/Pillow/OpenCV
HSV single-channel extraction; it was removed along with the other two
backends, since NumPy slicing is now the only implementation.
`run_experiment.run_pipeline()` is the single place that reads these two
values from `settings_manager.load_settings()` and forwards them here.

## Running the file directly

```
if this file is run directly:
    ask the user to choose mode 1 (pair) or mode 2 (reference)
    use a fixed set of example settings (100-1000 Hz step 100, 5 averages,
        exposure -6, gain 0.0, sine wave, 1.0 Vpp, 10 warmup frames)
    call the matching sweep function
    print which frequencies were measured, or that nothing was collected
```
