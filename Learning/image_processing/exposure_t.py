# ===============================================================================
# EXPOSURE CONTROL IN PYPYLON
# ===============================================================================
# Cameras have two exposure modes:
#
#   MANUAL  — you set a fixed exposure time (e.g. 5000 µs) and it never changes.
#             Good for: controlled lighting, high-speed capture, reproducibility.
#
#   AUTO    — the camera continuously measures brightness and adjusts exposure
#             on its own to hit a target brightness level you specify.
#             Good for: changing lighting conditions, live demos.
#
# This file demonstrates BOTH, then runs a short grab loop so you can watch
# the auto exposure value change in real time in the terminal.
# ===============================================================================

from pypylon import pylon    # Camera control: factory, InstantCamera, grabbing
from pypylon import genicam  # GenICam exceptions (catches all pypylon errors)

# -------------------------------------------------------------------------------
# CAMERA SETUP — same boilerplate as always
# -------------------------------------------------------------------------------
# Find the first connected Basler camera and open a session with it.
camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
camera.Open()

print("=" * 60)
print("Camera:", camera.GetDeviceInfo().GetModelName())
print("=" * 60)

try:
    # ===========================================================================
    # PART A: MANUAL EXPOSURE — ExposureTime.Value
    # ===========================================================================
    # Before turning on auto, let's see what manual exposure looks like.
    # ExposureTime is measured in MICROSECONDS (µs).
    #   1,000 µs  =   1 ms
    #  10,000 µs  =  10 ms  
    # 100,000 µs  = 100 ms  (very bright, motion blur likely)
    #
    # ExposureAuto must be "Off" for manual control to take effect.
    # ---------------------------------------------------------------------------

    # Turn off auto exposure so we can set a manual value
    # "Off" is a string enum — the camera accepts specific string tokens
    camera.ExposureAuto.Value = "Off"

    # Read the current exposure limits from the camera hardware
    # .Min and .Max are read-only properties — the camera tells you the boundary exposure time values
    min_exp = camera.ExposureTime.Min   # Shortest possible exposure (µs)
    max_exp = camera.ExposureTime.Max   # Longest possible exposure (µs)
    print(f"\n[Manual mode] Exposure range on this camera: {min_exp} µs to {max_exp} µs")

    # Set a specific manual exposure time (10,000 µs = 10 ms)
    # Change this number to experiment 
    # higher = brighter image, lower = darker
    manual_exposure_us = 10000.0
    camera.ExposureTime.Value = manual_exposure_us

    # Read it back to confirm the camera accepted the value
    print(f"[Manual mode] Exposure set to: {camera.ExposureTime.Value} µs")

    # ===========================================================================
    # PART B: AUTO EXPOSURE SETUP
    # ===========================================================================
    # Auto Exposure works by continuously measuring the image brightness and
    # adjusting the exposure time to hit a user-defined target brightness.
    #
    # There are three related limits you should set before enabling auto:
    #
    #   AutoExposureTimeLowerLimit — the shortest the auto can go (floor)
    #   AutoExposureTimeUpperLimit — the longest the auto can go (ceiling)
    #
    # Setting them to .Min and .Max (the hardware extremes) gives the auto
    # algorithm the widest possible range to work with.
    # You can narrow the range to prevent motion blur (cap the upper limit)
    # or prevent noise (raise the lower limit).
    # ---------------------------------------------------------------------------

    # Read the hardware-defined extremes for the auto limits
    # These are the absolute bounds the camera supports — set by Basler, not by you
    minLowerLimit = camera.AutoExposureTimeLowerLimit.Min  # e.g. 100 µs
    maxUpperLimit = camera.AutoExposureTimeUpperLimit.Max  # e.g. 1,000,000 µs

    # Apply the widest possible auto range
    # After this, auto exposure is allowed to roam the full hardware range
    camera.AutoExposureTimeLowerLimit.Value = minLowerLimit
    camera.AutoExposureTimeUpperLimit.Value = maxUpperLimit

    print(f"\n[Auto mode]   Auto exposure range: {minLowerLimit} µs to {maxUpperLimit} µs")

    # ---------------------------------------------------------------------------
    # TARGET BRIGHTNESS  —  camera.AutoTargetBrightness
    # ---------------------------------------------------------------------------
    # This is the brightness level the auto algorithm is trying to achieve.
    # Range: 0.0 (pure black) to 1.0 (pure white)
    #
    # 0.5 = mid-grey (neutral, good default)
    # 0.6 = slightly brighter than neutral (good for indoor scenes)
    # 0.3 = intentionally dark (useful for very bright scenes / HDR)
    #
    # The camera adjusts exposure until the average brightness of the
    # Auto Function ROI (see below) matches this value.
    # ---------------------------------------------------------------------------
    camera.AutoTargetBrightness.Value = 0.6  # Aim for 60% brightness
    print(f"[Auto mode]   Target brightness: {camera.AutoTargetBrightness.Value}")

    # ---------------------------------------------------------------------------
    # AUTO FUNCTION ROI  —  camera.AutoFunctionROISelector / AutoFunctionROIUseBrightness
    # ---------------------------------------------------------------------------
    # The camera does NOT measure brightness over the whole image by default.
    # Instead it uses a dedicated "Region of Interest" (ROI) for the measurement.
    #
    # AutoFunctionROISelector chooses WHICH roi slot to configure.
    # Most cameras have "ROI1" and "ROI2". Selecting one makes subsequent
    # AutoFunctionROI* writes apply to that slot.
    #
    # AutoFunctionROIUseBrightness = True
    #   Tells the camera to use the selected ROI when computing brightness
    #   for both Gain Auto AND Exposure Auto adjustments.
    #
    # Why does this matter?
    #   If your subject is in the center of the frame and the background is
    #   very bright or dark, measuring the whole image would skew the result.
    #   You can configure the ROI to cover only the region that matters.
    #   For now we leave the ROI at its default position (usually center).
    # ---------------------------------------------------------------------------
    camera.AutoFunctionROISelector.Value = "ROI1"        # Point at ROI slot 1
    camera.AutoFunctionROIUseBrightness.Value = True      # Use this ROI for brightness

    print(f"[Auto mode]   Auto function ROI: {camera.AutoFunctionROISelector.Value}")
    print(f"[Auto mode]   Use brightness ROI: {camera.AutoFunctionROIUseBrightness.Value}")

    # ---------------------------------------------------------------------------
    # ENABLE AUTO EXPOSURE  —  camera.ExposureAuto
    # ---------------------------------------------------------------------------
    # ExposureAuto accepts three string tokens:
    #
    #   "Off"        — manual mode, ExposureTime.Value is fixed
    #   "Once"       — auto runs until it converges on the target brightness,
    #                  then switches itself back to "Off" automatically.
    #                  Good for: one-shot adjustment before switching to manual.
    #   "Continuous" — auto runs forever, constantly re-adjusting.
    #                  Good for: scenes with changing light.
    # ---------------------------------------------------------------------------
    camera.ExposureAuto.Value = "Continuous"
    print(f"\n[Auto mode]   ExposureAuto is now: {camera.ExposureAuto.Value}")

    # ===========================================================================
    # PART C: GRAB LOOP — watch auto exposure adjust in real time
    # ===========================================================================
    # We grab 20 frames and print the actual ExposureTime.Value each time.
    # Because auto exposure is "Continuous", the value will shift frame by frame
    # as the algorithm converges toward the target brightness.
    # Point the camera at something bright, then cover the lens — you should
    # see the exposure time increase as the camera tries to compensate.
    # ===========================================================================

    print("\n--- Grabbing 20 frames. Watch ExposureTime change in real time ---\n")

    # StartGrabbingMax(n) — grab exactly n frames then stop automatically
    camera.StartGrabbingMax(20)

    frame_count = 0

    while camera.IsGrabbing():
        # Wait up to 5 seconds for the next frame
        # TimeoutHandling_ThrowException — raise an error if no frame arrives in time
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        if grabResult.GrabSucceeded():
            frame_count += 1

            # Read the CURRENT exposure time while the frame was being grabbed
            # Because ExposureAuto is "Continuous", this value changes each frame
            current_exposure = camera.ExposureTime.Value

            # grabResult.Array is a numpy ndarray of pixel values
            img = grabResult.Array

            # Compute mean brightness manually: sum all pixels / total pixels
            # img.mean() works because grabResult.Array is a numpy array
            mean_brightness = img.mean()

            print(f"Frame {frame_count:>2}  |  "
                  f"Exposure: {current_exposure:>10.1f} µs  |  "
                  f"Mean brightness: {mean_brightness:>6.1f} / 255")

        else:
            print(f"Frame {frame_count + 1}: Grab failed — {grabResult.ErrorDescription}")

        # ALWAYS release the grab result buffer so it can be reused
        # Forgetting this drains the buffer pool and stalls acquisition
        grabResult.Release()

    print("\n--- Grab complete ---")
    print(f"Final ExposureAuto state: {camera.ExposureAuto.Value}")
    print(f"Final ExposureTime:       {camera.ExposureTime.Value:.1f} µs")

except genicam.GenericException as e:
    # genicam.GenericException catches ALL pypylon/GenICam errors:
    # camera not found, feature not available, value out of range, timeout, etc.
    print("\n[ERROR] A GenICam exception occurred:")
    print(e)

finally:
    # ---------------------------------------------------------------------------
    # CLEANUP — always runs, even if an exception was raised above
    # ---------------------------------------------------------------------------
    # camera.Close() ends the communication session and frees resources.
    # Using a finally block guarantees the camera is never left open on error.
    # ---------------------------------------------------------------------------
    camera.Close()
    print("\nCamera closed.")
