"""
complete_pipeline_inclusive.py
Author: Patrick Mulikuza

The universal version of complete_pipeline.py.
Works with ANY camera your computer can see — not just Basler cameras.

HOW THIS SCRIPT WORKS
----------------------
This script runs three phases in order:

  Phase 1 — Live feed:
    A real-time camera window opens so you can aim, focus, and frame the
    plate before the experiment begins.  Press 'e' when you are satisfied
    with what you see.

  Phase 2 — Frequency sweep:
    The signal generator steps through every frequency from start_freq to
    end_freq.  At each frequency:
      a. The signal generator is updated to that frequency.
      b. The script waits SETTLE_TIME_S seconds for the plate to stop
         transitioning and settle into steady-state vibration.
      c. n_averages pairs of frames are captured from the camera.
      d. Each pair is subtracted to reveal the speckle shift caused by
         the vibration at that frequency.
      e. All difference images at that frequency are averaged together
         to reduce random noise.
      f. Two images are saved: a raw difference (for later analysis) and
         a contrast-amplified version (easier to look at on screen).

  Phase 3 — Clean up:
    The signal generator output is turned off and both devices are
    disconnected cleanly — this happens even if the sweep crashes or you
    press Ctrl+C mid-run.

HOW TO USE
----------
Just run this file directly:

    python3 complete_pipeline_inclusive.py

Or import the function and call it from another script:

    from complete_pipeline_inclusive import frequency_sweep_inclusive
    results = frequency_sweep_inclusive(100, 1000, 100, 5, -6, 0.0, "output")

HOW TO CHANGE SETTINGS
-----------------------
Edit the values in the if __name__ == "__main__" block at the bottom.

DEPENDENCIES
------------
    pip install opencv-python matplotlib numpy pyvisa pyvisa-py
"""

import cv2
import json
import math
import os
import time
from datetime import datetime

from signal_generator_control import *
from camera_control_inclusive import *


# How many seconds to wait after changing frequency before capturing frames.
# The plate needs this time to stop ringing and settle into a clean, steady
# vibration at the new frequency.  If your mode-shape images look smeared,
# increase this value.
SETTLE_TIME_S = 2.0

# How many times to retry a frame grab if the camera returns nothing.
# USB cameras occasionally drop a frame when the system is busy — retrying
# gives a second chance without aborting the whole experiment.
MAX_GRAB_RETRIES = 3


