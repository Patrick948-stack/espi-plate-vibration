"""
capture_and_display_allied.py
Author: Patrick Mulikuza

Allied Vision camera equivalent of capture_and_display_cv2.py.
Uses the VimbaX Python SDK (vmbpy) instead of OpenCV's generic VideoCapture.

Two windows open simultaneously:
  - "Live Feed"         : raw frames straight from the camera
  - "Frame Subtraction" : absolute difference between each consecutive pair of
                          frames — bright pixels show where the image changed

Press 'q' to quit.

HOW TO RUN
----------
    python3 capture_and_display_allied.py

HOW TO CHANGE SETTINGS
-----------------------
Edit the values under SETTINGS below.

CAMERA INDEX NOTE
-----------------
CAMERA_INDEX = 0 picks the first Allied Vision camera the SDK finds.
If you have multiple cameras connected, try 1, 2, etc.
Set LIST_CAMERAS = True to print all detected cameras and their IDs, then exit.

DEPENDENCIES
------------
    pip install vmbpy opencv-python numpy
    (vmbpy requires the VimbaX runtime to be installed — download from Allied Vision)
"""

import cv2
import numpy as np
import vmbpy


# ==============================================================================
# SETTINGS
# ==============================================================================

CAMERA_INDEX  = 0           # index of the Allied Vision camera to use (0 = first found)
EXPOSURE_US   = 10000       # exposure time in microseconds (10000 µs = 10 ms)
                            #   1000   =  1 ms  → short / dark
                            #  10000   = 10 ms  → medium (good starting point)
                            # 100000   = 100 ms → long / bright
LIST_CAMERAS  = False       # set True to print all detected cameras and exit


# ==============================================================================
# HELPERS
# ==============================================================================

def get_camera(vmb, index):
    """Return the camera at position `index` in the detected camera list."""
    cams = vmb.get_all_cameras()
    if not cams:
        raise RuntimeError("No Allied Vision cameras detected. Check USB/GigE connection.")
    if index >= len(cams):
        raise RuntimeError(
            f"CAMERA_INDEX={index} is out of range — only {len(cams)} camera(s) found."
        )
    return cams[index]


def set_exposure(cam, exposure_us):
    """Set manual exposure in microseconds (disables auto-exposure first)."""
    try:
        cam.ExposureAuto.set("Off")
    except Exception:
        pass
    try:
        cam.ExposureTime.set(float(exposure_us))
        print(f"  Exposure set to {exposure_us} µs.")
    except Exception as e:
        print(f"  [WARNING] Could not set exposure: {e}")


def frame_to_gray(frame):
    """Convert a vmbpy Frame to an 8-bit greyscale numpy array."""
    cv_img = frame.as_opencv_image()
    if cv_img.ndim == 3:
        if cv_img.shape[2] == 1:
            return cv_img[:, :, 0]
        return cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    return cv_img


# ==============================================================================
# MAIN
# ==============================================================================

with vmbpy.VmbSystem.get_instance() as vmb:

    if LIST_CAMERAS:
        cams = vmb.get_all_cameras()
        print(f"Found {len(cams)} Allied Vision camera(s):")
        for i, c in enumerate(cams):
            print(f"  [{i}]  ID={c.get_id()}  Name={c.get_name()}  Model={c.get_model()}")
        raise SystemExit(0)

    cam = get_camera(vmb, CAMERA_INDEX)
    print(f"Using camera [{CAMERA_INDEX}]: {cam.get_name()}  (ID={cam.get_id()})")

    print("Two windows open:")
    print("  'Live Feed'         — raw frame from the camera")
    print("  'Frame Subtraction' — absolute difference between consecutive frames")
    print("Press 'q' to quit.")

    with cam:
        set_exposure(cam, EXPOSURE_US)

        try:
            cam.set_pixel_format(vmbpy.PixelFormat.Mono8)
        except Exception:
            pass

        prev_gray = None

        while True:
            try:
                frame = cam.get_frame(timeout_ms=2000)
            except vmbpy.VmbTimeout:
                print("  [WARNING] Frame timeout — retrying...")
                continue
            except Exception as e:
                print(f"  [ERROR] Frame grab failed: {e}")
                print("  Stopping. If this repeats, unplug and replug the USB cable.")
                break

            gray = frame_to_gray(frame)

            cv2.imshow("Live Feed", gray)

            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                cv2.imshow("Frame Subtraction", diff)

            prev_gray = gray

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()
