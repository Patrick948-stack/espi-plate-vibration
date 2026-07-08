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
Edit CAMERA_INDEX, EXPOSURE, and GAIN at the top of this file, or call
main() directly with your own values, exactly what monitor.py does:

    import capture_and_display_cv2 as cad_cv2
    cad_cv2.main(camera_index=0, exposure=-6, gain=0.0, gain_factor=20)

CAMERA INDEX NOTE
-----------------
CAMERA_INDEX = 0  →  first camera the OS finds (usually built-in webcam if no camera is connected, on macbook, if you have Continuity Camera enabled (the setting that lets your macbook use your iphone camera), 0 might refer to your iphone camera, and 1 to your macbook webcam, unless you connect an external camera to your computer)

If the wrong camera opens, try 1, 2, 3, etc.

DEPENDENCIES
------------
    pip install opencv-python numpy
"""

import sys

import cv2
import numpy as np

import live_graphs


# ==============================================================================
# SETTINGS — used only when this file is run directly, not through monitor.py
# ==============================================================================

CAMERA_INDEX = 0    # 1 = built-in webcam, 0 = first external USB camera
EXPOSURE     = -6   # manual exposure (OpenCV log₂ scale):
                    #   -1  = long / bright
                    #   -6  = medium (good starting point)
                    #   -11 = short / dark
                    # If brightness doesn't respond, your camera driver doesn't
                    # support manual exposure via OpenCV — images still work.
GAIN         = 0.0  # camera gain, camera-dependent scale. Not all cameras
                    # let OpenCV control gain, it may be silently ignored.
Gain_factor  = 20   # multiplier applied to the subtraction display


def _capture_backend():
    """
    Pick the OpenCV capture backend for the current operating system.

    cv2.CAP_AVFOUNDATION only exists on macOS (it is Apple's AVFoundation
    media framework). Using it on Windows either fails to open the camera
    or silently falls back to a slower default, depending on the OpenCV
    build — this file used to hardcode it unconditionally, which meant it
    was never reliably tested on Windows even though nothing about the
    surrounding code looks platform-specific.

    cv2.CAP_DSHOW (DirectShow) is the reliable, fast-opening choice on
    Windows. Linux and anything else fall back to cv2.CAP_ANY, which lets
    OpenCV pick automatically.
    """
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY


# ==============================================================================
# MAIN
# ==============================================================================

def main(camera_index=CAMERA_INDEX, exposure=EXPOSURE, gain=GAIN,
         gain_factor=Gain_factor, graph_type=None):
    """
    Open camera_index and show the live feed and frame subtraction windows
    until 'q' is pressed.

    Args:
        camera_index : which camera to open (0 = first the OS finds)
        exposure     : OpenCV log₂ exposure value, NOT seconds or
                       microseconds. If you have an exposure time in
                       seconds, convert it with math.log2(seconds) before
                       calling main(), exactly what monitor.py does.
        gain         : camera gain, camera-dependent scale. Not all cameras
                       let OpenCV control gain, it may be silently ignored.
        gain_factor  : multiplier applied to the subtraction image so faint
                       fringes are easier to see on screen. Uses
                       cv2.convertScaleAbs, which saturates at 255 instead
                       of wrapping around the way plain multiplication of a
                       uint8 array would.
        graph_type   : None (default, no extra window), "histogram", or
                       "3d". Opens a third window that graphs the pixel
                       intensity of the raw "Live Feed" frame, updated
                       live. See live_graphs.py for details.
    """
    cap = cv2.VideoCapture(camera_index, _capture_backend())

    if not cap.isOpened():
        print(f"Could not open camera at index {camera_index}.")
        print("Try changing camera_index to 0, 1, or 2. Or check your camera connection.")
        return

    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
    cap.set(cv2.CAP_PROP_GAIN, gain)

    live_graph = live_graphs.create_live_graph(graph_type)

    print("Two windows open:")
    print("  'Live Feed'         — raw frame from the camera")
    print("  'Frame Subtraction' — absolute difference between consecutive frames")
    if live_graph is not None:
        print(f"  '{graph_type}' graph — live pixel intensity of the raw frame")
    print("Press 'q' to quit.")

    prev_gray = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame — check camera connection.")
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            cv2.imshow("Live Feed", gray)

            if live_graph is not None:
                live_graph.update(gray)

            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                amplified = cv2.convertScaleAbs(diff, alpha=gain_factor)
                cv2.imshow("Frame Subtraction", amplified)

            prev_gray = gray

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if live_graph is not None:
            live_graph.close()


if __name__ == "__main__":
    main()
