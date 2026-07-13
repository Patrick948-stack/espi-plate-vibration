"""
complete_pipeline.py
Author: Patrick Mulikuza

Ties the camera and signal generator control together into a single pipeline.

For each frequency between start_freq and end_freq (stepping by `step` Hz),
this script:
  1. Sets the signal generator to that frequency.
  2. Waits SETTLE_TIME_S seconds for the plate to reach steady-state vibration.
  3. Captures n_averages pairs of frames from the camera.
  4. Subtracts each pair to get a difference image.
  5. Averages all the difference images together to reduce noise.
  6. Saves the averaged result to disk as a PNG.

At the end it returns a dictionary so you can do further analysis in the
calling script without having to reload every saved image from disk.

HOW TO USE
----------
    from complete_pipeline import frequency_sweep

    results = frequency_sweep(
        start_freq  = 100,       # Hz — first frequency to test
        end_freq    = 1000,      # Hz — last frequency to test
        step        = 100,       # Hz — how much to increase each iteration
        n_averages  = 5,         # how many frame pairs to average per frequency
        exposure_us = 10000,     # camera exposure time in microseconds (10 ms)
        gain        = 0.0,       # camera gain in dB
        output_dir  = "output",  # folder where PNG images will be saved
    )

    # results is a dict: { frequency_in_Hz: averaged_difference_image, ... }
    # Each value is a numpy array you can pass to show_diff() or further process.

DEPENDENCIES
------------
    pip install pypylon numpy opencv-python pyvisa pyvisa-py
"""

import cv2
import math
import os
import time

# Import every public function from both library files.
# "from X import *" brings in all names listed in their __all__ lists.
from signal_generator_control import *
from camera_control import *


# Seconds to wait after changing frequency before capturing frames.
# The plate needs this time to stop transitioning and reach steady-state
# vibration at the new frequency.  Increase if mode shapes look smeared.
SETTLE_TIME_S = 2.0


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


