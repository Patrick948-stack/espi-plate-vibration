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
Change EXPOSURE_US, GAIN_DB, and GAIN_FACTOR below, or call main() directly
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
import live_graphs
import cv2
import numpy as np


# ==============================================================================
# SETTINGS — used only when this file is run directly, not through monitor.py
# ==============================================================================

EXPOSURE_US = 60000    # shutter time in microseconds (10 000 µs = 10 ms)
GAIN_DB     = 1.0      # amplification in dB. 0 means no extra gain
GAIN_FACTOR = 20        # multiplier applied to the subtraction display


# ==============================================================================
# MAIN
# ==============================================================================

def main(exposure_us=EXPOSURE_US, gain_db=GAIN_DB, gain_factor=GAIN_FACTOR,
         graph_type=None):
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
        graph_type  : None (default, no extra window), "histogram",
                      "log_histogram", or "3d".
                      Opens a third window that graphs the pixel intensity
                      of the raw "Live Feed" frame, updated live. See
                      live_graphs.py for how each type works and why the
                      3d option updates slower than the camera frame rate.
    """
    camera = connect_camera()
    if camera is None:
        print("No camera found. Check that it is plugged in and try again.")
        return

    set_exposure_manual(camera, exposure_us)
    set_gain_manual(camera, gain_db)

    live_graph = live_graphs.create_live_graph(graph_type)

    print("Two windows open:")
    print("  'Live Feed'         — raw frame from the camera")
    print("  'Frame Subtraction' — absolute difference between consecutive frames")
    if live_graph is not None:
        print(f"  '{graph_type}' graph — live pixel intensity of the raw frame")
    print("Press 'q' to quit.")

    prev_frame = None

    try:
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        while camera.IsGrabbing():
            try:
                grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            except Exception as e:
                # TimeoutHandling_ThrowException means a stalled or
                # disconnected camera raises here instead of returning a
                # failed result. Report it and stop cleanly instead of
                # letting a raw pylon traceback end the whole program —
                # the same behavior capture_and_display_allied.py already
                # has for its own grab loop.
                print(f"\n[ERROR] Frame grab failed: {e}")
                print("  Stopping. If this repeats, unplug and replug the camera cable.")
                break

            if grab_result.GrabSucceeded():
                frame = grab_result.Array.copy()
                grab_result.Release()

                cv2.imshow("Live Feed", frame)

                if live_graph is not None:
                    live_graph.update(frame)

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
        if live_graph is not None:
            live_graph.close()
        disconnect_camera(camera)


if __name__ == "__main__":
    main()
