"""
complete_pipeline.py
Author: Patrick Mulikuza

Ties the camera and signal generator control together into a single pipeline.

For each frequency between start_freq and end_freq (stepping by `step` Hz),
this script:
  1. Sets the signal generator to that frequency.
  2. Captures n_averages pairs of frames from the camera.
  3. Subtracts each pair to get a difference image.
  4. Averages all the difference images together to reduce noise.
  5. Saves the averaged result to disk as a PNG.

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
        exposure_us = 100000,     # camera exposure time in microseconds (10 ms)
        output_dir  = "output",  # folder where PNG images will be saved
    )

    # results is a dict: { frequency_in_Hz: averaged_difference_image, ... }
    # Each value is a numpy array you can pass to show_diff() or further process.

DEPENDENCIES
------------
    pip install pypylon numpy opencv-python pyvisa pyvisa-py
"""

import os

# Import every public function from both library files.
# "from X import *" brings in all names listed in their __all__ lists.
from control_signal_generator import *
from camera_control import *


def frequency_sweep(start_freq, end_freq, step, n_averages, exposure_us, gain, output_dir):
    """
    Run a full ESPI frequency sweep and save one averaged difference image per frequency.

    HOW IT WORKS STEP BY STEP:
      1. Connect to the signal generator and camera.
      2. Set the initial channel configuration on the signal generator.
      3. Set the camera exposure time.
      4. Loop through every frequency from start_freq to end_freq:
           a. Update the signal generator to the current frequency.
           b. Grab n_averages pairs of frames from the camera.
           c. Subtract each pair to produce a difference image.
           d. Average all difference images to reduce random noise.
           e. Save the averaged image to disk.
      5. Turn off the signal generator output, disconnect everything cleanly.
      6. Return a dictionary of { frequency → averaged_image }.

    Args:
        start_freq  (float) : First frequency to test, in Hz.
        end_freq    (float) : Last frequency to test, in Hz.
        step        (float) : How much to increase the frequency each iteration, in Hz.
        n_averages  (int)   : How many frame pairs to capture and average at each frequency.
                              More averages = less noise, but slower sweep.
        exposure_us (float) : Camera exposure time in microseconds.
                              (10 ms = 10 000 µs is a common starting point for ESPI.)
        gain        (float) : Camera gain in dB. Higher values brighten the image but
                              also amplify noise. Typical range: 0.0 – 24.0 dB.
        output_dir  (str)   : Folder path where images will be saved.
                              Created automatically if it does not exist.

    Returns:
        dict : Maps each frequency (float, Hz) to its averaged difference image
               (numpy array, uint8).  Example: { 100.0: array(...), 200.0: array(...) }
        None : If the signal generator or camera could not be connected.
    """

    # ==========================================================================
    # STEP 0 — VALIDATE INPUTS
    # ==========================================================================
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
    if start_freq <= 0:
        print("Invalid start_freq! Frequency must be positive.")
        return None

    # ==========================================================================
    # STEP 1 — CONNECT THE DEVICES
    # ==========================================================================
    # We must connect before doing anything else.
    # If either device is missing the program stops and notifies the user

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
    # STEP 2 — CONFIGURE INITIAL SETTINGS
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

    # Lock the camera to fixed exposure and gain so brightness stays constant
    # throughout the sweep.  Auto-exposure or auto-gain would change between
    # frames and corrupt the interference pattern.
    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain)

    # ==========================================================================
    # STEP 3 — CREATE OUTPUT FOLDER AND RESULTS CONTAINER
    # ==========================================================================

    # Create the output folder now so save_image() doesn't fail on a missing path.
    os.makedirs(output_dir, exist_ok=True)

    # This dict will collect { frequency: averaged_image } as the sweep runs.
    results = {}

    # ==========================================================================
    # STEP 4 — FREQUENCY SWEEP LOOP
    # ==========================================================================

    freq = start_freq

    while freq <= end_freq:

        print(f"\n--- Sweeping frequency: {freq} Hz ---")

        # ----------------------------------------------------------------------
        # 4a. Update the signal generator to the current frequency.
        #     We pass waveform so clamp_frequency uses the correct upper limit.
        # ----------------------------------------------------------------------
        set_frequency(instr, freq, channel=1, waveform=sg_settings["waveform"] or "sine")

        # ----------------------------------------------------------------------
        # 4b & 4c. Capture n_averages pairs of frames and subtract each pair.
        #
        # WHY TWO FRAMES PER PAIR?
        #   ESPI works by comparing a frame taken just BEFORE excitation to one
        #   taken just AFTER.  The difference reveals where the plate moved.
        #   We grab frame 0 (reference) and frame 1 (live) back-to-back.
        # ----------------------------------------------------------------------
        imgs_subs = []   # will hold one difference image per pair

        for i in range(n_averages):
            imgs_grab = grab_n_frames(camera, 2)

            # grab_n_frames may return fewer than 2 frames if the camera has a
            # problem.  We skip this pair rather than crash on imgs_grab[1].
            if len(imgs_grab) < 2:
                print(f"  [WARNING] Frame pair {i + 1}/{n_averages} incomplete "
                      f"— only {len(imgs_grab)} frame(s) received. Skipping.")
                continue

            diff = substract_frames(imgs_grab[0], imgs_grab[1])
            imgs_subs.append(diff)

        # ----------------------------------------------------------------------
        # 4d. Average all difference images to reduce noise.
        #
        # If every grab in the loop above failed, imgs_subs will be empty.
        # average_img returns None in that case — we skip saving and move on.
        # ----------------------------------------------------------------------
        if len(imgs_subs) == 0:
            print(f"  [WARNING] No valid frame pairs captured at {freq} Hz. "
                  f"Skipping this frequency.")
            freq += step
            continue

        averaged = average_img(imgs_subs)

        if averaged is None:
            print(f"  [WARNING] average_img returned None at {freq} Hz. Skipping.")
            freq += step
            continue

        # ----------------------------------------------------------------------
        # 4e. Save the averaged difference image to disk.
        #
        # build_filename creates a consistent name like:
        #   espi_1000Hz_2026-06-10_000.png
        # os.path.join puts it inside output_dir.
        # ----------------------------------------------------------------------
        save_image(
            averaged,
            output_dir=output_dir,
            frequency_hz=freq,
            exposure_us=exposure_us,
            step="Test Case",
                )


        # Store the result in memory so the caller can use it directly.
        results[freq] = averaged

        # Advance to the next frequency.
        # Without this line the loop would repeat the same frequency forever.
        freq += step

    # ==========================================================================
    # STEP 5 — CLEAN UP
    # ==========================================================================
    # Always turn off the output and disconnect both devices when the sweep
    # is done, even if some frequencies were skipped due to errors.

    print("\n--- Sweep complete. Disconnecting devices. ---")
    turn_off_output(instr, channel=1)
    disconnect_camera(camera)
    close_connection(instr)

    # ==========================================================================
    # STEP 6 — RETURN RESULTS
    # ==========================================================================
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

    results = frequency_sweep(
        start_freq  = 100,       # Hz
        end_freq    = 1000,      # Hz
        step        = 100,       # Hz  — tests 100, 200, 300, ... 1000
        n_averages  = 5,         # 5 pairs averaged per frequency
        exposure_us = 10000,     # 10 ms exposure
        output_dir  = "output",  # images saved to ./output/
    )

    if results is not None:
        print(f"\nFrequencies measured: {list(results.keys())}")