def frequency_sweep(start_freq, end_freq, step, n_averages, exposure_us, gain, output_dir,
                     gain_factor=1):
    """
    Run a full ESPI frequency sweep and save one averaged difference image per frequency.

    HOW IT WORKS STEP BY STEP:
      1. Connect to the signal generator and camera.
      2. Set the camera exposure and gain so brightness stays constant.
      3. Turn on the signal generator output at start_freq.
      4. Loop through every frequency from start_freq to end_freq:
           a. Update the signal generator to the current frequency.
           b. Wait SETTLE_TIME_S seconds for the plate to reach steady-state vibration.
           c. Grab n_averages pairs of frames from the camera.
           d. Subtract each pair to produce one difference image per pair.
           e. Average all difference images to reduce random noise.
           f. Save the averaged image to disk.
      5. Turn off the signal generator output, disconnect everything cleanly.
      6. Return a dictionary of { frequency → averaged_image }.

    WHY TWO FRAMES PER PAIR?
      ESPI works by comparing two frames of the same vibrating plate captured
      slightly apart in time.  Where the plate has moved between the two frames,
      the laser speckle pattern shifts and the subtraction reveals bright fringes.
      Averaging many such pairs reduces the random speckle noise.

    Args:
        start_freq  (float) : First frequency to test, in Hz.
        end_freq    (float) : Last frequency to test, in Hz.
        step        (float) : How much to increase the frequency each iteration, in Hz.
        n_averages  (int)   : How many frame pairs to capture and average at each
                              frequency.  More pairs = less noise, but slower sweep.
        exposure_us (float) : Camera exposure time in microseconds.
                              (10 ms = 10 000 µs is a common starting point for ESPI.)
        gain        (float) : Camera gain in dB. Higher values brighten the image but
                              also amplify noise. Typical range: 0.0 – 24.0 dB.
        output_dir  (str)   : Folder path where images will be saved.
                              Created automatically if it does not exist.
        gain_factor (float) : Multiplier applied to each difference image before
                              it is averaged and saved, so faint fringes are easier
                              to see. Applied with cv2.convertScaleAbs, which
                              saturates at 255 instead of wrapping around the way
                              plain multiplication of a uint8 array would. Defaults
                              to 1 (no amplification) so the saved data matches the
                              raw camera difference unless you explicitly ask for more.

    Returns:
        dict : Maps each frequency (float, Hz) to its averaged difference image
               (numpy array, uint8).  Example: { 100.0: array(...), 200.0: array(...) }
        None : If the signal generator or camera could not be connected.
    """

    # ==========================================================================
    # STEP 0 — VALIDATE INPUTS
    # ==========================================================================
    if start_freq <= 0:
        print("Invalid start_freq! Frequency must be positive.")
        return None
    if end_freq < start_freq:
        print("Invalid frequency range! end_freq must be >= start_freq.")
        return None
    if step <= 0:
        print("Invalid step! Step must be a positive number.")
        return None
    if n_averages <= 0:
        print("Invalid n_averages! Must be at least 1.")
        return None
    if exposure_us <= 0:
        print("Invalid exposure_us! Must be a positive number.")
        return None
    if gain < 0:
        print("Invalid gain! Gain cannot be negative.")
        return None

    # ==========================================================================
    # STEP 1 — CONNECT THE DEVICES
    # ==========================================================================
    # We must connect before doing anything else.
    # If either device is missing the program stops and notifies the user.

    instr = open_connection(index=0)
    if instr is None:
        print("ERROR: Signal generator not found. Check the USB cable and try again.")
        return None

    camera = connect_camera()
    if camera is None:
        print("ERROR: Camera not found. Check the USB cable and try again.")
        # Close the signal generator session we already opened before returning,
        # so it is not left in a locked state.
        close_connection(instr)
        return None

    # ==========================================================================
    # STEP 2 — CONFIGURE CAMERA SETTINGS
    # ==========================================================================
    # Lock exposure and gain so brightness stays constant for every frame in the
    # sweep.  Auto-exposure or auto-gain would change between frames and corrupt
    # the interference pattern.

    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain)

    # ==========================================================================
    # STEP 3 — CONFIGURE SIGNAL GENERATOR AND TURN OUTPUT ON
    # ==========================================================================
    # configure_channel sets waveform type, frequency, amplitude, and offset
    # all in one call, then turns the output ON.
    # We start at start_freq; the loop will update frequency each iteration.
    #
    # sg_settings is a dict with keys:
    #   "waveform", "frequency", "amplitude", "offset", "channel output"
    # We keep it so we can pass the waveform name to set_frequency later.

    sg_settings = configure_channel(
        instr,
        waveform  = "sine",
        frequency = start_freq,
        amplitude = 1.0,
        offset    = 0.0,
        channel   = 1,
    )

    # ==========================================================================
    # STEP 4 — CREATE OUTPUT FOLDER AND RESULTS CONTAINER
    # ==========================================================================

    # Create the output folder now so save_image() doesn't fail on a missing path.
    os.makedirs(output_dir, exist_ok=True)

    # This dict will collect { frequency: averaged_image } as the sweep runs.
    results = {}

    # ==========================================================================
    # STEP 5 — FREQUENCY SWEEP LOOP
    # ==========================================================================
    # Pre-compute the frequency list from start_freq + i * step so that
    # floating-point rounding never accumulates across iterations and end_freq
    # is always included exactly.

    n_steps = math.floor((end_freq - start_freq) / step + 1e-9)
    frequencies = [start_freq + i * step for i in range(n_steps + 1)]

    for freq in frequencies:

        print(f"\n--- Sweeping frequency: {freq} Hz ---")

        # ----------------------------------------------------------------------
        # 5a. Update the signal generator to the current frequency.
        #     We pass waveform so clamp_frequency uses the correct upper limit.
        # ----------------------------------------------------------------------
        set_frequency(instr, freq, channel=1, waveform=sg_settings["waveform"] or "sine")

        # ----------------------------------------------------------------------
        # 5b. Wait for the plate to reach steady-state vibration.
        #
        # After a frequency change the plate goes through a transient response
        # before settling into the resonant mode shape.  Capturing frames during
        # the transient produces a smeared difference image.  SETTLE_TIME_S
        # (defined at the top of this file) controls how long we wait.
        # ----------------------------------------------------------------------
        print(f"  Settling for {SETTLE_TIME_S} s — watch the live feed window...")
        _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

        # ----------------------------------------------------------------------
        # 5c & 5d. Capture n_averages pairs of frames and subtract each pair.
        #
        # Two frames are grabbed back-to-back at the same frequency.  The plate
        # moves slightly between them, so subtracting them reveals the speckle
        # shift caused by vibration at that frequency.
        # ----------------------------------------------------------------------
        imgs_subs = []   # will hold one difference image per pair

        for i in range(n_averages):
            imgs_grab = grab_n_frames(camera, 2)

            # grab_n_frames returns a list; we need at least 2 frames to form a
            # pair.  Skip this iteration if the camera failed to deliver both.
            if len(imgs_grab) < 2:
                print(f"  [WARNING] Failed to grab frame pair {i + 1} at {freq} Hz"
                      f" — only {len(imgs_grab)} frame(s) received. Skipping.")
                continue

            diff = cv2.convertScaleAbs(
                substract_frames(imgs_grab[0], imgs_grab[1]), alpha=gain_factor
            )
            imgs_subs.append(diff)

        # ----------------------------------------------------------------------
        # 5e. Average all difference images to reduce noise.
        #
        # If every grab in the loop above failed, imgs_subs will be empty.
        # average_img returns None in that case — we skip saving and move on.
        # ----------------------------------------------------------------------
        if len(imgs_subs) == 0:
            print(f"  [WARNING] No valid frame pairs captured at {freq} Hz. "
                  f"Skipping this frequency.")
            continue

        averaged = average_img(imgs_subs)

        if averaged is None:
            print(f"  [WARNING] average_img returned None at {freq} Hz. Skipping.")
            continue

        # ----------------------------------------------------------------------
        # 5f. Save the averaged difference image to disk.
        # ----------------------------------------------------------------------
        saved_path = save_image(
            averaged,
            output_dir   = output_dir,
            frequency_hz = freq,
            exposure_us  = exposure_us,
            step         = "espi_sweep",
        )
        if saved_path:
            print(f"  Saved: {saved_path}")

        # Store the result in memory so the caller can use it directly.
        results[freq] = averaged

        disp = amplify_difference(averaged)
        cv2.putText(disp, f"Last: {freq:g} Hz", (10, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA)
        cv2.imshow("ESPI Sweep — Last Result", disp)
        cv2.waitKey(1)

    # ==========================================================================
    # STEP 6 — CLEAN UP
    # ==========================================================================
    # Always turn off the output and disconnect both devices when the sweep
    # is done, even if some frequencies were skipped due to errors.

    print("\n--- Sweep complete. Disconnecting devices. ---")
    turn_off_output(instr, channel=1)
    disconnect_camera(camera)
    close_connection(instr)

    # ==========================================================================
    # STEP 7 — RETURN RESULTS
    # ==========================================================================
    cv2.destroyAllWindows()
    print(f"Results collected for {len(results)} frequency/frequencies. "
          f"Images saved to: {output_dir}")
    return results


def reference_frequency_sweep(start_freq, end_freq, step, n_averages, exposure_us, gain, output_dir,
                               gain_factor=1):
    """
    Reference-based ESPI frequency sweep.

    HOW THIS DIFFERS FROM frequency_sweep():
      frequency_sweep() grabs two frames back-to-back at each frequency and
      subtracts them from each other (pair subtraction).  This function instead
      captures one reference frame BEFORE vibration starts (signal generator
      off), then at every frequency subtracts each individual grabbed frame
      from that fixed reference.

      Pair subtraction shows the change between two instants of the vibrating
      plate.  Reference subtraction shows the total displacement from the
      resting state, which can reveal slower or lower-amplitude deformations
      that pair subtraction averages away.

    HOW IT WORKS STEP BY STEP:
      1. Connect to both devices and configure the camera.
      2. Capture one reference frame with the signal generator OFF
         (plate at rest).
      3. Turn on the signal generator at start_freq.
      4. Loop through every frequency:
           a. Set the signal generator to the current frequency.
           b. Wait SETTLE_TIME_S seconds for the plate to settle.
           c. Grab n_averages individual frames.
           d. Subtract each frame from the reference image.
           e. Average all difference images to reduce noise.
           f. Save the result to disk.
      5. Turn off the signal generator and disconnect cleanly.
      6. Return { frequency → averaged_difference_image }.

    Args:
        start_freq  (float) : First frequency to test, in Hz.
        end_freq    (float) : Last frequency to test, in Hz.
        step        (float) : Frequency increment per iteration, in Hz.
        n_averages  (int)   : Frames to grab at each frequency.
        exposure_us (float) : Camera exposure time in microseconds.
        gain        (float) : Camera gain in dB.
        output_dir  (str)   : Folder where images are saved.
        gain_factor (float) : Multiplier applied to each difference image before
                              it is averaged and saved. See frequency_sweep()'s
                              docstring for why cv2.convertScaleAbs is used
                              instead of plain multiplication. Defaults to 1
                              (no amplification).

    Returns:
        dict : { frequency_hz: averaged_difference_image } or None on error.
    """

    # ==========================================================================
    # STEP 0 — VALIDATE INPUTS
    # ==========================================================================
    if start_freq <= 0:
        print("Invalid start_freq! Frequency must be positive.")
        return None
    if end_freq < start_freq:
        print("Invalid frequency range! end_freq must be >= start_freq.")
        return None
    if step <= 0:
        print("Invalid step! Step must be a positive number.")
        return None
    if n_averages <= 0:
        print("Invalid n_averages! Must be at least 1.")
        return None
    if exposure_us <= 0:
        print("Invalid exposure_us! Must be a positive number.")
        return None
    if gain < 0:
        print("Invalid gain! Gain cannot be negative.")
        return None

    # ==========================================================================
    # STEP 1 — CONNECT
    # ==========================================================================
    instr = open_connection(index=0)
    if instr is None:
        print("ERROR: Signal generator not found. Check the USB cable and try again.")
        return None

    camera = connect_camera()
    if camera is None:
        print("ERROR: Camera not found. Check the USB cable and try again.")
        close_connection(instr)
        return None

    # ==========================================================================
    # STEP 2 — CONFIGURE CAMERA
    # ==========================================================================
    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain)

    os.makedirs(output_dir, exist_ok=True)
    results = {}

    # ==========================================================================
    # STEP 3 — CAPTURE REFERENCE FRAME (signal generator OFF)
    # ==========================================================================
    # The reference must be captured before vibration starts so it represents
    # the undisturbed resting state of the plate.
    print("\nCapturing reference frame (signal generator OFF, plate at rest)...")
    ref_frames = grab_n_frames(camera, 1)
    if len(ref_frames) < 1:
        print("ERROR: Could not capture reference frame. Aborting.")
        disconnect_camera(camera)
        close_connection(instr)
        return None
    reference = ref_frames[0]
    print("Reference frame captured.")

    # ==========================================================================
    # STEP 4 — CONFIGURE SIGNAL GENERATOR AND TURN OUTPUT ON
    # ==========================================================================
    sg_settings = configure_channel(
        instr,
        waveform  = "sine",
        frequency = start_freq,
        amplitude = 1.0,
        offset    = 0.0,
        channel   = 1,
    )

    # ==========================================================================
    # STEP 5 — FREQUENCY SWEEP LOOP
    # ==========================================================================
    n_steps     = math.floor((end_freq - start_freq) / step + 1e-9)
    frequencies = [start_freq + i * step for i in range(n_steps + 1)]

    for freq in frequencies:

        print(f"\n--- Sweeping frequency: {freq} Hz ---")

        set_frequency(instr, freq, channel=1, waveform=sg_settings["waveform"] or "sine")

        print(f"  Settling for {SETTLE_TIME_S} s — watch the live feed window...")
        _settle_with_live_feed(camera, SETTLE_TIME_S, freq)

        # Grab n_averages individual frames (not pairs) and subtract each from
        # the reference captured before vibration began.
        imgs_subs = []
        frames = grab_n_frames(camera, n_averages)

        for frame in frames:
            diff = cv2.convertScaleAbs(substract_frames(reference, frame), alpha=gain_factor)
            imgs_subs.append(diff)

        if len(imgs_subs) == 0:
            print(f"  [WARNING] No frames captured at {freq} Hz. Skipping.")
            continue

        averaged = average_img(imgs_subs)
        if averaged is None:
            print(f"  [WARNING] average_img returned None at {freq} Hz. Skipping.")
            continue

        saved_path = save_image(
            averaged,
            output_dir   = output_dir,
            frequency_hz = freq,
            exposure_us  = exposure_us,
            step         = "espi_ref",
        )
        if saved_path:
            print(f"  Saved: {saved_path}")

        results[freq] = averaged

        disp = amplify_difference(averaged)
        cv2.putText(disp, f"Last: {freq:g} Hz", (10, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, 200, 2, cv2.LINE_AA)
        cv2.imshow("ESPI Sweep — Last Result", disp)
        cv2.waitKey(1)

    # ==========================================================================
    # STEP 6 — CLEAN UP
    # ==========================================================================
    print("\n--- Sweep complete. Disconnecting devices. ---")
    turn_off_output(instr, channel=1)
    disconnect_camera(camera)
    close_connection(instr)

    cv2.destroyAllWindows()
    print(f"Results collected for {len(results)} frequency/frequencies. "
          f"Images saved to: {output_dir}")
    return results


# ==============================================================================
# QUICK-START EXAMPLE
# ==============================================================================
# This block only runs when you execute this file directly:
#   python complete_pipeline.py
#
# It does NOT run when you import this file from another script, so it is
# safe to leave here as reference code.
# ==============================================================================
if __name__ == "__main__":

    print("Choose subtraction mode:")
    print("  1 — Pair subtraction       (subtract consecutive frame pairs at each frequency)")
    print("  2 — Reference subtraction  (subtract each frame from a pre-captured resting reference)")
    mode = input("Enter 1 or 2: ").strip()

    sweep_params = dict(
        start_freq  = 100,      # Hz
        end_freq    = 1000,     # Hz
        step        = 100,      # Hz  — tests 100, 200, 300, ... 1000
        n_averages  = 5,        # frames (pairs for mode 1, individual for mode 2)
        exposure_us = 10000,    # 10 ms exposure
        gain        = 0.0,      # 0 dB gain (no amplification)
        output_dir  = "output", # images saved to ./output/
    )

    if mode == "2":
        print("\nRunning reference subtraction sweep...")
        results = reference_frequency_sweep(**sweep_params)
    else:
        if mode != "1":
            print("Unrecognised input — defaulting to pair subtraction.")
        print("\nRunning pair subtraction sweep...")
        results = frequency_sweep(**sweep_params)

    if results is not None:
        print(f"\nFrequencies measured: {list(results.keys())}")
