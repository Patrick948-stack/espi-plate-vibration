"""
capture_and_display_cv2.py
Author: Patrick Mulikuza

Works with any camera your computer can detect (webcams, USB cameras, or any
other camera the operating system recognises). No special SDK needed. If your 
camera is an industrial one with a dedicated SDK, you might need to use a 
different program.

Two windows open simultaneously:
  - "Live Feed"         : raw frames straight from the camera
  - "Frame Subtraction" : absolute difference between each consecutive pair of
                          frames. Bright areas show where the image changed

Press 'q' to close the window.

HOW TO RUN
----------
    python3 capture_and_display_cv2.py

HOW TO CHANGE SETTINGS
-----------------------
Edit CAMERA_INDEX and EXPOSURE at the top of this file.

CAMERA INDEX NOTE
-----------------
CAMERA_INDEX = 0  →  first camera the OS finds (usually built-in webcam if no camera is connected, on macbook, if you have Continuity Camera enabled (the setting that lets your macbook use your iphone camera), 0 might refer to your iphone camera, and 1 to your macbook webcam, unless you connect an external camera to your computer)

If the wrong camera opens, try 1, 2, 3, etc.

DEPENDENCIES
------------
    pip install opencv-python numpy
"""

import cv2
import numpy as np


# ==============================================================================
# SETTINGS
# ==============================================================================

CAMERA_INDEX = 0    # 1 = built-in webcam, 0 = first external USB camera
EXPOSURE     = -6   # manual exposure (OpenCV log₂ scale):
                    #   -1  = long / bright
                    #   -6  = medium (good starting point)
                    #   -11 = short / dark
                    # If brightness doesn't respond, your camera driver doesn't
                    # support manual exposure via OpenCV — images still work.


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_AVFOUNDATION)

    if not cap.isOpened():
        print(f"Could not open camera at index {CAMERA_INDEX}.")
        print("Try changing CAMERA_INDEX to 0, 1, or 2 at the top of this file. Or check your camera connection.")
        return

    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE)

    print("Two windows open:")
    print("  'Live Feed'         — raw frame from the camera")
    print("  'Frame Subtraction' — absolute difference between consecutive frames")
    print("Press 'q' to quit.")

    prev_gray = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame — check camera connection.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        cv2.imshow("Live Feed", gray)

        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            cv2.imshow("Frame Subtraction", diff)

        prev_gray = gray

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
