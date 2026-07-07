"""
capture_and_display.py
Author: Patrick Mulikuza

Connects to a Basler camera and opens two live windows simultaneously:
  - "Live Feed"         : raw frames straight from the camera
  - "Frame Subtraction" : absolute difference between each consecutive pair of
                          frames, amplified by gain_factor so faint fringes
                          are easier to see. Bright pixels show where the
                          image changed

Press 'q' to quit.

HOW TO RUN
----------
    python3 capture_and_display.py

HOW TO CHANGE THE BRIGHTNESS
-----------------------------
Change EXPOSURE_US, GAIN_DB, and Gain_factor below, or call main() directly
with your own values, exactly what monitor.py does:

    import capture_and_display as cad
    cad.main(exposure_us=10000, gain_db=1.0, gain_factor=20)

DEPENDENCIES
------------
    pip install pypylon numpy opencv-python
"""

from pypylon import pylon
from camera_control import (
    connect_camera,
    disconnect_camera,
    set_exposure_manual,
    set_gain_manual,
)
import cv2
import numpy as np


# ==============================================================================
# SETTINGS — used only when this file is run directly, not through monitor.py
# ==============================================================================

EXPOSURE_US = 60000    # shutter time in microseconds (10 000 µs = 10 ms)
GAIN_DB     = 1.0      # amplification in dB. 0 means no extra gain
Gain_factor = 20        # multiplier applied to the subtraction display


# ==============================================================================
# MAIN
# ==============================================================================

def main(exposure_us=EXPOSURE_US, gain_db=GAIN_DB, gain_factor=Gain_factor):
    """
    Open the first Basler camera and show the live feed and frame
    subtraction windows until 'q' is pressed.

    Args:
        exposure_us : shutter time in microseconds
        gain_db     : camera gain in dB
        gain_factor : multiplier applied to the subtraction image so faint
                      fringes are easier to see on screen. Uses
                      cv2.convertScaleAbs, which saturates at 255 instead of
                      wrapping around the way plain multiplication of a
                      uint8 array would.
    """
    camera = connect_camera()
    if camera is None:
        print("No camera found. Check that it is plugged in and try again.")
        return

    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain_db)

    print("Two windows open:")
    print("  'Live Feed'         — raw frame from the camera")
    print("  'Frame Subtraction' — absolute difference between consecutive frames")
    print("Press 'q' to quit.")

    prev_frame = None

    try:
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        while camera.IsGrabbing():
            grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grab_result.GrabSucceeded():
                frame = grab_result.Array.copy()
                grab_result.Release()

                cv2.imshow("Live Feed", frame)

                if prev_frame is not None:
                    diff = cv2.absdiff(frame, prev_frame)
                    amplified = cv2.convertScaleAbs(diff, alpha=gain_factor)
                    cv2.imshow("Frame Subtraction", amplified)

                prev_frame = frame
            else:
                grab_result.Release()

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        camera.StopGrabbing()
        cv2.destroyAllWindows()
        disconnect_camera(camera)


if __name__ == "__main__":
    main()
