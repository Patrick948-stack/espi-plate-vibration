"""
image_substraction.py
=====================
A self-contained file for ESPI image capture and subtraction.

Functions:
    connect_camera()                          — open the first Basler camera
    disconnect_camera(camera)                 — safely close the camera
    capture_images(camera, n, exposure_us)    — grab n frames at a fixed exposure
    display_images(frames)                    — show each frame in an OpenCV window
    save_images(frames, folder_name)          — save frames to ~/Desktop/<folder_name>/
    subtract_frames(frame_a, frame_b)         — pixel-wise absolute difference

Dependencies:
    pip install pypylon numpy opencv-python
"""

from pypylon import pylon
from pypylon import genicam
import numpy as np
import cv2
import os
import time


# ==============================================================================
# CAMERA CONNECTION
# ==============================================================================

def connect_camera():
    """
    Find the first available Basler camera, open it, and return it.

    Returns the camera object, or None if no camera is found.

    Example:
        camera = connect_camera()
        if camera is None:
            print("No camera found.")
    """
    try:
        device = pylon.TlFactory.GetInstance().CreateFirstDevice()
        camera = pylon.InstantCamera(device)
        camera.Open()
        print(f"Connected to: {camera.GetDeviceInfo().GetModelName()}")
        return camera
    except genicam.GenericException as e:
        print(f"Could not connect to camera: {e}")
        return None


def disconnect_camera(camera):
    """
    Safely close the connection to the camera.

    Always call this when you are done, even if something went wrong earlier.

    Example:
        disconnect_camera(camera)
    """
    try:
        if camera.IsGrabbing():
            camera.StopGrabbing()
        camera.Close()
        print("Camera disconnected.")
    except genicam.GenericException as e:
        print(f"Error while disconnecting camera: {e}")


# ==============================================================================
# IMAGE CAPTURE
# ==============================================================================

def capture_images(camera, n: int, exposure_us: float, delay_s: float = 0.0) -> list:
    """
    Set the exposure time and grab n frames from the camera.

    Args:
        camera      : camera object returned by connect_camera()
        n           : number of frames to capture
        exposure_us : exposure time in microseconds (e.g. 10000 = 10 ms)

    Returns a list of numpy arrays (one per frame). The list may be shorter
    than n if some frames fail to grab.

    Example:
        frames = capture_images(camera, 5, 10000)
        print(f"Captured {len(frames)} frames")
    """
    # Lock exposure to a fixed value so brightness stays constant across frames.
    camera.ExposureAuto.Value = "Off"
    exposure_us = max(camera.ExposureTime.Min, min(exposure_us, camera.ExposureTime.Max))
    camera.ExposureTime.Value = exposure_us
    print(f"Exposure set to: {camera.ExposureTime.Value} µs")

    frames = []
    try:
        camera.StartGrabbingMax(n)
        while camera.IsGrabbing():
            grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            if grabResult.GrabSucceeded():
                frames.append(grabResult.Array.copy())
            else:
                print(f"Frame {len(frames) + 1} grab failed: {grabResult.ErrorDescription}")
            grabResult.Release()
            if delay_s > 0:
                time.sleep(delay_s)
    except genicam.GenericException as e:
        print(f"Error grabbing frames: {e}")

    print(f"Captured {len(frames)} / {n} frames.")
    return frames


# ==============================================================================
# DISPLAY
# ==============================================================================

def display_images(frames: list) -> None:
    """
    Show each frame in a numbered OpenCV window.

    All windows open at once. Press any key to close them.

    Args:
        frames : list of numpy arrays returned by capture_images()

    Example:
        display_images(frames)
    """
    if not frames:
        print("No frames to display.")
        return

    for i, frame in enumerate(frames):
        cv2.imshow(f"Frame {i + 1}", frame)

    print(f"Displaying {len(frames)} frame(s) — press any key to close.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ==============================================================================
# SAVE
# ==============================================================================

def save_images(frames: list, folder_name: str) -> list:
    """
    Save a list of frames to ~/Desktop/<folder_name>/.

    The folder is created if it does not exist. Files are named
    frame_001.png, frame_002.png, etc.

    Args:
        frames      : list of numpy arrays returned by capture_images()
        folder_name : name of the new folder on the Desktop

    Returns a list of the full file paths that were saved successfully.

    Example:
        paths = save_images(frames, "experiment_01")
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    output_dir = os.path.join(desktop, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    saved_paths = []
    for i, frame in enumerate(frames):
        filename = f"frame_{i + 1:03d}.png"
        filepath = os.path.join(output_dir, filename)
        success = cv2.imwrite(filepath, frame)
        if success:
            print(f"Saved: {filepath}")
            saved_paths.append(filepath)
        else:
            print(f"Failed to save: {filepath}")

    return saved_paths


# ==============================================================================
# IMAGE SUBTRACTION
# ==============================================================================

def subtract_frames(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """
    Compute the absolute pixel-wise difference between two frames.

    Bright pixels in the result = large change between the two frames.
    Dark pixels = no change. This is the core operation in ESPI.

    Uses cv2.absdiff instead of plain numpy subtraction to avoid uint8
    overflow (e.g. 10 - 20 wraps to 246 in numpy but gives 10 here).

    Args:
        frame_a : first frame (numpy array, uint8 greyscale)
        frame_b : second frame (numpy array, uint8 greyscale, same shape)

    Returns a uint8 numpy array of the same shape.

    Example:
        diff = subtract_frames(frames[0], frames[1])
        cv2.imshow("Difference", diff)
        cv2.waitKey(0)
    """
    assert frame_a.shape == frame_b.shape, (
        f"Frame shapes must match: {frame_a.shape} vs {frame_b.shape}"
    )
    return cv2.absdiff(frame_a, frame_b)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    # --- User input ---
    exposure_us = float(input("Exposure time (µs): "))
    n           = int(input("Number of images to grab: "))
    folder_name = input("Output folder name (will be created on Desktop): ").strip()

    # --- Connect ---
    camera = connect_camera()
    if camera is None:
        return

    try:
        # --- Capture ---
        frames = capture_images(camera, n, exposure_us)

        if not frames:
            print("No frames captured — exiting.")
            return

        # --- Display ---
        display_images(frames)

        # --- Save ---
        save_images(frames, folder_name)

    finally:
        disconnect_camera(camera)


if __name__ == "__main__":
    main()