def _settle_with_live_feed(camera, seconds, freq):
    """
    Replace time.sleep() during settling: grab and show live frames for
    `seconds` seconds so the user can watch the plate while it settles.
    """
    end = time.time() + seconds
    while time.time() < end:
        frame = grab_single_frame(camera)
        if frame is not None:
            display = frame.copy()
            remaining = max(0.0, end - time.time())
            cv2.putText(
                display,
                f"{freq:.0f} Hz  |  Settling: {remaining:.1f}s",
                (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA,
            )
            cv2.imshow("ESPI Sweep — Live Feed", display)
        cv2.waitKey(1)


def frequency_sweep_inclusive(
    start_freq,
    end_freq,
    step,
    n_averages,
    exposure,
    gain,
    output_dir,
    waveform       = "sine",
    amplitude      = 1.0,
    warmup_frames  = 10,
    channel        = 1,
    skip_live_feed = False,
):
    """
    Run a full ESPI frequency sweep using any OpenCV-compatible camera.

    Before the sweep begins, a live camera feed opens so you can aim and
    align the camera.  Press 'e' to close the feed and start the sweep.

    HOW IT WORKS STEP BY STEP:
      1.  Check that all the input values make sense.
      2.  Connect to the signal generator and the camera.
      3.  Open a live feed so you can aim the camera — press 'e' when ready.
      4.  Discard warmup frames so the sensor brightness has stabilised.
      5.  Lock the camera exposure and gain so brightness stays constant.
      6.  Turn on the signal generator at the starting frequency.
      7.  Save a session metadata file (JSON) recording all experiment settings.
      8.  Loop through every frequency from start_freq to end_freq:
            a. Set the signal generator to the current frequency.
            b. Wait SETTLE_TIME_S seconds for the plate to settle.
            c. Grab n_averages pairs of frames (with automatic retry).
            d. Subtract each pair to get a difference image.
            e. Average all difference images to reduce noise.
            f. Save a raw PNG and a contrast-amplified PNG to disk.
      9.  Turn off the signal generator and disconnect everything.
     10.  Print a summary of how many frequencies succeeded or failed.
     11.  Return a dictionary of { frequency → averaged image }.

    GUARANTEED CLEAN-UP:
      Even if the sweep crashes halfway through, or you press Ctrl+C to stop
      early, the signal generator output is always turned off and the camera
      is always released.  You should never need to unplug anything to recover.

    WHY TWO FRAMES PER PAIR?
      ESPI works by comparing two frames of the same vibrating plate captured
      slightly apart in time.  The plate moves a tiny bit between the two
      frames and subtracting them shows exactly where it moved.  Averaging
      many such pairs cancels out random noise, making the pattern cleaner.

    Args:
        start_freq    (float) : First frequency to test, in Hz.
        end_freq      (float) : Last frequency to test, in Hz.
        step          (float) : How much to increase the frequency each step.
        n_averages    (int)   : Frame pairs to capture at each frequency.
                                More pairs = less noise, slower sweep.
        exposure      (float) : Camera exposure in OpenCV log₂ scale.
                                -1 ≈ bright,  -6 ≈ 15 ms,  -11 ≈ dark.
        gain          (float) : Camera gain.  0.0 = no extra amplification.
        output_dir    (str)   : Folder where images will be saved.
                                Created automatically if it doesn't exist.
        waveform      (str)   : Signal shape: "sine", "square", "ramp", etc.
                                Defaults to "sine" — the most common choice
                                for acoustic/mechanical vibration.
        amplitude     (float) : Peak-to-peak output voltage in Vpp.
                                Start low (1.0 Vpp) and increase if needed.
                                The SDG1015 maximum is 20 Vpp.
        warmup_frames (int)   : Frames to discard after opening the camera and
                                after locking exposure.  Lets the sensor settle.
                                Defaults to 10.
        channel       (int)   : Which signal generator channel to use (1 or 2).
                                Defaults to 1.

    Returns:
        dict : { frequency_hz: averaged_difference_image } for every frequency
               that produced a valid result.  May be empty if nothing worked.
        None : if the signal generator or camera could not be connected, or if
               the initial signal generator configuration failed.
    """

    # ==========================================================================
    # STEP 1 — CHECK THAT THE INPUTS MAKE SENSE
    # ==========================================================================
    # Better to catch a typo here — before any hardware is touched — than to
    # have the script fail halfway through a sweep and leave the signal
    # generator outputting a signal with the camera still locked.

    if start_freq <= 0:
        print(f"[ERROR] start_freq must be a positive number (got {start_freq}).")
        return None
    if end_freq < start_freq:
        print(f"[ERROR] end_freq ({end_freq}) must be >= start_freq ({start_freq}).")
        return None
    if step <= 0:
        print(f"[ERROR] step must be a positive number (got {step}).")
        return None
    if n_averages < 1:
        print(f"[ERROR] n_averages must be at least 1 (got {n_averages}).")
        return None
    if amplitude <= 0:
        print(f"[ERROR] amplitude must be positive (got {amplitude} Vpp).")
        return None
    if channel not in (1, 2):
        print(f"[ERROR] channel must be 1 or 2 (got {channel}).")
        return None

    # Pre-compute the full frequency list here so we can use it in the
    # summary print even if the sweep is interrupted early.
    #
    # We compute each frequency as start + i*step rather than adding step
    # repeatedly.  Repeatedly adding floating-point numbers accumulates tiny
    # rounding errors that can push the last frequency just above end_freq
    # and accidentally skip it.  Computing from scratch each time avoids that.
    n_steps     = math.floor((end_freq - start_freq) / step + 1e-9)
    frequencies = [start_freq + i * step for i in range(n_steps + 1)]

    # ==========================================================================
    # INITIALISE TRACKING VARIABLES
    # ==========================================================================
    # These are set to None / empty now so that the finally block can safely
    # check them regardless of how far the setup got before something failed.

    instr              = None
    camera             = None
    results            = {}
    failed_frequencies = []

    try:
        # ======================================================================
        # STEP 2 — CONNECT THE SIGNAL GENERATOR AND CAMERA
        # ======================================================================
        # We connect both devices before doing anything else.  If either one
        # is missing, the script stops immediately with a clear message instead
        # of failing silently mid-sweep.

        print("Connecting to signal generator...")
        instr = open_connection(index=0)
        if instr is None:
            print("[ERROR] Signal generator not found.  "
                  "Check the USB cable and try again.")
            return None

        sg_identity = get_identity(instr)
        print(f"Signal generator identified: {sg_identity}")

        print("\nConnecting to camera...")
        camera = connect_camera(camera_index=0)
        if camera is None:
            print("[ERROR] Camera not found.  "
                  "Check the USB cable and try again.")
            return None

        # ======================================================================
        # STEP 3 — LIVE FEED: AIM THE CAMERA
        # ======================================================================
        # Open a live window so you can physically aim the camera at the plate,
        # check the focus, and make sure the plate fills the frame nicely.
        # Press 'e' on your keyboard when you are happy with the view.
        #
        # We use show_live_feed_from_camera() here (not show_live_camera())
        # because it reuses the camera handle we already opened.  Opening a
        # second connection to the same camera simultaneously can cause a
        # conflict on some operating systems.

        if not skip_live_feed:
            print("\nOpening live feed — aim the camera at the plate, then press 'e'.")
            show_live_feed_from_camera(camera)

        # ======================================================================
        # STEP 4 — DISCARD WARMUP FRAMES
        # ======================================================================
        # The camera buffer may still hold a few stale frames from the live
        # feed.  Discarding them here ensures the sensor is delivering fresh,
        # stable frames before we lock the exposure settings.

        discard_warmup_frames(camera, n=warmup_frames)

        # ======================================================================
        # STEP 5 — LOCK CAMERA SETTINGS
        # ======================================================================
        # Fix the exposure and gain so they stay exactly the same for every
        # frame in the sweep.  If we left these on automatic, the camera might
        # change brightness between frames, which would corrupt the ESPI
        # subtraction and produce garbage fringe patterns.

        print("\nLocking camera settings...")
        actual_exposure = set_exposure_manual(camera, exposure)
        actual_gain     = set_gain_manual(camera, gain)

        # If the camera couldn't honour the exact value we requested, warn the
        # user now so they can decide whether to adjust the setting.
        if actual_exposure is not None and abs(actual_exposure - exposure) > 1:
            print(f"[WARNING] Camera applied exposure {actual_exposure} "
                  f"instead of the requested {exposure}.  "
                  f"Image brightness may differ from what you expect.")

        # Discard a few more frames so the new exposure setting is fully in
        # effect before we start capturing measurement data.
        discard_warmup_frames(camera, n=5)

        # ======================================================================
        # STEP 6 — CONFIGURE THE SIGNAL GENERATOR AND TURN OUTPUT ON
        # ======================================================================
        # configure_channel() sets waveform shape, frequency, amplitude, and
        # DC offset all in one call, then switches the output ON.
        # We start at start_freq; the loop below will update it each iteration.
        #
        # sg_settings stores the values that were actually applied — these may
        # differ slightly from what we requested because the hardware rounds
        # to its internal resolution.

        print(f"\nConfiguring signal generator: {waveform}, {start_freq} Hz, "
              f"{amplitude} Vpp, channel {channel}...")
        sg_settings = configure_channel(
            instr,
            waveform  = waveform,
            frequency = start_freq,
            amplitude = amplitude,
            offset    = 0.0,
            channel   = channel,
        )

        # Make sure the output actually turned on before we start the sweep.
        if sg_settings.get("channel output") is None:
            print(f"[ERROR] Could not turn on channel {channel} output.  "
                  f"Check the signal generator and try again.")
            return None

        active_waveform = sg_settings.get("waveform") or waveform

        # ======================================================================
        # STEP 7 — CREATE OUTPUT FOLDER AND SAVE SESSION METADATA
        # ======================================================================
        # We save a JSON file alongside the images so that anyone looking at
        # the results later knows exactly what settings were used.  This is
        # essential for reproducing the experiment or comparing results from
        # different sessions.

        os.makedirs(output_dir, exist_ok=True)

        cam_info = get_camera_info(camera)
        metadata = {
            "experiment":         "ESPI frequency sweep",
            "date":               datetime.now().strftime("%Y-%m-%d"),
            "time":               datetime.now().strftime("%H:%M:%S"),
            "start_freq_hz":      start_freq,
            "end_freq_hz":        end_freq,
            "step_hz":            step,
            "n_averages":         n_averages,
            "waveform":           active_waveform,
            "amplitude_vpp":      amplitude,
            "channel":            channel,
            "settle_time_s":      SETTLE_TIME_S,
            "exposure_requested": exposure,
            "exposure_actual":    actual_exposure,
            "gain_requested":     gain,
            "gain_actual":        actual_gain,
            "camera_width_px":    cam_info["width"],
            "camera_height_px":   cam_info["height"],
            "camera_fps":         cam_info["fps"],
            "sg_identity":        sg_identity,
            "n_frequencies":      len(frequencies),
            "frequencies_hz":     frequencies,
        }

        meta_path = os.path.join(output_dir, "session_metadata.json")
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Session metadata saved: {meta_path}")

        save_session_log(cam_info, output_dir)

        # ======================================================================
        # STEP 8 — FREQUENCY SWEEP LOOP
        # ======================================================================

        sweep_start = time.time()
        print(f"\nStarting sweep: {len(frequencies)} frequency step(s), "
              f"{n_averages} pair(s) each.\n")

        for idx, freq in enumerate(frequencies):

            elapsed = time.time() - sweep_start
            print(f"[{idx + 1}/{len(frequencies)}]  {freq:.1f} Hz  "
                  f"(elapsed: {elapsed:.0f}s)")

            # ------------------------------------------------------------------
            # 8a. Tell the signal generator to switch to this frequency.
            #     We pass the waveform type so the generator uses the right
            #     frequency ceiling (e.g. ramp can't go as high as sine).
            # ------------------------------------------------------------------
            result = set_frequency(
                instr, freq,
                channel  = channel,
                waveform = active_waveform,
            )

            if result is None:
                # set_frequency already printed an error — just move on.
                print(f"  [SKIP] Could not set {freq:.1f} Hz — skipping.")
                failed_frequencies.append(freq)
                continue

            # ------------------------------------------------------------------
            # 8b. Wait for the plate to settle at steady-state vibration.
            #
            #     When the frequency changes, the plate doesn't jump instantly
            #     into the new mode — it rings through a transition first.
            #     Capturing during the transition gives a blurry, smeared image.
            #     SETTLE_TIME_S seconds of waiting lets it reach a stable pattern.
            # ------------------------------------------------------------------
            print(f"  Settling ({SETTLE_TIME_S}s) — watch the live feed window...")
            _settle_with_live_feed(camera, SETTLE_TIME_S, freq)
            print("  Settled.")

            # ------------------------------------------------------------------
            # 8c & 8d. Capture n_averages pairs of frames and subtract each pair.
            #
            #     Two frames are grabbed back-to-back.  In the gap between them
            #     the plate has moved slightly, so subtracting them reveals the
            #     speckle shift caused by vibration at this frequency.
            #
            #     grab_n_frames() automatically retries failed grabs up to
            #     MAX_GRAB_RETRIES times, so occasional USB hiccups don't waste
            #     a whole pair.
            # ------------------------------------------------------------------
            difference_images = []

            for i in range(n_averages):
                pair = grab_n_frames(camera, 2, max_retries=MAX_GRAB_RETRIES)

                if len(pair) < 2:
                    print(f"  [WARNING] Only got {len(pair)} frame(s) for pair "
                          f"{i + 1}/{n_averages} — skipping this pair.")
                    continue

                diff = substract_frames(pair[0], pair[1])
                if diff is None:
                    # Shape mismatch — shouldn't happen normally, but better to
                    # skip than to crash and leave the signal generator running.
                    print(f"  [WARNING] Frame shape mismatch in pair "
                          f"{i + 1}/{n_averages} — skipping.")
                    continue

                difference_images.append(diff)

            # ------------------------------------------------------------------
            # 8e. Average all difference images together.
            #
            #     Each individual difference image contains random speckle noise
            #     on top of the real vibration pattern.  Averaging many of them
            #     cancels the random noise while keeping the real pattern, giving
            #     a much cleaner result.
            # ------------------------------------------------------------------
            if len(difference_images) == 0:
                print(f"  [SKIP] No valid pairs at {freq:.1f} Hz — skipping.")
                failed_frequencies.append(freq)
                continue

            print(f"  Averaging {len(difference_images)}/{n_averages} pair(s)...")
            averaged = average_img(difference_images)
            if averaged is None:
                print(f"  [SKIP] Averaging failed at {freq:.1f} Hz — skipping.")
                failed_frequencies.append(freq)
                continue

            # ------------------------------------------------------------------
            # 8f. Save images to disk.
            #
            #     We save two versions:
            #       "espi_raw"       — the averaged difference straight from the
            #                          camera.  Use this for quantitative analysis.
            #       "espi_amplified" — contrast-stretched so the fringe pattern
            #                          fills the full 0-255 range.  Use this to
            #                          visually inspect the mode shape on screen.
            # ------------------------------------------------------------------
            saved_raw = save_image(
                averaged,
                output_dir   = output_dir,
                frequency_hz = freq,
                exposure_us  = exposure,
                step         = "espi_raw",
            )
            if saved_raw:
                print(f"  Saved (raw):       {os.path.basename(saved_raw)}")

            amplified = amplify_difference(averaged)

            results[freq] = averaged

            disp = amplified.copy()
            cv2.putText(disp, f"Last: {freq:g} Hz", (10, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA)
            cv2.imshow("ESPI Sweep — Last Result", disp)
            cv2.waitKey(1)

        # End of sweep loop — fall through to finally for clean-up.

    except KeyboardInterrupt:
        # The user pressed Ctrl+C.  We stop the loop gracefully and let the
        # finally block below handle disconnecting the hardware.
        print("\n\n[Interrupted] Sweep stopped early — cleaning up...")

    except Exception as e:
        # Something unexpected went wrong (e.g. VISA timeout, OpenCV error).
        # Print the error and re-raise it so the caller can see the full
        # traceback, but still let the finally block clean up hardware first.
        print(f"\n[ERROR] Unexpected error during sweep: {e}")
        raise

    finally:
        # ======================================================================
        # STEP 9 — GUARANTEED CLEAN-UP
        # ======================================================================
        # This block runs NO MATTER WHAT — normal finish, Ctrl+C, or crash.
        # Leaving the signal generator outputting a signal when you walk away
        # is wasteful and potentially damages the speaker/shaker.  Leaving the
        # camera open can prevent the next connection attempt from succeeding.

        print("\n--- Disconnecting devices ---")

        if instr is not None:
            try:
                turn_off_output(instr, channel=channel)
            except Exception:
                # If we can't turn off output cleanly (e.g. USB dropped),
                # just move on — closing the connection also stops the output.
                pass
            close_connection(instr)

        if camera is not None:
            disconnect_camera(camera)
        cv2.destroyAllWindows()

    # ==========================================================================
    # STEP 10 — PRINT A SUMMARY
    # ==========================================================================
    total      = len(frequencies)
    succeeded  = len(results)
    n_failed   = len(failed_frequencies)

    print(f"\n{'='*50}")
    print(f"Sweep complete.")
    print(f"  Succeeded : {succeeded}/{total} frequencies")
    if n_failed:
        print(f"  Failed    : {n_failed} — {[f'{f:.1f} Hz' for f in failed_frequencies]}")
    print(f"  Images in : {os.path.abspath(output_dir)}")
    print(f"{'='*50}")

    # Return the results even if the sweep was interrupted — whatever was
    # collected before the stop is still useful data.
    return results or None


def reference_frequency_sweep_inclusive(
    start_freq,
    end_freq,
    step,
    n_averages,
    exposure,
    gain,
    output_dir,
    waveform       = "sine",
    amplitude      = 1.0,
    warmup_frames  = 10,
    channel        = 1,
    skip_live_feed = False,
):
    """
    Reference-based ESPI frequency sweep using any OpenCV-compatible camera.

    HOW THIS DIFFERS FROM frequency_sweep_inclusive():
      frequency_sweep_inclusive() subtracts consecutive frame pairs captured
      at the same frequency (pair subtraction).  This function captures one
      reference frame BEFORE vibration starts — with the signal generator still
      OFF — and then at every frequency subtracts every individual grabbed frame
      from that fixed reference image.

      Reference subtraction reveals the cumulative displacement from the resting
      state rather than the instantaneous change between two vibrating frames.
      This can make slow or low-amplitude deformations more visible.

    HOW IT WORKS STEP BY STEP:
      1.  Validate all input parameters.
      2.  Connect to the signal generator and camera.
      3.  Open a live feed so you can aim the camera — press 'e' when ready.
      4.  Discard warmup frames so the sensor has stabilised.
      5.  Lock camera exposure and gain.
      6.  Capture one reference frame (signal generator still OFF).
      7.  Turn on the signal generator at start_freq.
      8.  Save session metadata (JSON).
      9.  Loop through every frequency:
            a. Set signal generator to current frequency.
            b. Wait SETTLE_TIME_S for the plate to settle.
            c. Grab n_averages individual frames (with retry).
            d. Subtract each frame from the reference.
            e. Average all difference images.
            f. Save a raw PNG and a contrast-amplified PNG.
     10.  Turn off the signal generator and disconnect everything.
     11.  Print a sweep summary and return results.

    Args:
        start_freq    (float) : First frequency to test, in Hz.
        end_freq      (float) : Last frequency to test, in Hz.
        step          (float) : Frequency increment per step, in Hz.
        n_averages    (int)   : Frames to grab at each frequency.
        exposure      (float) : OpenCV log₂ exposure value (-6 ≈ 15 ms).
        gain          (float) : Camera gain. 0.0 = no amplification.
        output_dir    (str)   : Folder where images will be saved.
        waveform      (str)   : Signal shape ("sine", "square", etc.).
        amplitude     (float) : Peak-to-peak output voltage in Vpp.
        warmup_frames (int)   : Frames to discard while sensor settles.
        channel       (int)   : Signal generator channel (1 or 2).

    Returns:
        dict : { frequency_hz: averaged_difference_image } for each successful
               frequency.  May be empty if nothing worked.
        None : if a device could not be connected or configured.
    """

    # ==========================================================================
    # STEP 1 — VALIDATE INPUTS
    # ==========================================================================
    if start_freq <= 0:
        print(f"[ERROR] start_freq must be positive (got {start_freq}).")
        return None
    if end_freq < start_freq:
        print(f"[ERROR] end_freq ({end_freq}) must be >= start_freq ({start_freq}).")
        return None
    if step <= 0:
        print(f"[ERROR] step must be positive (got {step}).")
        return None
    if n_averages < 1:
        print(f"[ERROR] n_averages must be at least 1 (got {n_averages}).")
        return None
    if amplitude <= 0:
        print(f"[ERROR] amplitude must be positive (got {amplitude} Vpp).")
        return None
    if channel not in (1, 2):
        print(f"[ERROR] channel must be 1 or 2 (got {channel}).")
        return None

    n_steps     = math.floor((end_freq - start_freq) / step + 1e-9)
    frequencies = [start_freq + i * step for i in range(n_steps + 1)]

    # ==========================================================================
    # INITIALISE TRACKING VARIABLES
    # ==========================================================================
    instr              = None
    camera             = None
    results            = {}
    failed_frequencies = []

    try:
        # ======================================================================
        # STEP 2 — CONNECT DEVICES
        # ======================================================================
        print("Connecting to signal generator...")
        instr = open_connection(index=0)
        if instr is None:
            print("[ERROR] Signal generator not found. Check the USB cable.")
            return None

        sg_identity = get_identity(instr)
        print(f"Signal generator identified: {sg_identity}")

        print("\nConnecting to camera...")
        camera = connect_camera(camera_index=0)
        if camera is None:
            print("[ERROR] Camera not found. Check the USB cable.")
            return None

        # ======================================================================
        # STEP 3 — LIVE FEED: AIM THE CAMERA
        # ======================================================================
        if not skip_live_feed:
            print("\nOpening live feed — aim the camera at the plate, then press 'e'.")
            show_live_feed_from_camera(camera)

        # ======================================================================
        # STEP 4 — DISCARD WARMUP FRAMES
        # ======================================================================
        discard_warmup_frames(camera, n=warmup_frames)

        # ======================================================================
        # STEP 5 — LOCK CAMERA SETTINGS
        # ======================================================================
        print("\nLocking camera settings...")
        actual_exposure = set_exposure_manual(camera, exposure)
        actual_gain     = set_gain_manual(camera, gain)

        if actual_exposure is not None and abs(actual_exposure - exposure) > 1:
            print(f"[WARNING] Camera applied exposure {actual_exposure} "
                  f"instead of {exposure}. Brightness may differ from expectation.")

        discard_warmup_frames(camera, n=5)

        # ======================================================================
        # STEP 6 — CAPTURE REFERENCE FRAME (signal generator still OFF)
        # ======================================================================
        # The reference must be captured under the same exposure settings as the
        # measurement frames, but with the plate undisturbed.  Turning on the
        # signal generator afterwards guarantees this ordering.
        print("\nCapturing reference frame (signal generator OFF, plate at rest)...")
        ref_pair = grab_n_frames(camera, 1, max_retries=MAX_GRAB_RETRIES)
        if len(ref_pair) < 1:
            print("[ERROR] Could not capture reference frame. Aborting.")
            return None
        reference = ref_pair[0]
        print("Reference frame captured.")

        # ======================================================================
        # STEP 7 — CONFIGURE SIGNAL GENERATOR AND TURN OUTPUT ON
        # ======================================================================
        print(f"\nConfiguring signal generator: {waveform}, {start_freq} Hz, "
              f"{amplitude} Vpp, channel {channel}...")
        sg_settings = configure_channel(
            instr,
            waveform  = waveform,
            frequency = start_freq,
            amplitude = amplitude,
            offset    = 0.0,
            channel   = channel,
        )

        if sg_settings.get("channel output") is None:
            print(f"[ERROR] Could not turn on channel {channel} output.")
            return None

        active_waveform = sg_settings.get("waveform") or waveform

        # ======================================================================
        # STEP 8 — CREATE OUTPUT FOLDER AND SAVE SESSION METADATA
        # ======================================================================
        os.makedirs(output_dir, exist_ok=True)

        cam_info = get_camera_info(camera)
        metadata = {
            "experiment":         "ESPI reference-subtraction frequency sweep",
            "date":               datetime.now().strftime("%Y-%m-%d"),
            "time":               datetime.now().strftime("%H:%M:%S"),
            "diff_mode":          "reference",
            "start_freq_hz":      start_freq,
            "end_freq_hz":        end_freq,
            "step_hz":            step,
            "n_averages":         n_averages,
            "waveform":           active_waveform,
            "amplitude_vpp":      amplitude,
            "channel":            channel,
            "settle_time_s":      SETTLE_TIME_S,
            "exposure_requested": exposure,
            "exposure_actual":    actual_exposure,
            "gain_requested":     gain,
            "gain_actual":        actual_gain,
            "camera_width_px":    cam_info["width"],
            "camera_height_px":   cam_info["height"],
            "camera_fps":         cam_info["fps"],
            "sg_identity":        sg_identity,
            "n_frequencies":      len(frequencies),
            "frequencies_hz":     frequencies,
        }

        meta_path = os.path.join(output_dir, "session_metadata.json")
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Session metadata saved: {meta_path}")

        save_session_log(cam_info, output_dir)

        # ======================================================================
        # STEP 9 — FREQUENCY SWEEP LOOP
        # ======================================================================
        sweep_start = time.time()
        print(f"\nStarting reference sweep: {len(frequencies)} step(s), "
              f"{n_averages} frame(s) each.\n")

        for idx, freq in enumerate(frequencies):

            elapsed = time.time() - sweep_start
            print(f"[{idx + 1}/{len(frequencies)}]  {freq:.1f} Hz  "
                  f"(elapsed: {elapsed:.0f}s)")

            # 9a. Update signal generator frequency.
            result = set_frequency(instr, freq, channel=channel, waveform=active_waveform)
            if result is None:
                print(f"  [SKIP] Could not set {freq:.1f} Hz — skipping.")
                failed_frequencies.append(freq)
                continue

            # 9b. Wait for the plate to settle.
            print(f"  Settling ({SETTLE_TIME_S}s) — watch the live feed window...")
            _settle_with_live_feed(camera, SETTLE_TIME_S, freq)
            print("  Settled.")

            # 9c & 9d. Grab n_averages individual frames and subtract each from
            #           the reference captured before vibration started.
            difference_images = []
            frames = grab_n_frames(camera, n_averages, max_retries=MAX_GRAB_RETRIES)

            for frame in frames:
                diff = substract_frames(reference, frame)
                if diff is not None:
                    difference_images.append(diff)

            if len(difference_images) == 0:
                print(f"  [SKIP] No valid frames at {freq:.1f} Hz — skipping.")
                failed_frequencies.append(freq)
                continue

            # 9e. Average all difference images to reduce noise.
            print(f"  Averaging {len(difference_images)}/{n_averages} frame(s)...")
            averaged = average_img(difference_images)
            if averaged is None:
                print(f"  [SKIP] Averaging failed at {freq:.1f} Hz — skipping.")
                failed_frequencies.append(freq)
                continue

            # 9f. Save raw and contrast-amplified images.
            saved_raw = save_image(
                averaged,
                output_dir   = output_dir,
                frequency_hz = freq,
                exposure_us  = exposure,
                step         = "espi_ref_raw",
            )
            if saved_raw:
                print(f"  Saved (raw):       {os.path.basename(saved_raw)}")

            amplified = amplify_difference(averaged)

            results[freq] = averaged

            disp = amplified.copy()
            cv2.putText(disp, f"Last: {freq:g} Hz", (10, 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA)
            cv2.imshow("ESPI Sweep — Last Result", disp)
            cv2.waitKey(1)

    except KeyboardInterrupt:
        print("\n\n[Interrupted] Sweep stopped early — cleaning up...")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error during sweep: {e}")
        raise

    finally:
        # ======================================================================
        # STEP 10 — GUARANTEED CLEAN-UP
        # ======================================================================
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

    # ==========================================================================
    # STEP 11 — PRINT SUMMARY
    # ==========================================================================
    total     = len(frequencies)
    succeeded = len(results)
    n_failed  = len(failed_frequencies)

    print(f"\n{'='*50}")
    print(f"Reference sweep complete.")
    print(f"  Succeeded : {succeeded}/{total} frequencies")
    if n_failed:
        print(f"  Failed    : {n_failed} — {[f'{f:.1f} Hz' for f in failed_frequencies]}")
    print(f"  Images in : {os.path.abspath(output_dir)}")
    print(f"{'='*50}")

    return results or None


# ==============================================================================
# RUN DIRECTLY
# ==============================================================================
# This block only runs when you execute this file directly:
#     python3 complete_pipeline_inclusive.py
#
# It does NOT run when you import this file from another script, so it is
# safe to leave the experiment settings here as a reference.
# ==============================================================================
if __name__ == "__main__":

    print("Choose subtraction mode:")
    print("  1 — Pair subtraction       (subtract consecutive frame pairs at each frequency)")
    print("  2 — Reference subtraction  (subtract each frame from a pre-captured resting reference)")
    mode = input("Enter 1 or 2: ").strip()

    sweep_params = dict(
        start_freq    = 100,      # Hz — first frequency to test
        end_freq      = 1000,     # Hz — last frequency to test
        step          = 100,      # Hz — jump between steps (100, 200 ... 1000)
        n_averages    = 5,        # frames per frequency (pairs for mode 1, individual for mode 2)
        exposure      = -6,       # OpenCV exposure: -6 ≈ 15 ms, good starting point
        gain          = 0.0,      # camera gain (0 = no extra amplification)
        output_dir    = "output", # folder where images are saved (auto-created)
        waveform      = "sine",   # signal shape — sine is best for plate vibration
        amplitude     = 1.0,      # Vpp — start low, increase if plate doesn't vibrate
        warmup_frames = 10,       # frames to discard before locking exposure
        channel       = 1,        # signal generator channel (1 or 2)
    )

    if mode == "2":
        print("\nRunning reference subtraction sweep...")
        results = reference_frequency_sweep_inclusive(**sweep_params)
    else:
        if mode != "1":
            print("Unrecognised input — defaulting to pair subtraction.")
        print("\nRunning pair subtraction sweep...")
        results = frequency_sweep_inclusive(**sweep_params)

    if results:
        print(f"\nFrequencies measured: {sorted(results.keys())}")
    else:
        print("\nNo results collected.")
