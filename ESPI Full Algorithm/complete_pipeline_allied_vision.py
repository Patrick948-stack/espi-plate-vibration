"""
complete_pipeline_allied_vision.py
Author: Patrick Mulikuza

ESPI frequency sweep pipeline for Allied Vision cameras (Vimba X SDK).

BEFORE USING THIS FILE
----------------------
  1. Install the Vimba X SDK from Allied Vision's website.
  2. Install VmbPy (not on PyPI):
         pip install git+https://github.com/alliedvision/VmbPy.git
  3. Plug in the Allied Vision camera and the signal generator, then run:
         python3 complete_pipeline_allied_vision.py
     or use run_experiment.py for a guided interactive launcher.

WHAT THIS FILE DOES
--------------------
It provides two sweep functions:
  frequency_sweep_allied_vision()
      Pair subtraction: grabs two frames at each frequency and subtracts
      them from each other. Best for high-frequency vibration where the
      plate moves noticeably between consecutive frames.

  reference_frequency_sweep_allied_vision()
      Reference subtraction: captures one frame at rest before the sweep,
      then subtracts that fixed baseline from every measurement frame.
      Best for slow vibration where consecutive frames look nearly identical.

DEPENDENCIES
------------
    pip install numpy opencv-python pyvisa pyvisa-py pyusb
    + vmbpy from https://github.com/alliedvision/VmbPy
    + libusb (macOS: brew install libusb)
"""

from __future__ import annotations

import cv2
import json
import math
import os
import time
import traceback
from datetime import datetime

from sdg_control import (
    open_connection,
    close_connection,
    get_identity,
    configure_channel,
    set_frequency,
    turn_on_output,
    turn_off_output,
)
from camera_control_allied_vision import *


# How long to wait at each frequency before grabbing frames.
# The plate needs time to reach a steady vibration after the frequency changes.
# 2 seconds is usually enough; increase if the plate takes longer to stabilise.
SETTLE_TIME_S = 2.0

# How many times to retry a failed frame grab before skipping that pair.
MAX_GRAB_RETRIES = 3


# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

