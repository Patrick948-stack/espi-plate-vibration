"""
capture_and_display.py
Author: Patrick Mulikuza

Connects to a Basler camera and opens two live windows simultaneously:
  - "Live Feed"         : raw frames straight from the camera
  - "Frame Subtraction" : absolute difference between each consecutive pair of
                          frames — bright pixels show where the image changed

Press 'q' to quit.

HOW TO RUN
----------
    python3 capture_and_display.py

HOW TO CHANGE THE BRIGHTNESS
-----------------------------
Change EXPOSURE_US (shutter time in microseconds) and GAIN_DB below.

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
# SETTINGS
# ==============================================================================

EXPOSURE_US = 60000    # shutter time in microseconds (10 000 µs = 10 ms)
GAIN_DB     = 1.0      # amplification in dB. 0 means no extra gain


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    camera = connect_camera()
    if camera is None:
        print("No camera found. Check that it is plugged in and try again.")
        return

    set_exposure_manual(camera, EXPOSURE_US)
    set_gain_manual(camera, GAIN_DB)

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
                    diff = 20 * cv2.absdiff(frame, prev_frame)
                    cv2.imshow("Frame Subtraction", diff)

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
