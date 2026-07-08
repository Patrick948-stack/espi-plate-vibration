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
Edit the values under SETTINGS below, or call main() directly with your own
values, exactly what monitor.py does:

    import capture_and_display_allied as cad_av
    cad_av.main(camera_index=0, exposure_us=10000, gain=0.0, gain_factor=20)

Importing this file no longer opens a camera by itself, only main() does.

CAMERA INDEX NOTE
-----------------
camera_index = 0 picks the first Allied Vision camera the SDK finds.
If you have multiple cameras connected, try 1, 2, etc.
Pass list_cameras=True to main() to print all detected cameras and their
IDs instead of opening a live feed.

DEPENDENCIES
------------
    pip install vmbpy opencv-python numpy
    (vmbpy requires the VimbaX runtime to be installed — download from Allied Vision)
"""

import cv2
import numpy as np
import vmbpy

import live_graphs


# ==============================================================================
# SETTINGS — used only when this file is run directly, not through monitor.py
# ==============================================================================

CAMERA_INDEX  = 0           # index of the Allied Vision camera to use (0 = first found)
EXPOSURE_US   = 10000       # exposure time in microseconds (10000 µs = 10 ms)
                            #   1000   =  1 ms  → short / dark
                            #  10000   = 10 ms  → medium (good starting point)
                            # 100000   = 100 ms → long / bright
GAIN          = None        # camera gain in dB, or None to leave it unchanged
LIST_CAMERAS  = False       # set True to print all detected cameras and exit

Gain_factor = 20 # Factor by which the difference will be multiplied



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
            f"camera_index={index} is out of range — only {len(cams)} camera(s) found."
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


def set_gain(cam, gain):
    """Set manual gain in dB (disables auto-gain first). Skipped if gain is None."""
    if gain is None:
        return
    try:
        cam.GainAuto.set("Off")
    except Exception:
        pass
    try:
        cam.Gain.set(float(gain))
        print(f"  Gain set to {gain} dB.")
    except Exception as e:
        print(f"  [WARNING] Could not set gain: {e}")


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

def main(camera_index=CAMERA_INDEX, exposure_us=EXPOSURE_US, gain=GAIN,
         gain_factor=Gain_factor, list_cameras=LIST_CAMERAS, graph_type=None):
    """
    Open an Allied Vision camera and show the live feed and frame
    subtraction windows until 'q' is pressed.

    Args:
        camera_index : index of the Allied Vision camera to use (0 = first found)
        exposure_us  : exposure time in microseconds
        gain         : camera gain in dB, or None to leave it unchanged
        gain_factor  : multiplier applied to the subtraction image so faint
                       fringes are easier to see on screen. Uses
                       cv2.convertScaleAbs, which saturates at 255 instead
                       of wrapping around the way plain multiplication of a
                       uint8 array would.
        list_cameras : if True, print all detected cameras and their IDs,
                       then return without opening a live feed
        graph_type   : None (default, no extra window), "histogram", or
                       "3d". Opens a third window that graphs the pixel
                       intensity of the raw "Live Feed" frame, updated
                       live. See live_graphs.py for details.
    """
    with vmbpy.VmbSystem.get_instance() as vmb:

        if list_cameras:
            cams = vmb.get_all_cameras()
            print(f"Found {len(cams)} Allied Vision camera(s):")
            for i, c in enumerate(cams):
                print(f"  [{i}]  ID={c.get_id()}  Name={c.get_name()}  Model={c.get_model()}")
            return

        try:
            cam = get_camera(vmb, camera_index)
        except RuntimeError as e:
            print(f"[ERROR] {e}")
            return

        print(f"Using camera [{camera_index}]: {cam.get_name()}  (ID={cam.get_id()})")

        live_graph = live_graphs.create_live_graph(graph_type)

        print("Two windows open:")
        print("  'Live Feed'         — raw frame from the camera")
        print("  'Frame Subtraction' — absolute difference between consecutive frames")
        if live_graph is not None:
            print(f"  '{graph_type}' graph — live pixel intensity of the raw frame")
        print("Press 'q' to quit.")

        with cam:
            set_exposure(cam, exposure_us)
            set_gain(cam, gain)

            try:
                cam.set_pixel_format(vmbpy.PixelFormat.Mono8)
            except Exception:
                pass

            prev_gray = None

            try:
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
                cv2.destroyAllWindows()
                if live_graph is not None:
                    live_graph.close()


if __name__ == "__main__":
    main()