def _settle_with_live_feed(camera, seconds: float, freq: float) -> None:
    """
    Wait for `seconds` seconds while showing a live camera feed.

    This replaces a plain time.sleep() so the user can watch the plate
    settle after each frequency change rather than staring at a frozen screen.

    Args:
        camera  : the camera handle from connect_camera()
        seconds : how long to wait
        freq    : the current frequency, shown as an overlay on the feed window
    """
    end_time = time.time() + seconds

    while time.time() < end_time:
        frame = grab_single_frame(camera)
        if frame is not None:
            display   = frame.copy()
            remaining = max(0.0, end_time - time.time())
            cv2.putText(
                display,
                f"{freq:.0f} Hz  |  Settling: {remaining:.1f}s",
                (10, 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                200,       # grey text — visible on a greyscale image
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("ESPI Sweep — Live Feed", display)

        # waitKey(1) is required for cv2 to actually draw the window.
        # Without this call the window freezes even though the loop is running.
        cv2.waitKey(1)


def _build_metadata(mode: str, cam_info: dict, sg_identity: str,
                    start_freq: float, end_freq: float, step: float,
                    n_averages: int, waveform: str, amplitude: float,
                    channel: int, exposure_us: float, actual_exposure: float | None,
                    gain: float, actual_gain: float | None,
                    frequencies: list) -> dict:
    """
    Build the session metadata dictionary saved to session_metadata.json.

    Keeping this in one place means both sweep functions write the same format,
    making it easy to compare experiment files later.
    """
    return {
        "experiment":         f"ESPI {mode} sweep — Allied Vision",
        "date":               datetime.now().strftime("%Y-%m-%d"),
        "time":               datetime.now().strftime("%H:%M:%S"),
        "diff_mode":          mode,
        "camera_type":        "Allied Vision (Vimba X)",
        "camera_model":       cam_info.get("model"),
        "camera_width_px":    cam_info.get("width"),
        "camera_height_px":   cam_info.get("height"),
        "sg_identity":        sg_identity,
        "start_freq_hz":      start_freq,
        "end_freq_hz":        end_freq,
        "step_hz":            step,
        "n_averages":         n_averages,
        "waveform":           waveform,
        "amplitude_vpp":      amplitude,
        "channel":            channel,
        "settle_time_s":      SETTLE_TIME_S,
        "exposure_requested_us": exposure_us,
        "exposure_actual_us":    actual_exposure,
        "gain_requested_db":     gain,
        "gain_actual_db":        actual_gain,
        "frequencies_hz":     frequencies,
    }


def _save_metadata(metadata: dict, output_dir: str) -> None:
    """Write the metadata dictionary to session_metadata.json in output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    meta_path = os.path.join(output_dir, "session_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Session metadata saved: {meta_path}")


def _print_sweep_summary(results: dict, failed: list,
                          total: int, output_dir: str) -> None:
    """Print a summary table at the end of a sweep."""
    print(f"\n{'=' * 50}")
    print(f"Sweep complete.")
    print(f"  Succeeded : {len(results)}/{total} frequencies")
    if failed:
        failed_strs = [f"{f:.1f} Hz" for f in failed]
        print(f"  Failed    : {len(failed)} — {failed_strs}")
    print(f"  Images in : {os.path.abspath(output_dir)}")
    print(f"{'=' * 50}")


def _validate_sweep_params(start_freq: float, end_freq: float, step: float,
                            n_averages: int, exposure_us: float,
                            amplitude: float, channel: int) -> bool:
    """
    Check that sweep parameters are physically reasonable.
    Returns True if all checks pass, False otherwise.
    """
    if start_freq <= 0:
        print(f"[ERROR] start_freq must be positive (got {start_freq}).")
        return False
    if end_freq < start_freq:
        print(f"[ERROR] end_freq must be >= start_freq (got {end_freq} < {start_freq}).")
        return False
    if step <= 0:
        print(f"[ERROR] step must be positive (got {step}).")
        return False
    if n_averages < 1:
        print(f"[ERROR] n_averages must be at least 1 (got {n_averages}).")
        return False
    if exposure_us <= 0:
        print(f"[ERROR] exposure_us must be positive (got {exposure_us}).")
        return False
    if amplitude <= 0:
        print(f"[ERROR] amplitude must be positive (got {amplitude} Vpp).")
        return False
    if channel not in (1, 2):
        print(f"[ERROR] channel must be 1 or 2 (got {channel}).")
        return False
    return True


def _connect_devices(channel: int):
    """
    Connect to the signal generator and the Allied Vision camera.

    Returns (instr, camera, sg_identity) on success, or (None, None, None)
    if either device could not be found.
    """
    print("Connecting to signal generator...")
    instr = open_connection(index=0)
    if instr is None:
        print("[ERROR] Signal generator not found. Check USB and driver.")
        return None, None, None
    sg_identity = get_identity(instr)
    print(f"  Signal generator: {sg_identity}")

    print("\nConnecting to Allied Vision camera...")
    result = connect_camera(camera_index=0)
    if result is None or (isinstance(result, tuple) and result[0] is None):
        print("[ERROR] Allied Vision camera not found. Check USB cable.")
        close_connection(instr)
        return None, None, None


    camera, format_info = result
    camera, format_info = result
    return instr, camera, sg_identity


def _configure_signal_generator(instr, waveform: str, start_freq: float,
                                 amplitude: float, channel: int,
                                 offset: float = 0.0) -> str | None:
    """
    Configure the signal generator and turn on its output.

    Returns the waveform name as confirmed by the generator, or None on failure.
    """
    print(f"\nConfiguring signal generator: {waveform}, {start_freq} Hz, "
          f"{amplitude} Vpp, channel {channel}...")

    sg_settings = configure_channel(
        instr,
        waveform  = waveform,
        frequency = start_freq,
        amplitude = amplitude,
        offset    = offset,
        channel   = channel,
    )

    # turn_on_output() returns the channel number on success, None on a
    # communication error. configure_channel()'s own return dict never had
    # a "channel output" key to check here (neither the old nor the new
    # signal generator library returns one) -- this used to check a key
    # that was always missing, so this branch always fired.
    if not sg_settings or turn_on_output(instr, channel=channel) is None:
        print(f"[ERROR] Could not turn on channel {channel} of the signal generator.")
        return None

    # Use the waveform name the generator confirmed, not our input string,
    # because the generator may normalise the name (e.g. "SINE" -> "sine").
    return sg_settings.get("waveform") or waveform


def _lock_camera_settings(camera, exposure_us: float,
                           gain: float, warmup_frames: int):
    """
    Set exposure and gain to manual mode and discard warmup frames.

    Returns (actual_exposure, actual_gain). Either may be None if the
    camera rejected the value.
    """
    print("\nLocking camera settings...")
    actual_exposure = set_exposure_manual(camera, exposure_us)
    actual_gain     = set_gain_manual(camera, gain)

    if actual_exposure is not None and abs(actual_exposure - exposure_us) > 100:
        print(f"  [WARNING] Camera applied {actual_exposure:.0f} µs "
              f"instead of the requested {exposure_us:.0f} µs.")

    # After changing exposure or gain the first few frames still reflect the
    # old settings. Discard them so the first measurement frame is clean.
    discard_warmup_frames(camera, n=warmup_frames)

    return actual_exposure, actual_gain


def _cleanup(instr, camera, channel: int) -> None:
    """
    Turn off the signal generator output and disconnect both devices.

    Called in a `finally` block so it runs even if the sweep raises an error.
    """
    print("\n--- Disconnecting devices ---")
    if instr is not None:
        try:
            turn_off_output(instr, channel=channel)
        except Exception:
            pass
        close_connection(instr)
    if camera is not None:
        disconnect_camera(camera)
    cv2.destroyAllWindows()


# ==============================================================================
# PAIR SUBTRACTION SWEEP
# ==============================================================================

def frequency_sweep_allied_vision(
    start_freq:      float,
    end_freq:        float,
    step:            float,
    n_averages:      int,
    exposure_us:     float,
    gain:            float,
    output_dir:      str,
    waveform:        str   = "sine",
    amplitude:       float = 1.0,
    offset:          float = 0.0,
    warmup_frames:   int   = 10,
    channel:         int   = 1,
    skip_live_feed:  bool  = False,
    gain_factor:     float = 1,
    stop_check=None,
) -> dict | None:
    """
    Run a full ESPI pair-subtraction sweep using an Allied Vision camera.

    At each frequency two frames are grabbed back-to-back and subtracted.
    This is repeated n_averages times and the results are averaged to reduce noise.

    HOW IT WORKS:
      1.  Validate the input parameters.
      2.  Connect to the signal generator and Allied Vision camera.
      3.  Open a live feed — aim the camera and press 'e' to continue.
      4.  Discard warmup frames so the sensor has fully settled.
      5.  Lock exposure and gain so they do not change during the sweep.
      6.  Configure and enable the signal generator.
      7.  Save session metadata to a JSON file.
      8.  Loop through each frequency:
            a. Set the signal generator to the target frequency.
            b. Wait SETTLE_TIME_S seconds (with live feed visible).
            c. Grab n_averages pairs of frames and subtract each pair.
            d. Average all the difference images.
            e. Save a raw PNG and a contrast-amplified PNG.
      9.  Turn off the signal generator and disconnect all devices.
      10. Return { frequency_hz: averaged_difference_image }.

    Args:
        start_freq    : first frequency to test, in Hz
        end_freq      : last frequency to test, in Hz
        step          : frequency increment per step, in Hz
        n_averages    : how many frame pairs to grab and average at each frequency
        exposure_us   : camera exposure in MICROSECONDS (10000 = 10 ms)
        gain          : camera gain in dB (0.0 = no amplification)
        output_dir    : folder where images will be saved (created if missing)
        waveform      : signal shape, e.g. "sine" or "square"
        amplitude     : peak-to-peak voltage in Vpp
        offset        : signal generator DC offset, in Volts. Clamped by
                        configure_channel() so the waveform's peaks stay
                        within the +/-10V rail. Defaults to 0.0.
        warmup_frames : frames to discard after connecting the camera
        channel       : signal generator output channel, 1 or 2
        gain_factor   : multiplier applied to each difference image, before
                        averaging, with cv2.convertScaleAbs (saturates at 255
                        instead of wrapping around). Baked into the saved
                        "espi_av_raw" file itself, the same as every other
                        camera in this project. Defaults to 1 (no amplification).
        stop_check    : optional callable, checked once at the start of every
                        frequency before any signal generator or camera command
                        for that frequency is issued. If it returns True, the
                        sweep stops there — clean-up still runs normally, and
                        whatever frequencies were already measured are still
                        returned. Left as None (the default), the sweep always
                        runs every frequency to completion.

    Returns:
        dict of { frequency_hz: averaged_image } if the sweep ran. May contain
        fewer entries than requested if stop_check ended the sweep early.
        None if a device could not be connected or a parameter was invalid.
    """
    if not _validate_sweep_params(start_freq, end_freq, step,
                                   n_averages, exposure_us, amplitude, channel):
        return None

    # Build the list of frequencies to test.
    # round() avoids floating-point drift in long sweeps (e.g. 0.1 + 0.1 + 0.1
    # is not exactly 0.3 in binary floating point).
    n_steps     = math.floor((end_freq - start_freq) / step + 1e-9)
    frequencies = [round(start_freq + i * step, 6) for i in range(n_steps + 1)]

    instr              = None
    camera             = None
    results            = {}
    failed_frequencies = []

    try:
        # ---- Connect devices ----
        instr, camera, sg_identity = _connect_devices(channel)
        if instr is None:
            return None

        # ---- Live feed — let the user aim the camera ----
        if not skip_live_feed:
            print("\nOpening live feed — aim the camera at the plate, then press 'e'.")
            show_live_feed_from_camera(camera)

        # ---- Lock camera settings ----
        actual_exposure, actual_gain = _lock_camera_settings(
            camera, exposure_us, gain, warmup_frames
        )

        # ---- Turn on signal generator ----
        active_waveform = _configure_signal_generator(
            instr, waveform, start_freq, amplitude, channel, offset=offset
        )
        if active_waveform is None:
            return None

        # ---- Save metadata ----
        cam_info = get_camera_info(camera)
        metadata = _build_metadata(
            "pair", cam_info, sg_identity,
            start_freq, end_freq, step, n_averages,
            active_waveform, amplitude, channel,
            exposure_us, actual_exposure, gain, actual_gain, frequencies,
        )
        _save_metadata(metadata, output_dir)
        save_session_log(cam_info, output_dir)

        # ---- Frequency sweep ----
        sweep_start = time.time()
        print(f"\nStarting sweep: {len(frequencies)} frequency step(s), "
              f"{n_averages} pair(s) each.\n")

        for idx, freq in enumerate(frequencies):
            elapsed = time.time() - sweep_start
            print(f"[{idx + 1}/{len(frequencies)}]  {freq:.1f} Hz  "
                  f"(elapsed: {elapsed:.0f}s)")

            # Checked before any hardware command for this frequency is
            # issued, so stopping here never interrupts an in-progress
            # settle or frame grab.
            if stop_check is not None and stop_check():
                print("  [STOPPED] Sweep stopped by user request.")
                break

            # Move the signal generator to this frequency.
            result = set_frequency(instr, freq, channel=channel,
                                   waveform=active_waveform)
            if result is None:
                print(f"  [SKIP] Could not set {freq:.1f} Hz.")
                failed_frequencies.append(freq)
                continue

            # Wait for the plate to reach steady-state vibration at this frequency.
            print(f"  Settling ({SETTLE_TIME_S}s)...")
            _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

            # Grab n_averages pairs of frames and subtract each pair.
            difference_images = []
            for pair_num in range(n_averages):
                pair = grab_n_frames(camera, 2, max_retries=MAX_GRAB_RETRIES)

                if len(pair) < 2:
                    print(f"  [WARNING] Only {len(pair)}/2 frames arrived "
                          f"for pair {pair_num + 1}/{n_averages} — skipping.")
                    continue

                diff = substract_frames(pair[0], pair[1])
                if diff is not None:
                    difference_images.append(cv2.convertScaleAbs(diff, alpha=gain_factor))

            if not difference_images:
                print(f"  [SKIP] No valid frame pairs at {freq:.1f} Hz.")
                failed_frequencies.append(freq)
                continue

            # Average all the difference images to reduce noise.
            print(f"  Averaging {len(difference_images)}/{n_averages} pair(s)...")
            averaged = average_img(difference_images)
            if averaged is None:
                failed_frequencies.append(freq)
                continue

            # "espi_av_raw" is already scaled by gain_factor (see docstring);
            # it is not the untouched camera data.
            saved_raw = save_image(averaged, output_dir=output_dir,
                                   frequency_hz=freq, exposure_us=exposure_us,
                                   step="espi_av_raw")
            if saved_raw:
                print(f"  Saved (raw):       {os.path.basename(saved_raw)}")

            results[freq] = averaged

            # Show the gain_factor-scaled result as a quick visual check.
            # .copy() because cv2.putText draws in place, and averaged is also
            # what got stored in results[freq] and saved to disk above.
            disp = averaged.copy()
            cv2.putText(disp, f"Last: {freq:g} Hz", (10, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA)
            cv2.imshow("ESPI Sweep — Last Result", disp)
            cv2.waitKey(1)

    except KeyboardInterrupt:
        print("\n\n[Interrupted] Sweep stopped by user — cleaning up...")

    except Exception:
        # Print the full traceback so the exact line that failed is visible.
        # Then re-raise so the caller knows an error occurred.
        print("\n[ERROR] Unexpected error during sweep:")
        traceback.print_exc()
        raise

    finally:
        _cleanup(instr, camera, channel)

    _print_sweep_summary(results, failed_frequencies, len(frequencies), output_dir)
    return results or None


# ==============================================================================
# REFERENCE SUBTRACTION SWEEP
# ==============================================================================

def reference_frequency_sweep_allied_vision(
    start_freq:      float,
    end_freq:        float,
    step:            float,
    n_averages:      int,
    exposure_us:     float,
    gain:            float,
    output_dir:      str,
    waveform:        str   = "sine",
    amplitude:       float = 1.0,
    offset:          float = 0.0,
    warmup_frames:   int   = 10,
    channel:         int   = 1,
    skip_live_feed:  bool  = False,
    gain_factor:     float = 1,
    stop_check=None,
) -> dict | None:
    """
    Run an ESPI reference-subtraction sweep using an Allied Vision camera.

    One frame is captured with the plate at rest (signal generator OFF).
    Every measurement frame is then subtracted from that fixed reference.

    This is better than pair subtraction when the plate moves slowly, because
    consecutive frames look almost identical and their difference is mostly noise.
    Comparing against a truly stationary baseline gives a cleaner result.

    Args: same as frequency_sweep_allied_vision() above, including stop_check.

    Returns:
        dict of { frequency_hz: averaged_image } if the sweep ran. May contain
        fewer entries than requested if stop_check ended the sweep early.
        None if a device could not be connected or a parameter was invalid.
    """
    if not _validate_sweep_params(start_freq, end_freq, step,
                                   n_averages, exposure_us, amplitude, channel):
        return None

    n_steps     = math.floor((end_freq - start_freq) / step + 1e-9)
    frequencies = [round(start_freq + i * step, 6) for i in range(n_steps + 1)]

    instr              = None
    camera             = None
    results            = {}
    failed_frequencies = []

    try:
        # ---- Connect devices ----
        instr, camera, sg_identity = _connect_devices(channel)
        if instr is None:
            return None

        # ---- Live feed ----
        if not skip_live_feed:
            print("\nOpening live feed — aim the camera at the plate, then press 'e'.")
            show_live_feed_from_camera(camera)

        # ---- Lock camera settings ----
        actual_exposure, actual_gain = _lock_camera_settings(
            camera, exposure_us, gain, warmup_frames
        )

        # ---- Reference frame (signal generator must be OFF at this point) ----
        print("\nCapturing reference frame — plate at rest, signal generator OFF...")
        ref_frames = grab_n_frames(camera, n=3, max_retries=MAX_GRAB_RETRIES)
        if not ref_frames:
            print("[ERROR] Could not capture a reference frame. Aborting.")
            return None

        # Average three frames for the reference to reduce its own noise.
        reference = average_img(ref_frames)
        if reference is None:
            print("[ERROR] Reference frame averaging failed. Aborting.")
            return None
        print(f"  Reference captured — shape: {reference.shape}")

        # ---- Turn on signal generator ----
        active_waveform = _configure_signal_generator(
            instr, waveform, start_freq, amplitude, channel, offset=offset
        )
        if active_waveform is None:
            return None

        # ---- Save metadata ----
        cam_info = get_camera_info(camera)
        metadata = _build_metadata(
            "reference", cam_info, sg_identity,
            start_freq, end_freq, step, n_averages,
            active_waveform, amplitude, channel,
            exposure_us, actual_exposure, gain, actual_gain, frequencies,
        )
        _save_metadata(metadata, output_dir)
        save_session_log(cam_info, output_dir)

        # ---- Frequency sweep ----
        sweep_start = time.time()
        print(f"\nStarting reference sweep: {len(frequencies)} step(s), "
              f"{n_averages} frame(s) each.\n")

        for idx, freq in enumerate(frequencies):
            elapsed = time.time() - sweep_start
            print(f"[{idx + 1}/{len(frequencies)}]  {freq:.1f} Hz  "
                  f"(elapsed: {elapsed:.0f}s)")

            # Checked before any hardware command for this frequency is
            # issued, so stopping here never interrupts an in-progress
            # settle or frame grab.
            if stop_check is not None and stop_check():
                print("  [STOPPED] Sweep stopped by user request.")
                break

            result = set_frequency(instr, freq, channel=channel,
                                   waveform=active_waveform)
            if result is None:
                print(f"  [SKIP] Could not set {freq:.1f} Hz.")
                failed_frequencies.append(freq)
                continue

            print(f"  Settling ({SETTLE_TIME_S}s)...")
            _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

            # Grab n_averages frames and subtract each from the reference.
            frames = grab_n_frames(camera, n_averages, max_retries=MAX_GRAB_RETRIES)

            difference_images = []
            for frame in frames:
                diff = substract_frames(reference, frame)
                if diff is not None:
                    difference_images.append(cv2.convertScaleAbs(diff, alpha=gain_factor))

            if not difference_images:
                print(f"  [SKIP] No valid frames at {freq:.1f} Hz.")
                failed_frequencies.append(freq)
                continue

            print(f"  Averaging {len(difference_images)}/{n_averages} frame(s)...")
            averaged = average_img(difference_images)
            if averaged is None:
                failed_frequencies.append(freq)
                continue

            # "espi_av_ref_raw" is already scaled by gain_factor (see docstring);
            # it is not the untouched camera data.
            saved_raw = save_image(averaged, output_dir=output_dir,
                                   frequency_hz=freq, exposure_us=exposure_us,
                                   step="espi_av_ref_raw")
            if saved_raw:
                print(f"  Saved (raw):       {os.path.basename(saved_raw)}")

            results[freq] = averaged

            # .copy() because cv2.putText draws in place, and averaged is also
            # what got stored in results[freq] and saved to disk above.
            disp = averaged.copy()
            cv2.putText(disp, f"Last: {freq:g} Hz", (10, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA)
            cv2.imshow("ESPI Sweep — Last Result", disp)
            cv2.waitKey(1)

    except KeyboardInterrupt:
        print("\n\n[Interrupted] Sweep stopped by user — cleaning up...")

    except Exception:
        print("\n[ERROR] Unexpected error during sweep:")
        traceback.print_exc()
        raise

    finally:
        _cleanup(instr, camera, channel)

    _print_sweep_summary(results, failed_frequencies, len(frequencies), output_dir)
    return results or None


# ==============================================================================
# RUN DIRECTLY
# ==============================================================================
if __name__ == "__main__":
    print("Choose subtraction mode:")
    print("  1 — Pair subtraction       (two frames per frequency, subtract each other)")
    print("  2 — Reference subtraction  (one resting baseline, compare all frames to it)")
    mode = input("Enter 1 or 2 [default 1]: ").strip() or "1"

    sweep_params = dict(
        start_freq    = 100,
        end_freq      = 1000,
        step          = 100,
        n_averages    = 5,
        exposure_us   = 10000,   # 10 ms — adjust if image is too dark or too bright
        gain          = 0.0,
        output_dir    = "output",
        waveform      = "sine",
        amplitude     = 1.0,
        warmup_frames = 10,
        channel       = 1,
    )

    if mode == "2":
        results = reference_frequency_sweep_allied_vision(**sweep_params)
    else:
        if mode != "1":
            print("Unrecognised input — defaulting to pair subtraction.")
        results = frequency_sweep_allied_vision(**sweep_params)

    if results:
        print(f"\nFrequencies measured: {sorted(results.keys())}")
    else:
        print("\nNo results collected.")
