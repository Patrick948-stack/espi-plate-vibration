# complete_pipeline_allied_vision.py — Plain-Language Pseudocode

## What this file is for

This is the Allied Vision version of the automated ESPI frequency sweep,
using `camera_control_allied_vision.py` and the `vmbpy` SDK. Its overall
behavior matches `complete_pipeline_inclusive.py` closely (live-feed aiming,
warmup frames, retries, JSON metadata), but the code is organized more
tightly: several small helper functions do jobs that are inlined directly
inside the sweep functions in the other two pipeline files. Exposure here is
in **microseconds**, same as `camera_control.py`, not the OpenCV log-2 scale.

## Module-level settings

```
SETTLE_TIME_S    = 2.0   # seconds to wait after each frequency change
MAX_GRAB_RETRIES = 3     # retry attempts per frame if a grab fails
```

## Shared helper functions

Both sweep functions in this file call the same set of small helpers instead
of repeating this logic twice:

```
function _settle_with_live_feed(camera, seconds, freq):
    same idea as the other pipeline files — show live frames with a
    countdown overlay instead of freezing the screen during the wait

function _build_metadata(mode, cam_info, sg_identity, ...):
    assemble one dictionary containing every setting used for this sweep:
    date, time, subtraction mode, camera model/resolution, signal generator
    identity, frequency range, averages, waveform, amplitude, channel,
    settle time, requested vs. actual exposure and gain, full frequency list

function _save_metadata(metadata, output_dir):
    write the dictionary to session_metadata.json in output_dir

function _print_sweep_summary(results, failed, total, output_dir):
    print how many frequencies succeeded out of the total, list any that
    failed, and print where the images were saved

function _validate_sweep_params(start_freq, end_freq, step, n_averages,
                                 exposure_us, amplitude, channel):
    check every value is physically sensible; print a specific error and
    return False for the first one that is not

function _connect_devices(channel):
    open_connection() for the signal generator, connect_camera() for the
    camera; if either fails, clean up whatever was opened and return nothing
        for all three results

function _configure_signal_generator(instr, waveform, start_freq,
                                      amplitude, channel):
    call configure_channel(), confirm the output actually turned on,
    return the waveform name the instrument confirmed (or nothing on failure)

function _lock_camera_settings(camera, exposure_us, gain, warmup_frames):
    set_exposure_manual(), set_gain_manual(), warn if the applied exposure
    is far from what was requested, discard warmup_frames frames
    return the actual exposure and gain applied

function _cleanup(instr, camera, channel):
    turn off the signal generator output, close its connection,
    disconnect the camera, close all preview windows
    # called from a "finally" block so it always runs, even after a crash
```

## `frequency_sweep_allied_vision()` — pair subtraction mode

```
function frequency_sweep_allied_vision(start_freq, end_freq, step,
                                        n_averages, exposure_us, gain,
                                        output_dir, waveform="sine",
                                        amplitude=1.0, warmup_frames=10,
                                        channel=1, skip_live_feed=False):

    if not _validate_sweep_params(...): return nothing

    build the frequency list, rounding each value to avoid floating-point
        drift over a long sweep

    instr, camera, results, failed_frequencies = nothing, nothing, {}, []

    try:
        instr, camera, sg_identity = _connect_devices(channel)
        if instr is nothing: return nothing

        if not skip_live_feed:
            show_live_feed_from_camera(camera)   # aim, press 'e'

        actual_exposure, actual_gain = _lock_camera_settings(
            camera, exposure_us, gain, warmup_frames)

        active_waveform = _configure_signal_generator(
            instr, waveform, start_freq, amplitude, channel)
        if nothing: return nothing

        metadata = _build_metadata("pair", camera info, sg_identity, ...)
        _save_metadata(metadata, output_dir)
        save_session_log(camera info, output_dir)

        for each freq in frequencies:
            print progress and elapsed time

            result = set_frequency(instr, freq, waveform=active_waveform)
            if it failed: record as failed, skip to next

            _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

            difference_images = []
            repeat n_averages times:
                pair = grab_n_frames(camera, 2, max_retries=MAX_GRAB_RETRIES)
                if fewer than 2 arrived: warn, skip this pair
                diff = substract_frames(pair[0], pair[1])
                if valid: add to difference_images

            if difference_images is empty: record as failed, skip to next

            averaged = average_img(difference_images)
            if nothing: record as failed, skip to next

            save_image(averaged, output_dir, freq, exposure_us,
                       step="espi_av_raw")
            results[freq] = averaged
            show averaged.copy() in a "Last Result" window

    except Ctrl+C: print that the sweep was interrupted
    except any other error: print the full traceback, re-raise after clean-up
    finally: _cleanup(instr, camera, channel)

    _print_sweep_summary(results, failed_frequencies, total, output_dir)
    return results, or nothing if empty
```

## `reference_frequency_sweep_allied_vision()` — reference subtraction mode

Same shape as the pair-subtraction function above, with one extra step
inserted after locking camera settings and before configuring the signal
generator:

```
    # capture the resting reference BEFORE the signal generator turns on
    ref_frames = grab_n_frames(camera, n=3, max_retries=MAX_GRAB_RETRIES)
    if none arrived: print error, return nothing
    reference = average_img(ref_frames)   # average 3 frames to reduce
                                           # the reference's own noise
    if averaging failed: print error, return nothing
```

From there, every frequency in the loop grabs `n_averages` individual
frames and subtracts each one from this same fixed `reference`, rather than
subtracting frame pairs from each other. Saved files are labeled
`espi_av_ref_raw`, and the metadata records `"diff_mode": "reference"`.

## Running the file directly

```
if this file is run directly:
    ask the user to choose mode 1 (pair, default) or mode 2 (reference)
    use a fixed set of example settings (100-1000 Hz step 100, 5 averages,
        10000 microsecond exposure, 0 dB gain, sine wave, 1.0 Vpp,
        10 warmup frames)
    call the matching sweep function
    print which frequencies were measured, or that nothing was collected
```
